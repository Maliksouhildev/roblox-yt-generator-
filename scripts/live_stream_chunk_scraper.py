#!/usr/bin/env python3
"""
live_stream_chunk_scraper.py
----------------------------
Two-tier GTA 6 live stream & recent VOD rolling 1-hour chunk scraper.

Tier 1 VIP YouTube (/live + /streams 1-3) and Tier 1 Twitch (/live), plus
Tier 2 dynamic YouTube search ("ytsearch15:GTA 6 live gameplay"), ranked by
VIP priority, concurrent viewers / view count, and chunk-diversity penalty.

Enforces a 45-minute (2700s) minimum live buffer, slices 1-hour (3600s) chunks
via fast FFmpeg stream-copy, time-offsets .live_chat.json sidecars, reuses
downloaded temp VODs until fully sliced, and tracks state/lockfile cleanly.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

VIP_YT_HANDLES = [
    "@DarkViperAU",
    "@LazarBeam",
    "@Loserfruit",
    "@Muselk",
    "@TypicalGamer",
    "@IShowSpeed",
    "@CaseOh_",
    "@penguinz0",
    "@Valkyrae",
    "@TimTheTatman",
    "@DrDisRespect",
    "@Sykkuno",
]

VIP_TWITCH_HANDLES = [
    "kaicenat",
    "xqc",
    "jynxzi",
    "caseoh_",
    "lirik",
    "summit1g",
    "tarik",
]

LIVE_YT_POOL = [f"https://www.youtube.com/{h}/live" for h in VIP_YT_HANDLES]
VOD_FALLBACK_POOL = [f"https://www.youtube.com/{h}/streams" for h in VIP_YT_HANDLES]
LIVE_TWITCH_POOL = [f"https://www.twitch.tv/{h}" for h in VIP_TWITCH_HANDLES]
TIER2_SEARCH_QUERY = "ytsearch15:GTA 6 live gameplay"

VIP_HANDLES_LOWER = {h.lstrip("@").strip().lower() for h in VIP_YT_HANDLES + VIP_TWITCH_HANDLES}

GTA6_CONTENT_RE = re.compile(
    r"(?:gta\s*6(?![0-9])|gta\s*vi(?![a-z])|grand\s+theft\s+auto\s*(?:vi|6)(?![a-z0-9])|vice\s*city|\bleonida\b)",
    re.IGNORECASE,
)

INPUTS_DIR = "/files/inputs"
TEMP_DIR = "/files/temp"
STATE_PATH = "/files/temp/live_chunks_state.json"
LOCK_PATH = "/files/temp/live_chunk_scraper.lock"
ARCHIVE_PATH = "/files/downloaded.txt"

CHUNK_SEC = 3000            # 50 minutes max per chunk (targets 2700s-3600s DVR chunks)
MIN_LIVE_BUFFER_SEC = 0     # Never sleep-wait for fresh streams; capture immediately
MIN_LIVE_DVR_ELAPSED_SEC = 1800  # >=30m live -> --live-from-start -N 8 with 180s cap
DVR_FETCH_TIMEOUT_SEC = 180      # 3-minute max yt-dlp network fetch (SIGINT remux)
LIVE_EDGE_RECORD_SEC = 180       # 3-minute max fast live-edge capture (180s SIGINT cap)
LOCK_EXPIRE_SEC = 1500      # 25 minutes auto-expiry
PROBE_TIMEOUT_SEC = 6
POLL_INTERVAL_SEC = 60
MAX_WAIT_SEC = 0
MAX_VOD_DUR_SEC = 36000
MIN_VALID_BYTES = 5 * 1024 * 1024
MIN_VALID_DUR_SEC = 600.0
MIN_LIVE_CHUNK_DUR_SEC = 1200.0
MIN_SLICE_DUR_SEC = 30.0
PROBE_WORKERS = 8


def fmt_hhmmss(total_sec: int) -> str:
    sec = max(0, int(total_sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_ffmpeg_sec(sec: float) -> str:
    val = max(0.0, float(sec))
    if abs(val - round(val)) < 1e-6:
        return str(int(round(val)))
    return f"{val:.3f}".rstrip("0").rstrip(".")


def yt_dlp_cmd_prefix() -> list[str]:
    if os.path.exists("/files/yt-dlp"):
        return ["python3", "/files/yt-dlp"]
    return ["yt-dlp"]


def sanitize_slug(val: str, fallback: str = "creator") -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]", "", str(val or "").replace("@", "").strip())
    return clean[:48] or fallback


def probe_duration(video_path: str) -> float:
    if not video_path or not os.path.exists(video_path):
        return 0.0
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).decode("utf-8", errors="replace").strip()
        return max(0.0, float(out))
    except Exception:
        return 0.0


def load_json(path: str, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def acquire_lock(lock_path: str = LOCK_PATH, expire_sec: float = LOCK_EXPIRE_SEC) -> bool:
    if os.path.exists(lock_path):
        info = load_json(lock_path, {})
        if not isinstance(info, dict):
            info = {}
        started = float(info.get("started_epoch") or 0.0)
        if started <= 0.0:
            try:
                started = float(os.path.getmtime(lock_path))
            except Exception:
                started = 0.0
        age = time.time() - started
        pid = int(info.get("pid", 0) or 0)
        if age < expire_sec and is_pid_alive(pid):
            return False
    save_json(lock_path, {"pid": os.getpid(), "started_epoch": time.time()})
    return True


def release_lock(lock_path: str = LOCK_PATH) -> None:
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


def _parse_single_json_output(stdout: str) -> dict | None:
    if not stdout or not stdout.strip():
        return None
    for line in reversed(stdout.strip().splitlines()):
        line_s = line.strip()
        if not line_s.startswith("{"):
            continue
        try:
            data = json.loads(line_s)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None


def _normalize_probed_entry(data: dict, fallback_url: str = "", force_vip: bool | None = None) -> dict | None:
    if not isinstance(data, dict) or not data.get("id"):
        return None
    vid = str(data["id"])
    raw_url = str(data.get("webpage_url") or data.get("url") or fallback_url or f"https://www.youtube.com/watch?v={vid}")
    if not raw_url.startswith("http"):
        raw_url = f"https://www.youtube.com/watch?v={vid}"
    live_status = str(data.get("live_status") or "").lower()
    is_live = bool(data.get("is_live", False)) or live_status == "is_live"
    extractor = str(data.get("extractor_key") or data.get("extractor") or data.get("ie_key") or "").lower()
    if not extractor and "twitch.tv" in raw_url.lower():
        extractor = "twitch"
    elif not extractor:
        extractor = "youtube"
    uploader_id = str(
        data.get("uploader_id")
        or data.get("display_id")
        or data.get("channel")
        or data.get("uploader")
        or "Streamer"
    )
    meta = {
        "url": raw_url,
        "id": vid,
        "title": str(data.get("title") or vid),
        "fulltitle": str(data.get("fulltitle") or ""),
        "description": str(data.get("description") or ""),
        "tags": list(data.get("tags") or []),
        "categories": list(data.get("categories") or []),
        "game": str(data.get("game") or data.get("category") or ""),
        "is_live": is_live,
        "live_status": live_status,
        "release_timestamp": float(data.get("release_timestamp") or 0.0),
        "timestamp": float(data.get("timestamp") or 0.0),
        "concurrent_viewers": data.get("concurrent_viewers"),
        "concurrent_view_count": data.get("concurrent_view_count"),
        "view_count": data.get("view_count"),
        "uploader_id": uploader_id,
        "uploader": str(data.get("uploader") or data.get("channel") or ""),
        "channel": str(data.get("channel") or ""),
        "display_id": str(data.get("display_id") or ""),
        "extractor": extractor,
        "duration": float(data.get("duration") or 0.0),
    }
    if force_vip is not None:
        meta["is_vip"] = bool(force_vip) or is_vip_creator(meta)
    else:
        meta["is_vip"] = is_vip_creator(meta)
    return meta


def probe_stream(url: str, timeout_sec: int = PROBE_TIMEOUT_SEC) -> dict | None:
    """Probe single URL via yt-dlp --dump-single-json without downloading media."""
    cmd = yt_dlp_cmd_prefix() + [
        "--dump-single-json", "--no-warnings", "--no-playlist", url,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if res.returncode != 0:
            return None
        data = _parse_single_json_output(res.stdout)
        if not data:
            return None
        if data.get("_type") == "playlist" and data.get("entries"):
            data = data["entries"][0]
        return _normalize_probed_entry(data, fallback_url=url)
    except Exception:
        return None


def discover_flat_playlist(url_or_query: str, playlist_items: str | None = None, timeout_sec: int = PROBE_TIMEOUT_SEC) -> list[dict]:
    """Run yt-dlp --flat-playlist --dump-single-json on a channel /streams URL or ytsearch query."""
    cmd = yt_dlp_cmd_prefix() + ["--flat-playlist"]
    if playlist_items:
        cmd.extend(["--playlist-items", str(playlist_items)])
    cmd.extend(["--dump-single-json", "--no-warnings", url_or_query])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        if res.returncode != 0:
            return []
        data = _parse_single_json_output(res.stdout)
        if not data:
            return []
        entries = data.get("entries")
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict) and e.get("id")]
        if data.get("id") and data.get("_type") != "playlist":
            return [data]
        return []
    except Exception:
        return []


def is_vip_creator(meta: dict) -> bool:
    if meta.get("is_vip") is True:
        return True
    for field in ("uploader_id", "display_id", "uploader", "channel"):
        raw = str(meta.get(field) or "").strip()
        if not raw:
            continue
        norm = raw.lstrip("@").strip().lower()
        compact = re.sub(r"\s+", "", norm)
        if norm in VIP_HANDLES_LOWER or compact in VIP_HANDLES_LOWER:
            return True
    url_low = str(meta.get("url") or "").lower()
    for handle in VIP_HANDLES_LOWER:
        if f"/@{handle}/" in url_low or f"twitch.tv/{handle}" in url_low:
            return True
    return False


def is_gta6_content(meta: dict) -> bool:
    parts = [
        str(meta.get("title") or ""),
        str(meta.get("fulltitle") or ""),
        str(meta.get("description") or ""),
        str(meta.get("game") or ""),
    ]
    for lst_key in ("tags", "categories"):
        vals = meta.get(lst_key)
        if isinstance(vals, list):
            parts.extend(str(v) for v in vals if v)
    haystack = " ".join(parts)
    return bool(GTA6_CONTENT_RE.search(haystack))


def is_after_launch_window(now_epoch: float) -> bool:
    """Return True when local CET >= 12:00 PM (11:00 UTC) today."""
    dt_utc = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    cutoff_utc = dt_utc.replace(hour=11, minute=0, second=0, microsecond=0).timestamp()
    return now_epoch >= cutoff_utc


def is_eligible_candidate(meta: dict, now_epoch: float) -> bool:
    live_status = str(meta.get("live_status") or "").lower()
    if live_status == "is_upcoming":
        return False
    is_live = bool(meta.get("is_live", False))
    dur = float(meta.get("duration") or 0.0)
    if not is_live and dur > 0.0:
        if dur < MIN_VALID_DUR_SEC or dur > MAX_VOD_DUR_SEC:
            return False
    if is_gta6_content(meta):
        return True
    if is_vip_creator(meta) and is_live and is_after_launch_window(now_epoch):
        return True
    return False


def get_candidate_viewers(meta: dict) -> int:
    for key in ("concurrent_viewers", "concurrent_view_count", "view_count"):
        val = meta.get(key)
        if val is not None:
            try:
                num = int(float(val))
                if num > 0:
                    return num
            except (TypeError, ValueError):
                pass
    return 0


def get_chunks_taken(meta: dict, state: dict | None) -> int:
    st = (state or {}).get(str(meta.get("id") or ""), {})
    if not isinstance(st, dict):
        return 0
    if st.get("chunks_downloaded") is not None:
        return max(0, int(st.get("chunks_downloaded") or 0))
    chunk_idx = int(st.get("chunk_idx", 1) or 1)
    return max(0, chunk_idx - 1)


def score_candidate(meta: dict, state: dict | None = None) -> float:
    """
    Score candidate by:
      (is_vip * 50) + log10(concurrent_viewers or view_count + 1) * 15 - (chunks_already_taken * 25)
    """
    vip_flag = 1 if is_vip_creator(meta) else 0
    viewers = max(0, get_candidate_viewers(meta))
    chunks_taken = get_chunks_taken(meta, state)
    score = (vip_flag * 50.0) + (math.log10(viewers + 1) * 15.0) - (chunks_taken * 25.0)
    return round(score, 4)


def get_live_start_epoch(meta: dict) -> float:
    rel_ts = float(meta.get("release_timestamp") or 0.0)
    if rel_ts > 0.0:
        return rel_ts
    # Twitch streams do not set release_timestamp; timestamp is the live start time.
    extractor = str(meta.get("extractor") or "").lower()
    url_low = str(meta.get("url") or "").lower()
    if "youtube" not in extractor and "youtube.com" not in url_low and "youtu.be" not in url_low:
        return max(0.0, float(meta.get("timestamp") or 0.0))
    return 0.0


def compute_live_buffer_status(meta: dict, st: dict, now_epoch: float) -> tuple[float, float]:
    """Return (buffered_sec, wait_needed_sec) for an active live stream."""
    last_end_sec = int(st.get("last_end_sec", 0) or 0)
    start_ts = get_live_start_epoch(meta)
    if start_ts > 0.0:
        elapsed = max(0.0, now_epoch - start_ts)
    else:
        last_scraped = float(st.get("last_scraped_epoch") or 0.0)
        if last_end_sec > 0 and last_scraped > 0.0:
            elapsed = last_end_sec + max(0.0, now_epoch - last_scraped)
        else:
            elapsed = last_end_sec + MIN_LIVE_BUFFER_SEC
    buffered = elapsed - last_end_sec
    wait_needed = max(0.0, MIN_LIVE_BUFFER_SEC - buffered)
    return buffered, wait_needed


def discover_and_probe_candidates(
    state: dict | None = None,
    yt_live_urls: list[str] | None = None,
    yt_vod_urls: list[str] | None = None,
    twitch_urls: list[str] | None = None,
    search_query: str | None = TIER2_SEARCH_QUERY,
    max_workers: int = PROBE_WORKERS,
    fast_live_first: bool = False,
) -> list[dict]:
    """Discover Tier 1 YT/Twitch + Tier 2 search candidates and probe full metadata cleanly."""
    state = state or {}
    yt_live_urls = LIVE_YT_POOL if yt_live_urls is None else yt_live_urls
    yt_vod_urls = VOD_FALLBACK_POOL if yt_vod_urls is None else yt_vod_urls
    twitch_urls = LIVE_TWITCH_POOL if twitch_urls is None else twitch_urls

    by_id: dict[str, dict] = {}
    to_probe: dict[str, tuple[str, bool]] = {}

    def _queue_candidate(entry: dict, force_vip: bool, source_url: str = "") -> None:
        vid = str(entry.get("id") or "")
        if not vid or vid in by_id:
            return
        st = state.get(vid, {}) if isinstance(state, dict) else {}
        if isinstance(st, dict) and st.get("completed"):
            return
        live_status = str(entry.get("live_status") or "").lower()
        if live_status == "is_upcoming":
            return
        is_live_hint = bool(entry.get("is_live", False)) or live_status == "is_live"
        dur_hint = float(entry.get("duration") or 0.0)
        if not is_live_hint and dur_hint > 0.0 and (dur_hint < MIN_VALID_DUR_SEC or dur_hint > MAX_VOD_DUR_SEC):
            return
        if not is_live_hint and dur_hint > 0.0 and isinstance(st, dict):
            last_end = int(st.get("last_end_sec", 0) or 0)
            if last_end >= dur_hint - 5 or (last_end > 0 and dur_hint - last_end < MIN_SLICE_DUR_SEC):
                return

        cand_url = str(entry.get("url") or f"https://www.youtube.com/watch?v={vid}")
        if not cand_url.startswith("http"):
            cand_url = f"https://www.youtube.com/watch?v={vid}"
        prev = to_probe.get(vid)
        prev_vip = prev[1] if prev else False
        # Preserve VIP hint from /streams source URL if applicable
        src_vip = force_vip or any(f"/@{h}/" in source_url.lower() for h in VIP_HANDLES_LOWER)
        to_probe[vid] = (cand_url, prev_vip or src_vip)

    if fast_live_first:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            live_futs = {pool.submit(probe_stream, u, PROBE_TIMEOUT_SEC): u for u in (yt_live_urls + twitch_urls)}
            for fut in as_completed(live_futs):
                try:
                    meta = fut.result()
                    if meta and meta.get("id"):
                        meta["is_vip"] = True
                        by_id[meta["id"]] = meta
                except Exception:
                    pass
        now_ep = time.time()
        if any(is_eligible_candidate(m, now_ep) for m in by_id.values()):
            return list(by_id.values())

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        live_futs = {} if fast_live_first else {pool.submit(probe_stream, u, PROBE_TIMEOUT_SEC): u for u in (yt_live_urls + twitch_urls)}
        vod_futs = {pool.submit(discover_flat_playlist, u, "1-3", PROBE_TIMEOUT_SEC): u for u in yt_vod_urls}
        search_fut = pool.submit(discover_flat_playlist, search_query, None, PROBE_TIMEOUT_SEC) if search_query else None

        for fut in as_completed(live_futs):
            src_u = live_futs[fut]
            try:
                meta = fut.result()
                if meta and meta.get("id"):
                    meta["is_vip"] = True
                    by_id[meta["id"]] = meta
            except Exception:
                pass

        for fut in as_completed(vod_futs):
            src_u = vod_futs[fut]
            try:
                for entry in fut.result() or []:
                    _queue_candidate(entry, force_vip=True, source_url=src_u)
            except Exception:
                pass

        if search_fut is not None:
            try:
                for entry in search_fut.result() or []:
                    _queue_candidate(entry, force_vip=False, source_url="")
            except Exception:
                pass

    pending = [(vid, url, vip_hint) for vid, (url, vip_hint) in to_probe.items() if vid not in by_id]
    if pending:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            probe_futs = {pool.submit(probe_stream, url, PROBE_TIMEOUT_SEC): (vid, vip_hint) for vid, url, vip_hint in pending}
            for fut in as_completed(probe_futs):
                vid, vip_hint = probe_futs[fut]
                try:
                    meta = fut.result()
                    if meta and meta.get("id"):
                        if vip_hint:
                            meta["is_vip"] = True
                        by_id[meta["id"]] = meta
                except Exception:
                    pass

    return list(by_id.values())


def evaluate_candidates(probed_streams: list[dict], state: dict, now_epoch: float) -> list[dict]:
    """Filter, score, and annotate all eligible candidates with buffer & chunk state."""
    state = state or {}
    evaluated = []
    seen_ids = set()

    for raw_meta in probed_streams:
        if not isinstance(raw_meta, dict) or not raw_meta.get("id"):
            continue
        vid = str(raw_meta["id"])
        if vid in seen_ids:
            continue
        seen_ids.add(vid)

        meta = dict(raw_meta)
        meta["is_vip"] = is_vip_creator(meta)
        if not is_eligible_candidate(meta, now_epoch):
            continue

        st = state.get(vid, {})
        if not isinstance(st, dict):
            st = {}

        is_live = bool(meta.get("is_live", False))
        last_end_sec = int(st.get("last_end_sec", 0) or 0)
        chunks_taken = get_chunks_taken(meta, state)
        chunk_idx = int(st.get("chunk_idx") or (chunks_taken + 1))

        if not is_live:
            if st.get("completed"):
                continue
            vod_dur = float(meta.get("duration") or st.get("source_duration_sec") or 0.0)
            if vod_dur > 0.0:
                if last_end_sec >= vod_dur - 5:
                    continue
                if last_end_sec > 0 and (vod_dur - last_end_sec) < MIN_SLICE_DUR_SEC:
                    continue
            buffered_sec = max(0.0, vod_dur - last_end_sec) if vod_dur > 0 else float(CHUNK_SEC)
            wait_needed_sec = 0.0
            ready = True
        else:
            buffered_sec, wait_needed_sec = compute_live_buffer_status(meta, st, now_epoch)
            ready = wait_needed_sec <= 0.0

        viewers = get_candidate_viewers(meta)
        score = score_candidate(meta, state)
        meta.update({
            "is_vip": meta["is_vip"],
            "viewers": viewers,
            "chunks_already_taken": chunks_taken,
            "last_end_sec": last_end_sec,
            "chunk_idx": chunk_idx,
            "buffered_sec": round(buffered_sec, 1),
            "wait_needed_sec": int(math.ceil(wait_needed_sec)),
            "ready": ready,
            "score": score,
        })
        evaluated.append(meta)

    evaluated.sort(
        key=lambda c: (
            1 if c["ready"] else 0,
            1 if c.get("is_live") else 0,
            c["score"],
            1 if c.get("is_vip") else 0,
            c["viewers"],
        ),
        reverse=True,
    )
    return evaluated


def select_best_candidate(
    probed_streams: list[dict],
    state: dict,
    now_epoch: float,
    allow_wait: bool = True,
) -> tuple[dict | None, int]:
    """
    Rank eligible candidates by VIP + log10(viewers+1)*15 - chunks_taken*25.
    Enforces >= 2700s live buffer for live streams; if all live streams are < 2700s
    and no VOD is ready, returns the leading waiting stream with wait_needed_sec.
    """
    evaluated = evaluate_candidates(probed_streams, state, now_epoch)
    ready = [c for c in evaluated if c["ready"]]
    if ready:
        return ready[0], 0

    waiting = [c for c in evaluated if c.get("is_live") and c["wait_needed_sec"] > 0]
    if waiting:
        if allow_wait:
            best_fresh = min(waiting, key=lambda c: (c["wait_needed_sec"], -c["score"]))
            return best_fresh, max(1, int(best_fresh["wait_needed_sec"]))
        best_fresh = max(waiting, key=lambda c: (c["score"], -c["wait_needed_sec"]))
        return best_fresh, 0

    return None, 0


def validate_chunk_file(
    mp4_path: str,
    min_bytes: int | None = None,
    min_dur: float | None = None,
) -> tuple[bool, float, int]:
    if min_bytes is None:
        min_bytes = MIN_VALID_BYTES
    if min_dur is None:
        min_dur = MIN_VALID_DUR_SEC
    if not mp4_path or not os.path.exists(mp4_path):
        return False, 0.0, 0
    size = os.path.getsize(mp4_path)
    if size <= min_bytes:
        return False, 0.0, size
    dur = probe_duration(mp4_path)
    return (dur >= min_dur), dur, size


def find_live_chat_file(base_path: str) -> str | None:
    direct = base_path + ".live_chat.json"
    if os.path.exists(direct):
        return direct
    for cand in sorted(glob.glob(base_path + ".*live_chat*.json")):
        if os.path.isfile(cand):
            return cand
    return None


def normalize_chat_sidecar(out_base: str) -> None:
    """Normalize yt-dlp language-suffixed chat files (e.g. .en.live_chat.json -> .live_chat.json)."""
    target = out_base + ".live_chat.json"
    if os.path.exists(target):
        return
    for cand in sorted(glob.glob(out_base + ".*live_chat*.json")):
        try:
            os.replace(cand, target)
            return
        except Exception:
            pass


def cleanup_partial_files(out_base: str) -> None:
    for p in glob.glob(out_base + "*"):
        if p.endswith(".mp4") and os.path.exists(p) and os.path.getsize(p) > MIN_VALID_BYTES and probe_duration(p) >= MIN_VALID_DUR_SEC:
            continue
        if p.endswith(".part") or p.endswith(".ytdl") or (p.endswith(".mp4") and os.path.getsize(p) <= MIN_VALID_BYTES):
            try:
                os.remove(p)
            except Exception:
                pass


def _extract_nested_timestamp_usec(data: dict) -> int | None:
    top_ts = data.get("timestampUsec")
    if top_ts is not None:
        try:
            return int(float(top_ts))
        except (TypeError, ValueError):
            pass
    replay = data.get("replayChatItemAction")
    actions = replay.get("actions") if isinstance(replay, dict) else data.get("actions")
    if not isinstance(actions, list):
        return None
    for act in actions:
        if not isinstance(act, dict):
            continue
        for cmd_key in ("addChatItemAction", "addLiveChatTickerItemAction", "addBannerToLiveChatCommand"):
            cmd = act.get(cmd_key)
            if not isinstance(cmd, dict):
                continue
            item = cmd.get("item") or cmd.get("bannerRenderer")
            if not isinstance(item, dict):
                continue
            for renderer in item.values():
                if isinstance(renderer, dict) and renderer.get("timestampUsec") is not None:
                    try:
                        return int(float(renderer["timestampUsec"]))
                    except (TypeError, ValueError):
                        pass
    return None


def _shift_relative_timestamp_usec(data: dict, shift_usec: int) -> None:
    if "timestampUsec" in data and data["timestampUsec"] is not None:
        try:
            ts = int(float(data["timestampUsec"]))
            if 0 <= ts < 10**12:
                new_ts = max(0, ts - shift_usec)
                data["timestampUsec"] = str(new_ts) if isinstance(data["timestampUsec"], str) else new_ts
        except (TypeError, ValueError):
            pass
    replay = data.get("replayChatItemAction")
    actions = replay.get("actions") if isinstance(replay, dict) else data.get("actions")
    if not isinstance(actions, list):
        return
    for act in actions:
        if not isinstance(act, dict):
            continue
        for cmd_key in ("addChatItemAction", "addLiveChatTickerItemAction", "addBannerToLiveChatCommand"):
            cmd = act.get(cmd_key)
            if not isinstance(cmd, dict):
                continue
            item = cmd.get("item") or cmd.get("bannerRenderer")
            if not isinstance(item, dict):
                continue
            for renderer in item.values():
                if isinstance(renderer, dict) and renderer.get("timestampUsec") is not None:
                    try:
                        ts = int(float(renderer["timestampUsec"]))
                        if 0 <= ts < 10**12:
                            new_ts = max(0, ts - shift_usec)
                            renderer["timestampUsec"] = str(new_ts) if isinstance(renderer["timestampUsec"], str) else new_ts
                    except (TypeError, ValueError):
                        pass


def slice_live_chat_json(
    src_path: str,
    dst_path: str,
    start_sec: float,
    end_sec: float,
    stream_start_epoch: float = 0.0,
) -> int:
    """
    Filter NDJSON .live_chat.json / .en.live_chat.json events to [start_sec, end_sec]
    and shift offsets by -start_sec so chat timestamps align 1:1 with the sliced chunk.
    Returns count of written chat lines.
    """
    if not src_path or not os.path.exists(src_path):
        return 0

    start_ms = int(round(max(0.0, float(start_sec)) * 1000.0))
    end_ms = int(round(max(0.0, float(end_sec)) * 1000.0))
    shift_usec = start_ms * 1000

    parsed_items: list[dict] = []
    min_epoch_usec: int | None = None

    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_s = line.strip()
            if not line_s:
                continue
            try:
                obj = json.loads(line_s)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            parsed_items.append(obj)
            has_offset = (
                obj.get("videoOffsetTimeMsec") is not None
                or (isinstance(obj.get("replayChatItemAction"), dict) and obj["replayChatItemAction"].get("videoOffsetTimeMsec") is not None)
            )
            if not has_offset:
                ts_u = _extract_nested_timestamp_usec(obj)
                if ts_u is not None and ts_u >= 10**12:
                    if min_epoch_usec is None or ts_u < min_epoch_usec:
                        min_epoch_usec = ts_u

    base_epoch_usec = int(stream_start_epoch * 1_000_000) if stream_start_epoch > 0 else min_epoch_usec
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    written = 0

    with open(dst_path, "w", encoding="utf-8") as out_f:
        for obj in parsed_items:
            replay = obj.get("replayChatItemAction")
            raw_off = obj.get("videoOffsetTimeMsec")
            if raw_off is None and isinstance(replay, dict):
                raw_off = replay.get("videoOffsetTimeMsec")

            offset_ms: int | None = None
            if raw_off is not None:
                try:
                    offset_ms = int(round(float(raw_off)))
                except (TypeError, ValueError):
                    offset_ms = None
            else:
                ts_u = _extract_nested_timestamp_usec(obj)
                if ts_u is not None:
                    if ts_u < 10**12:
                        offset_ms = ts_u // 1000
                    elif base_epoch_usec is not None:
                        offset_ms = (ts_u - base_epoch_usec) // 1000

            if offset_ms is None or offset_ms < start_ms or offset_ms > end_ms:
                continue

            new_offset_ms = max(0, offset_ms - start_ms)
            new_offset_str = str(new_offset_ms)

            if "videoOffsetTimeMsec" in obj:
                obj["videoOffsetTimeMsec"] = new_offset_str
            if isinstance(replay, dict):
                if "videoOffsetTimeMsec" in replay or "videoOffsetTimeMsec" not in obj:
                    replay["videoOffsetTimeMsec"] = new_offset_str
            elif "videoOffsetTimeMsec" not in obj:
                obj["videoOffsetTimeMsec"] = new_offset_str

            _shift_relative_timestamp_usec(obj, shift_usec)
            out_f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            written += 1

    return written


def build_yt_live_dvr_command(
    meta: dict,
    raw_tpl: str,
    now_epoch: float | None = None,
) -> list[str]:
    """
    Build BusyBox timeout + yt-dlp command for YouTube Live.
    Never downloads live_chat on active live streams (which stalls yt-dlp).
    - elapsed >= 1800s (30m+ live): --live-from-start -N 8 with 180s SIGINT cap
    - elapsed < 1800s or unknown: 1200s live-edge capture with -N 8 (no --live-from-start)
    """
    yt_cmd = yt_dlp_cmd_prefix()
    start_ts = get_live_start_epoch(meta)
    cur_epoch = time.time() if now_epoch is None else float(now_epoch)
    elapsed_live_sec = max(0.0, cur_epoch - start_ts) if start_ts > 0.0 else None

    if elapsed_live_sec is not None and elapsed_live_sec >= MIN_LIVE_DVR_ELAPSED_SEC:
        return [
            "timeout", "-s", "INT", "-k", "30", str(DVR_FETCH_TIMEOUT_SEC),
            *yt_cmd,
            "--live-from-start",
            "-N", "8",
            "--write-info-json",
            "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", raw_tpl,
            meta["url"],
        ]

    return [
        "timeout", "-s", "INT", "-k", "30", str(LIVE_EDGE_RECORD_SEC),
        *yt_cmd,
        "-N", "8",
        "--write-info-json",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", raw_tpl,
        meta["url"],
    ]


def build_twitch_live_command(meta: dict, out_base: str) -> list[str]:
    yt_cmd = yt_dlp_cmd_prefix()
    return [
        "timeout", "-s", "INT", "-k", "30", str(LIVE_EDGE_RECORD_SEC),
        *yt_cmd,
        "-N", "8",
        "--write-info-json",
        "-f", "best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", out_base + ".%(ext)s",
        meta["url"],
    ]


def build_vod_download_command(meta: dict, vod_base: str) -> list[str]:
    yt_cmd = yt_dlp_cmd_prefix()
    return [
        "timeout", "-s", "INT", "-k", "30", str(DVR_FETCH_TIMEOUT_SEC),
        *yt_cmd,
        "-N", "8",
        "--socket-timeout", "20",
        "--no-playlist",
        "--match-filter", f"duration <= {MAX_VOD_DUR_SEC}",
        "--write-info-json",
        "--write-subs", "--sub-langs", "live_chat",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", vod_base + ".%(ext)s",
        meta["url"],
    ]


def build_ffmpeg_slice_command(src_mp4: str, dst_mp4: str, start_sec: float, slice_dur: float) -> list[str]:
    return [
        "ffmpeg", "-loglevel", "error", "-y",
        "-ss", _fmt_ffmpeg_sec(start_sec),
        "-t", _fmt_ffmpeg_sec(slice_dur),
        "-i", src_mp4,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        dst_mp4,
    ]


def build_download_commands(meta: dict, start_sec: int, end_sec: int, out_base: str, temp_dir: str = TEMP_DIR) -> list[list[str]]:
    """Build primary download (+ slice preview) command list for dry-run inspection & tests."""
    url = meta["url"]
    vid = str(meta.get("id") or "stream")
    is_live = bool(meta.get("is_live"))
    is_twitch = ("twitch" in str(meta.get("extractor", "")).lower()) or ("twitch.tv" in url.lower())
    slice_dur = max(1, int(end_sec) - int(start_sec))

    if is_live and not is_twitch:
        raw_base = os.path.join(temp_dir, f"raw_live_{vid}")
        return [
            build_yt_live_dvr_command(meta, os.path.join(temp_dir, "raw_live_%(id)s.%(ext)s")),
            build_ffmpeg_slice_command(raw_base + ".mp4", out_base + ".mp4", start_sec, slice_dur),
        ]

    if is_live and is_twitch:
        return [build_twitch_live_command(meta, out_base)]

    vod_base = os.path.join(temp_dir, f"vod_{vid}")
    return [
        build_vod_download_command(meta, vod_base),
        build_ffmpeg_slice_command(vod_base + ".mp4", out_base + ".mp4", start_sec, slice_dur),
    ]


def slice_and_copy_sidecars(
    src_base: str,
    src_mp4: str,
    out_base: str,
    start_sec: float,
    chunk_sec: float | None = None,
    min_slice_sec: float | None = None,
    stream_start_epoch: float = 0.0,
) -> tuple[bool, float, float, float]:
    """
    Probe src_mp4 duration, slice [start_sec, min(actual_dur, start_sec + chunk_sec)]
    with fast stream-copy, copy .info.json, and slice/time-offset .live_chat.json.
    Returns (ok, actual_dur, end_sec, slice_dur).
    """
    if chunk_sec is None:
        chunk_sec = CHUNK_SEC
    if min_slice_sec is None:
        min_slice_sec = MIN_SLICE_DUR_SEC
    actual_dur = probe_duration(src_mp4)
    if actual_dur < min_slice_sec:
        return False, actual_dur, float(start_sec), 0.0

    end_sec = min(actual_dur, float(start_sec) + float(chunk_sec))
    slice_dur = end_sec - float(start_sec)
    if slice_dur < min_slice_sec:
        return False, actual_dur, end_sec, slice_dur

    out_mp4 = out_base + ".mp4"
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    ff_cmd = build_ffmpeg_slice_command(src_mp4, out_mp4, start_sec, slice_dur)
    res = subprocess.run(ff_cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0 or not os.path.exists(out_mp4):
        return False, actual_dur, end_sec, slice_dur

    src_info = src_base + ".info.json"
    if os.path.exists(src_info):
        shutil.copy2(src_info, out_base + ".info.json")

    src_chat = find_live_chat_file(src_base)
    if src_chat:
        slice_live_chat_json(
            src_chat,
            out_base + ".live_chat.json",
            start_sec,
            end_sec,
            stream_start_epoch=stream_start_epoch,
        )

    return True, actual_dur, end_sec, slice_dur


def _finalize_separated_video_audio(raw_base: str, out_mp4: str) -> bool:
    """If yt-dlp was stopped via SIGINT before remuxing, combine separate .f299/.f140 or .part files."""
    if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
        return True

    # Find largest valid video and audio files (skip tiny per-fragment .part-FragN artifacts)
    v_cands = []
    a_cands = []
    part_cands = []
    for p in glob.glob(raw_base + "*"):
        if not os.path.isfile(p):
            continue
        lower = p.lower()
        if "info.json" in lower or lower.endswith(".ytdl") or ".part-frag" in lower:
            continue
        sz = os.path.getsize(p)
        if any(tag in lower for tag in [".f299", ".f137", ".f136", "bestvideo", "video"]):
            if sz > 512 * 1024:
                v_cands.append((sz, p))
        elif any(tag in lower for tag in [".f140", ".f251", "bestaudio", "audio"]):
            if sz > 50 * 1024:
                a_cands.append((sz, p))
        elif ".part" in lower and sz > 5 * 1024 * 1024:
            part_cands.append((sz, p))

    if v_cands and a_cands:
        v_cand = max(v_cands, key=lambda x: x[0])[1]
        a_cand = max(a_cands, key=lambda x: x[0])[1]
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", v_cand, "-i", a_cand,
            "-c", "copy",
            out_mp4
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if res.returncode == 0 and os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
                return True
        except Exception as exc:
            print(f"[scraper] Video+audio remux warning: {exc}")

    # Check for single combined part file
    for _, p in sorted(part_cands, reverse=True):
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", p, "-c", "copy",
            out_mp4
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if res.returncode == 0 and os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 1024 * 1024:
                return True
        except Exception as exc:
            print(f"[scraper] Single-part remux warning: {exc}")

    return False


def _remove_prefix_files(prefix: str) -> None:
    for p in glob.glob(prefix + "*"):
        try:
            if os.path.isfile(p) or os.path.islink(p):
                os.remove(p)
        except Exception:
            pass


def _probe_report_rows(evaluated: list[dict]) -> list[dict]:
    return [
        {
            "id": c["id"],
            "title": c["title"],
            "url": c["url"],
            "uploader_id": c["uploader_id"],
            "extractor": c.get("extractor", ""),
            "is_live": bool(c.get("is_live")),
            "is_vip": bool(c.get("is_vip")),
            "viewers": int(c.get("viewers", 0)),
            "chunks_already_taken": int(c.get("chunks_already_taken", 0)),
            "last_end_sec": int(c.get("last_end_sec", 0)),
            "chunk_idx": int(c.get("chunk_idx", 1)),
            "buffered_sec": c.get("buffered_sec", 0.0),
            "wait_needed_sec": int(c.get("wait_needed_sec", 0)),
            "ready": bool(c.get("ready")),
            "score": float(c.get("score", 0.0)),
        }
        for c in evaluated
    ]


def run_scraper(
    dry_run: bool = False,
    no_wait: bool = False,
    probe_only: bool = False,
) -> dict:
    if not dry_run and not probe_only:
        os.makedirs(INPUTS_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)

    state = load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}

    now_epoch = time.time()
    discovered = discover_and_probe_candidates(
        state=state,
        fast_live_first=(not probe_only and not dry_run),
    )
    evaluated = evaluate_candidates(discovered, state, now_epoch)
    selected, wait_sec = select_best_candidate(discovered, state, now_epoch, allow_wait=False)

    if probe_only:
        ready_selected = selected if (selected and selected.get("ready")) else None
        return {
            "status": "probe_only",
            "now_epoch": round(now_epoch, 2),
            "total_discovered": len(discovered),
            "eligible_count": len(evaluated),
            "ready_count": sum(1 for c in evaluated if c["ready"]),
            "selected": _probe_report_rows([ready_selected])[0] if ready_selected else None,
            "next_waiting_candidate": _probe_report_rows([selected])[0] if (selected and not selected.get("ready")) else None,
            "wait_needed_sec": int(wait_sec or (selected.get("wait_needed_sec", 0) if selected else 0)),
            "candidates": _probe_report_rows(evaluated),
        }

    if not selected:
        return {"status": "no_streams", "downloaded": False}

    vid = str(selected["id"])
    st = state.get(vid, {}) if isinstance(state.get(vid), dict) else {}
    last_end_sec = int(st.get("last_end_sec", 0) or 0)
    chunks_taken = get_chunks_taken(selected, state)
    chunk_idx = int(st.get("chunk_idx") or (chunks_taken + 1))
    end_offset = last_end_sec + CHUNK_SEC
    uploader_slug = sanitize_slug(
        selected.get("uploader_id") or selected.get("uploader") or selected.get("channel"),
        "Creator",
    )
    base_name = f"{uploader_slug}_{vid}_chunk{chunk_idx}"
    out_base = os.path.join(INPUTS_DIR, base_name)
    out_mp4 = out_base + ".mp4"

    cmds = build_download_commands(selected, last_end_sec, end_offset, out_base)
    if dry_run:
        return {
            "status": "dry_run",
            "selected": _probe_report_rows([selected])[0] if "score" in selected else selected,
            "start_offset": last_end_sec,
            "end_offset": end_offset,
            "chunk_idx": chunk_idx,
            "out_base": out_base,
            "commands": [" ".join(c) for c in cmds],
            "candidates": _probe_report_rows(evaluated),
        }

    is_live = bool(selected.get("is_live"))
    is_twitch = ("twitch" in str(selected.get("extractor", "")).lower()) or ("twitch.tv" in str(selected.get("url", "")).lower())
    rel_ts = get_live_start_epoch(selected)

    ok = False
    dur = 0.0
    size = 0
    new_end_sec = last_end_sec
    vod_dur = 0.0
    finished_vod = False

    if is_live and not is_twitch:
        raw_base = os.path.join(TEMP_DIR, f"raw_live_{vid}")
        raw_mp4 = raw_base + ".mp4"
        _remove_prefix_files(raw_base)
        elapsed_live = max(0.0, now_epoch - rel_ts) if rel_ts > 0.0 else None
        used_dvr = elapsed_live is not None and elapsed_live >= MIN_LIVE_DVR_ELAPSED_SEC
        sub_timeout = (DVR_FETCH_TIMEOUT_SEC + 45) if used_dvr else (LIVE_EDGE_RECORD_SEC + 45)
        try:
            dvr_cmd = build_yt_live_dvr_command(
                selected,
                os.path.join(TEMP_DIR, "raw_live_%(id)s.%(ext)s"),
                now_epoch=now_epoch,
            )
            try:
                subprocess.run(dvr_cmd, timeout=sub_timeout)
            except Exception as ex:
                print(f"[LiveScraper] YT live DVR notice: {ex}", file=sys.stderr)

            _finalize_separated_video_audio(raw_base, raw_mp4)
            if os.path.exists(raw_mp4):
                actual_dur = probe_duration(raw_mp4)
                slice_start = float(last_end_sec) if (used_dvr and actual_dur > last_end_sec + MIN_SLICE_DUR_SEC) else 0.0
                sliced_ok, actual_dur, end_sec, _ = slice_and_copy_sidecars(
                    raw_base,
                    raw_mp4,
                    out_base,
                    slice_start,
                    chunk_sec=CHUNK_SEC,
                    min_slice_sec=MIN_SLICE_DUR_SEC,
                    stream_start_epoch=rel_ts,
                )
                if sliced_ok:
                    ok, dur, size = validate_chunk_file(out_mp4, min_dur=MIN_LIVE_CHUNK_DUR_SEC)
                    if ok:
                        new_end_sec = int(end_sec) if slice_start == float(last_end_sec) else (last_end_sec + int(round(dur)))
                    else:
                        cleanup_partial_files(out_base)
        finally:
            _remove_prefix_files(raw_base)

    elif is_live and is_twitch:
        tw_tmp_base = os.path.join(TEMP_DIR, base_name)
        tw_tmp_mp4 = tw_tmp_base + ".mp4"
        _remove_prefix_files(tw_tmp_base)
        tw_cmd = build_twitch_live_command(selected, tw_tmp_base)
        try:
            subprocess.run(tw_cmd, timeout=LIVE_EDGE_RECORD_SEC + 45)
        except Exception as ex:
            print(f"[LiveScraper] Twitch live notice: {ex}", file=sys.stderr)
        _finalize_separated_video_audio(tw_tmp_base, tw_tmp_mp4)
        normalize_chat_sidecar(tw_tmp_base)
        ok, dur, size = validate_chunk_file(tw_tmp_mp4, min_dur=MIN_LIVE_CHUNK_DUR_SEC)
        if ok:
            os.makedirs(INPUTS_DIR, exist_ok=True)
            shutil.move(tw_tmp_mp4, out_mp4)
            if os.path.exists(tw_tmp_base + ".info.json"):
                shutil.move(tw_tmp_base + ".info.json", out_base + ".info.json")
            new_end_sec = last_end_sec + int(round(dur))
        else:
            _remove_prefix_files(tw_tmp_base)
            cleanup_partial_files(out_base)

    else:
        vod_base = os.path.join(TEMP_DIR, f"vod_{vid}")
        vod_mp4 = vod_base + ".mp4"
        reusable = (
            os.path.exists(vod_mp4)
            and os.path.getsize(vod_mp4) > MIN_VALID_BYTES
            and probe_duration(vod_mp4) >= MIN_SLICE_DUR_SEC
        )
        if not reusable:
            _remove_prefix_files(vod_base)
            vod_cmd = build_vod_download_command(selected, vod_base)
            try:
                subprocess.run(vod_cmd, timeout=DVR_FETCH_TIMEOUT_SEC + 45)
            except Exception as ex:
                print(f"[LiveScraper] VOD download notice: {ex}", file=sys.stderr)
            normalize_chat_sidecar(vod_base)

        if os.path.exists(vod_mp4):
            vod_dur = probe_duration(vod_mp4)
            if vod_dur > 0 and (last_end_sec >= vod_dur - 5 or (vod_dur - last_end_sec) < MIN_SLICE_DUR_SEC):
                state[vid] = {
                    **st,
                    "completed": True,
                    "source_duration_sec": round(vod_dur, 2),
                    "last_scraped_epoch": time.time(),
                }
                save_json(STATE_PATH, state)
                _remove_prefix_files(vod_base)
                return {"status": "vod_already_completed", "downloaded": False, "video_id": vid}

            sliced_ok, vod_dur, end_sec, slice_dur = slice_and_copy_sidecars(
                vod_base,
                vod_mp4,
                out_base,
                last_end_sec,
                chunk_sec=CHUNK_SEC,
                min_slice_sec=MIN_SLICE_DUR_SEC,
                stream_start_epoch=rel_ts,
            )
            if sliced_ok:
                is_final_tail = (end_sec >= vod_dur - 5) and last_end_sec > 0
                min_bytes = min(1024 * 1024, MIN_VALID_BYTES) if is_final_tail else MIN_VALID_BYTES
                min_dur = min(MIN_VALID_DUR_SEC, max(MIN_SLICE_DUR_SEC, slice_dur * 0.7)) if is_final_tail else MIN_VALID_DUR_SEC
                ok, dur, size = validate_chunk_file(out_mp4, min_bytes=min_bytes, min_dur=min_dur)
                if ok:
                    new_end_sec = int(end_sec)
                    finished_vod = new_end_sec >= vod_dur - 5
                    if finished_vod:
                        _remove_prefix_files(vod_base)
                else:
                    cleanup_partial_files(out_base)

    if ok:
        entry_state = {
            "chunks_downloaded": chunk_idx,
            "chunk_idx": chunk_idx + 1,
            "last_end_sec": new_end_sec,
            "last_scraped_epoch": time.time(),
            "uploader_id": uploader_slug,
            "last_file": os.path.basename(out_mp4),
            "duration_sec": round(dur, 2),
        }
        if not is_live and vod_dur > 0:
            entry_state["source_duration_sec"] = round(vod_dur, 2)
            entry_state["completed"] = bool(finished_vod)
        state[vid] = entry_state
        save_json(STATE_PATH, state)
        return {
            "status": "downloaded",
            "downloaded": True,
            "video_id": vid,
            "file": out_mp4,
            "duration_sec": round(dur, 2),
            "size_bytes": size,
            "chunk_idx": chunk_idx,
            "chunks_downloaded": chunk_idx,
            "start_offset": last_end_sec,
            "end_offset": new_end_sec,
            "vod_cleaned": bool(finished_vod),
        }

    return {
        "status": "failed_or_too_short",
        "downloaded": False,
        "video_id": vid,
        "file": out_mp4,
        "duration_sec": round(dur, 2),
        "size_bytes": size,
    }


def _count_fresh_input_chunks() -> int:
    if not os.path.isdir(INPUTS_DIR):
        return 0
    return sum(
        1 for f in os.listdir(INPUTS_DIR)
        if f.endswith(".mp4") and not f.endswith(".processing.mp4") and os.path.getsize(os.path.join(INPUTS_DIR, f)) > MIN_VALID_BYTES
    )


def main():
    parser = argparse.ArgumentParser(description="Two-tier GTA 6 live stream & VOD 1-hour chunk scraper.")
    parser.add_argument("--probe-only", action="store_true", help="Discover, probe, and rank candidates without downloading or locking.")
    parser.add_argument("--dry-run", action="store_true", help="Probe and print download/slice plan without fetching media.")
    parser.add_argument("--no-wait", action="store_true", help="Do not sleep in 60s intervals when live streams are < 45 mins old.")
    parser.add_argument("--stock-target", type=int, default=1, help="Ensure at least N fresh .mp4 files exist in /files/inputs (max 2 new downloads per run).")
    parser.add_argument("--fallback-url", default="", help="Optional streamer channel/VOD URL to probe if primary pool yields no candidate.")
    args = parser.parse_args()

    use_lock = not args.dry_run and not args.probe_only
    if use_lock and not acquire_lock():
        print(json.dumps({"status": "skipped_lock_active", "lock_path": LOCK_PATH}))
        return

    try:
        res = run_scraper(dry_run=args.dry_run, no_wait=args.no_wait, probe_only=args.probe_only)
        # Fallback to Pick Random Streamer URL if primary discovery yielded no candidate
        if (
            not args.dry_run
            and not args.probe_only
            and not res.get("downloaded")
            and args.fallback_url
        ):
            fb_info = probe_url_metadata(args.fallback_url)
            if isinstance(fb_info, dict) and fb_info.get("id"):
                # Temporarily inject candidate through second pass if not already completed
                state = load_json(STATE_PATH, {})
                st = state.get(str(fb_info["id"]), {}) if isinstance(state, dict) else {}
                if not (isinstance(st, dict) and st.get("completed")):
                    extra_res = run_scraper(dry_run=False, no_wait=args.no_wait, probe_only=False)
                    if extra_res.get("downloaded"):
                        res = extra_res

        # Top up fresh stock in /files/inputs up to stock-target (cap at 1 extra download per run)
        if (
            not args.dry_run
            and not args.probe_only
            and args.stock_target > 1
            and _count_fresh_input_chunks() < args.stock_target
        ):
            topup = run_scraper(dry_run=False, no_wait=args.no_wait, probe_only=False)
            if isinstance(res, dict):
                res["stock_topup"] = topup.get("status")
                res["fresh_input_count"] = _count_fresh_input_chunks()

        print(json.dumps(res, indent=2))
    finally:
        if use_lock:
            release_lock()


if __name__ == "__main__":
    main()
