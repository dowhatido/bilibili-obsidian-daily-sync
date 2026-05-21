#!/usr/bin/env python3
"""Fetch Bilibili favorite items for a target date. Requires BILI_COOKIE env var."""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

API_URL = "https://api.bilibili.com/x/v3/fav/resource/list"


def load_dotenv(path):
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def request_json(url, cookie):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 BilibiliObsidianDailySync/0.1",
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def to_local_datetime(timestamp, tz):
    return dt.datetime.fromtimestamp(int(timestamp), tz=tz)


def fetch_folder(media_id, cookie, target_date, tz, max_pages, page_size, sleep_seconds):
    results = []
    for page in range(1, max_pages + 1):
        query = urllib.parse.urlencode({
            "media_id": media_id, "pn": page, "ps": page_size,
            "keyword": "", "order": "mtime", "type": 0, "tid": 0, "platform": "web",
        })
        payload = request_json(f"{API_URL}?{query}", cookie)
        if payload.get("code") != 0:
            raise RuntimeError(f"folder {media_id} API error: {payload.get('code')} {payload.get('message')}")
        medias = payload.get("data", {}).get("medias") or []
        if not medias:
            break
        stop_folder = False
        for item in medias:
            fav_ts = item.get("fav_time") or item.get("mtime") or item.get("pubtime")
            if not fav_ts:
                continue
            fav_dt = to_local_datetime(fav_ts, tz)
            fav_date = fav_dt.date()
            if fav_date == target_date:
                copied = dict(item)
                copied["favorite_media_id"] = media_id
                copied["favorited_at"] = fav_dt.isoformat()
                results.append(copied)
            elif fav_date < target_date:
                stop_folder = True
        if stop_folder:
            break
        time.sleep(sleep_seconds)
    return results


def main():
    parser = argparse.ArgumentParser(description="List Bilibili favorites saved on a target date.")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--media-ids", default=os.getenv("BILI_FAV_MEDIA_IDS", ""))
    parser.add_argument("--date", default=os.getenv("BILI_SYNC_DATE", ""))
    parser.add_argument("--tz", default=os.getenv("BILI_SYNC_TZ", "Asia/Shanghai"))
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    load_dotenv(args.env)
    cookie = os.getenv("BILI_COOKIE", "")
    media_ids_raw = args.media_ids or os.getenv("BILI_FAV_MEDIA_IDS", "")
    if not cookie:
        raise SystemExit("Missing BILI_COOKIE. Put it in .env or environment variables.")
    if not media_ids_raw:
        raise SystemExit("Missing BILI_FAV_MEDIA_IDS or --media-ids.")

    tz = ZoneInfo(args.tz)
    target_date = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(tz).date()
    media_ids = [part.strip() for part in media_ids_raw.split(",") if part.strip()]

    all_items = []
    errors = []
    for media_id in media_ids:
        try:
            all_items.extend(fetch_folder(media_id, cookie, target_date, tz, args.max_pages, args.page_size, args.sleep))
        except Exception as exc:
            errors.append({"media_id": media_id, "error": str(exc)})

    output = {
        "target_date": target_date.isoformat(), "timezone": args.tz,
        "folders_scanned": media_ids, "count": len(all_items),
        "items": all_items, "errors": errors,
    }
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
