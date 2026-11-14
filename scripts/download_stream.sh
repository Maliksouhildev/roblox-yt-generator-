#!/bin/sh
TARGET_URL="$1"
MAX_STREAMS="${2:-2}"
COUNT_FILE="/files/temp/download_count.txt"

if [ -f "$COUNT_FILE" ]; then
  COUNT=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
else
  COUNT=0
fi

case "$COUNT" in
  ''|*[!0-9]*) COUNT=0 ;;
esac

if [ "$COUNT" -ge "$MAX_STREAMS" ]; then
  echo "[LIMIT REACHED] $COUNT/$MAX_STREAMS streams already downloaded in this execution. Skipping: $TARGET_URL"
  exit 0
fi

echo "[CHECKING] ($COUNT/$MAX_STREAMS downloaded) $TARGET_URL"

BEFORE_LINES=$(wc -l < /files/downloaded.txt 2>/dev/null || echo 0)

# Domain Branching: Explicit Twitch vs YouTube Ingestion
case "$TARGET_URL" in
  *twitch.tv*)
    echo "[INGESTION] Detected Twitch stream URL. Fetching Twitch chat via GraphQL..."
    python3 /files/twitch_chat_fetcher.py "$TARGET_URL" || true
    /files/yt-dlp \
      --download-archive "/files/downloaded.txt" \
      -i \
      --windows-filenames \
      --write-info-json \
      --no-write-playlist-meta \
      --socket-timeout 20 \
      --retries 2 \
      -f "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b" \
      -S "res:1080,fps" \
      --merge-output-format mp4 \
      --playlist-items 1 \
      --match-filter "duration >= 1500 & duration <= 14400 & aspect_ratio >= 1" \
      -o "/files/inputs/%(uploader)s___%(title)s.%(ext)s" \
      "$TARGET_URL" || true
    ;;
  *)
    echo "[INGESTION] Detected YouTube stream URL. Fetching video & live_chat.json..."
    /files/yt-dlp \
      --download-archive "/files/downloaded.txt" \
      -i \
      --windows-filenames \
      --write-info-json \
      --write-subs \
      --sub-langs "live_chat" \
      --no-write-playlist-meta \
      --socket-timeout 20 \
      --retries 2 \
      -f "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b" \
      -S "res:1080,fps" \
      --merge-output-format mp4 \
      --playlist-items 1 \
      --match-filter "was_live & duration >= 1500 & duration <= 14400 & aspect_ratio >= 1" \
      -o "/files/inputs/%(uploader)s___%(title)s.%(ext)s" \
      "$TARGET_URL" || true
    ;;
esac

AFTER_LINES=$(wc -l < /files/downloaded.txt 2>/dev/null || echo 0)

if [ "$AFTER_LINES" -gt "$BEFORE_LINES" ]; then
  NEW_DL=$((AFTER_LINES - BEFORE_LINES))
  COUNT=$((COUNT + NEW_DL))
  echo "$COUNT" > "$COUNT_FILE"
  echo "[DOWNLOAD SUCCESS] Added $NEW_DL stream(s). Execution total: $COUNT/$MAX_STREAMS"
else
  echo "[NO NEW STREAM] No new livestream for $TARGET_URL. Execution total: $COUNT/$MAX_STREAMS"
fi
