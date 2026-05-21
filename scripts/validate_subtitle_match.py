#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def load_metadata(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_time(value):
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    return float(value)


def subtitle_end_from_srt_or_vtt(text):
    ends = []
    pattern = re.compile(r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})")
    for match in pattern.finditer(text):
        ends.append(parse_time(match.group(2)))
    return max(ends) if ends else None


def subtitle_end_from_json(text):
    data = json.loads(text)
    body = data.get("body") if isinstance(data, dict) else data
    ends = []
    if isinstance(body, list):
        for item in body:
            if not isinstance(item, dict):
                continue
            if "to" in item:
                ends.append(float(item["to"]))
            elif "from" in item and "duration" in item:
                ends.append(float(item["from"]) + float(item["duration"]))
    return max(ends) if ends else None


def get_duration(metadata):
    for key in ("duration", "video_duration", "length"):
        value = metadata.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
            return parse_time(value)
    return None


def main():
    parser = argparse.ArgumentParser(description="Validate that a subtitle file plausibly matches video duration.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--tolerance", type=float, default=8.0)
    parser.add_argument("--min-ratio", type=float, default=0.25)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    duration = get_duration(metadata)
    if not duration:
        raise SystemExit("metadata_missing_duration")

    text = Path(args.subtitle).read_text(encoding="utf-8")
    subtitle_end = None
    try:
        subtitle_end = subtitle_end_from_json(text)
    except Exception:
        subtitle_end = subtitle_end_from_srt_or_vtt(text)

    if subtitle_end is None:
        raise SystemExit("subtitle_missing_timestamps")

    status = "ok"
    reason = ""
    if subtitle_end > duration + args.tolerance:
        status = "mismatch"
        reason = "subtitle_end_exceeds_video_duration"
    elif subtitle_end < duration * args.min_ratio:
        status = "suspicious"
        reason = "subtitle_too_short_for_video_duration"

    result = {
        "status": status,
        "reason": reason,
        "duration": duration,
        "subtitle_end": subtitle_end,
        "bvid": metadata.get("bvid"),
        "cid": metadata.get("cid"),
        "page": metadata.get("page"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.as_json else f"{status}: {reason or 'duration_match'}")
    if status == "mismatch":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
