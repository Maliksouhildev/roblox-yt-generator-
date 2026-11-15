#!/usr/bin/env python3
"""
twitch_chat_fetcher.py
----------------------
Zero-dependency, bulletproof Twitch VOD chat fetcher.
Uses Twitch's public GraphQL endpoint (gql.twitch.tv) with explicit typed GraphQL schema
(bypassing rotated persisted query hashes).
Outputs normalized JSON compatible with chat_analyzer.py.
"""

import sys
import os
import json
import re
import time
import urllib.request
import urllib.error

TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
GQL_URL = "https://gql.twitch.tv/gql"

COMMENTS_GQL_QUERY = """
query VideoCommentsByOffsetOrCursor($videoID: ID!, $cursor: Cursor, $contentOffsetSeconds: Int) {
  video(id: $videoID) {
    id
    comments(after: $cursor, contentOffsetSeconds: $contentOffsetSeconds) {
      edges {
        cursor
        node {
          id
          commenter {
            displayName
          }
          contentOffsetSeconds
          createdAt
          message {
            fragments {
              text
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
      }
    }
  }
}
"""


def extract_vod_id(url_or_id: str) -> str:
    m = re.search(r'(?:videos/|v=)?(\d{8,12})', str(url_or_id))
    if m:
        return m.group(1)
    return str(url_or_id).strip()


def fetch_twitch_vod_chat(vod_id: str, output_path: str = None, max_messages: int = 150000):
    vod_id = extract_vod_id(vod_id)
    if not vod_id.isdigit():
        raise ValueError(f"Invalid Twitch VOD ID: {vod_id}")

    if not output_path:
        output_path = f"/files/inputs/twitch_{vod_id}.chat.json"

    print(f"[Twitch Chat Fetcher] Fetching chat for Twitch VOD: {vod_id}...")

    comments = []
    cursor = None
    has_next = True
    page = 0
    retries = 0

    while has_next and len(comments) < max_messages:
        page += 1
        variables = {
            "videoID": vod_id
        }
        if cursor:
            variables["cursor"] = cursor
        else:
            variables["contentOffsetSeconds"] = 0

        payload = [{
            "operationName": "VideoCommentsByOffsetOrCursor",
            "query": COMMENTS_GQL_QUERY,
            "variables": variables
        }]

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            GQL_URL,
            data=data,
            headers={
                "Client-Id": TWITCH_CLIENT_ID,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )

        res_json = None
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
            retries = 0
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = min(30, 2 ** (retries + 1))
                print(f"[Twitch Chat Fetcher] Rate limited (429). Backing off for {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                retries += 1
                if retries <= 3:
                    continue
            print(f"[Twitch Chat Fetcher] HTTP error on page {page}: {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"[Twitch Chat Fetcher] Network error on page {page}: {e}", file=sys.stderr)
            retries += 1
            if retries <= 3:
                time.sleep(2)
                continue
            break

        if not res_json or not isinstance(res_json, list) or "data" not in res_json[0]:
            print(f"[Twitch Chat Fetcher] Unexpected response on page {page}: {res_json}", file=sys.stderr)
            break

        video_data = res_json[0]["data"].get("video")
        if not video_data or "comments" not in video_data:
            print(f"[Twitch Chat Fetcher] No video or comments data for VOD {vod_id} (may be sub-only or deleted).", file=sys.stderr)
            break

        comments_data = video_data["comments"]
        edges = comments_data.get("edges") or []
        if not edges:
            break

        for edge in edges:
            node = edge.get("node")
            if not node:
                continue

            commenter = node.get("commenter") or {}
            msg_obj = node.get("message") or {}
            fragments = msg_obj.get("fragments") or []
            msg_text = "".join([f.get("text", "") for f in fragments if "text" in f])
            if not msg_text:
                msg_text = msg_obj.get("body", "")

            comments.append({
                "content_offset_seconds": float(node.get("contentOffsetSeconds", 0.0)),
                "created_at": node.get("createdAt", ""),
                "commenter": {
                    "display_name": commenter.get("displayName", "anonymous")
                },
                "message": {
                    "body": msg_text,
                    "bits_spent": 0
                }
            })

        page_info = comments_data.get("pageInfo") or {}
        has_next = page_info.get("hasNextPage", False)
        if edges:
            cursor = edges[-1].get("cursor")

        if page % 10 == 0:
            print(f"[Twitch Chat Fetcher] Page {page}: Fetched {len(comments)} comments so far (Offset: {comments[-1]['content_offset_seconds']}s)...")

        time.sleep(0.04)  # Politeness delay

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    out_doc = {
        "platform": "twitch",
        "vod_id": vod_id,
        "total_comments": len(comments),
        "comments": comments
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out_doc, f, indent=2)

    print(f"[Twitch Chat Fetcher] Successfully saved {len(comments)} comments to {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 twitch_chat_fetcher.py <vod_url_or_id> [output.chat.json]")
        sys.exit(1)

    v_id = sys.argv[1]
    o_path = sys.argv[2] if len(sys.argv) > 2 else None
    fetch_twitch_vod_chat(v_id, o_path)
