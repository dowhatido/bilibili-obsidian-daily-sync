#!/usr/bin/env python3
"""Fetch AI subtitles for Bilibili videos using user cookie. Validates content matches video title."""
import argparse
import json
import os
import re
import sys
import time
import urllib.request


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


def get_subtitle_url(bvid, cid, cookie):
    """Get AI subtitle URL from player/v2 API (requires cookie)."""
    url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
    req = urllib.request.Request(url, headers={
        "Cookie": cookie, "User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    subs = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    for s in subs:
        if s.get("lan") == "ai-zh":
            sub_url = s["subtitle_url"]
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url
            return sub_url
    # fallback to first subtitle
    if subs:
        sub_url = subs[0]["subtitle_url"]
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        return sub_url
    return None


def download_subtitle(sub_url):
    """Download subtitle JSON from URL (no cookie needed)."""
    req = urllib.request.Request(sub_url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def validate_subtitle(title, transcript):
    """Check if subtitle content matches video title. Returns (is_valid, matched_keywords)."""
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', title)
    keywords = [w for w in words if len(w) >= 2]
    found = [kw for kw in keywords if kw.lower() in transcript.lower()]
    return len(found) >= 2, found


def main():
    parser = argparse.ArgumentParser(description="Fetch and validate Bilibili AI subtitles.")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--favorites", required=True, help="favorites.json from list_today_favorites.py")
    parser.add_argument("--output-dir", default="/tmp/bili_sync/subtitles")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't download")
    args = parser.parse_args()

    load_dotenv(args.env)
    cookie = os.getenv("BILI_COOKIE", "")
    if not cookie:
        raise SystemExit("Missing BILI_COOKIE")

    with open(args.favorites, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    results = []
    for item in data["items"]:
        bvid = item["bvid"]
        cid = item["ugc"]["first_cid"]
        title = item["title"]

        try:
            sub_url = get_subtitle_url(bvid, cid, cookie)
            if not sub_url:
                results.append({"bvid": bvid, "title": title, "status": "no_subtitle"})
                print(f"❌ {bvid} | 无字幕 | {title[:50]}")
                continue

            sub_data = download_subtitle(sub_url)
            body = sub_data.get("body", [])
            transcript = " ".join(e["content"] for e in body)
            is_valid, matched = validate_subtitle(title, transcript)

            if is_valid:
                # Save transcript
                with open(os.path.join(args.output_dir, f"{bvid}_transcript.txt"), "w") as f:
                    f.write(transcript)
                timestamped = "\n".join(f"[{e['from']:.0f}s] {e['content']}" for e in body)
                with open(os.path.join(args.output_dir, f"{bvid}_timestamped.txt"), "w") as f:
                    f.write(timestamped)
                results.append({"bvid": bvid, "title": title, "status": "valid", "chars": len(transcript), "keywords": matched})
                print(f"✅ {bvid} | {len(body)}条 | {len(transcript)}字 | 关键词: {matched} | {title[:50]}")
            else:
                results.append({"bvid": bvid, "title": title, "status": "mismatch", "keywords": matched, "preview": transcript[:100]})
                print(f"⚠️ {bvid} | 字幕不匹配 | 匹配词: {matched} | {title[:50]}")

        except Exception as e:
            results.append({"bvid": bvid, "title": title, "status": "error", "error": str(e)})
            print(f"💥 {bvid} | 错误: {e} | {title[:50]}")

        time.sleep(0.5)

    # Summary
    valid = sum(1 for r in results if r["status"] == "valid")
    mismatch = sum(1 for r in results if r["status"] == "mismatch")
    no_sub = sum(1 for r in results if r["status"] == "no_subtitle")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"\n总结: ✅{valid} ⚠️{mismatch} ❌{no_sub} 💥{errors} / {len(results)}")

    out_path = os.path.join(args.output_dir, "validation_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果保存: {out_path}")


if __name__ == "__main__":
    main()
