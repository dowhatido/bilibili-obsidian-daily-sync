#!/usr/bin/env python3
"""Render a Bilibili video into an Obsidian Markdown note."""
import argparse
import json
import os
import re
from pathlib import Path


def read_text(path, default=""):
    if not path:
        return default
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def safe_filename(value):
    value = re.sub(r'[\\/:*?"<>|]+', " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "untitled"


def get_bvid(metadata):
    return metadata.get("bvid") or metadata.get("bv_id") or metadata.get("id") or "unknown-bvid"


def main():
    parser = argparse.ArgumentParser(description="Render a Bilibili Obsidian Markdown note.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--transcript", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--vault", default=os.getenv("OBSIDIAN_VAULT", ""))
    parser.add_argument("--inbox", default=os.getenv("OBSIDIAN_INBOX", "Bilibili Inbox"))
    parser.add_argument("--status", default="summarized")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if not args.vault and not args.output:
        raise SystemExit("Missing --vault/OBSIDIAN_VAULT or --output.")

    with open(args.metadata, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    bvid = get_bvid(metadata)
    title = metadata.get("title") or metadata.get("name") or bvid
    upper = metadata.get("upper", {})
    upper_name = metadata.get("upper_name") or upper.get("name") or metadata.get("uname") or ""
    url = metadata.get("url") or f"https://www.bilibili.com/video/{bvid}"
    favorited_at = metadata.get("favorited_at") or ""
    transcript = read_text(args.transcript, "")
    summary = read_text(args.summary, "待总结。")

    note = f'''---
source: bilibili
bvid: "{bvid}"
url: "{url}"
title: "{title.replace('"', "'")}"
up: "{upper_name.replace('"', "'")}"
favorited_at: "{favorited_at}"
status: "{args.status}"
tags:
  - bilibili
  - llm-wiki
---

# {title}

## 一句话总结

待提炼。

## 核心观点

{summary}

## 结构化笔记

待整理。

## 关键时间戳

待整理。

## 对我的启发

待补充。

## 原始字幕

{transcript}
'''

    if args.output:
        output_path = Path(args.output)
    else:
        date_part = favorited_at[:10] if favorited_at else "undated"
        output_path = Path(args.vault) / args.inbox / f"{date_part} - {safe_filename(title)} - {bvid}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise SystemExit(f"Refusing to overwrite existing note: {output_path}")
    output_path.write_text(note, encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
