#!/usr/bin/env python3
"""Download Bilibili video audio and transcribe with faster-whisper."""
import argparse
import json
import os
import re
import subprocess
import sys
import time


def download_audio(bvid, output_dir, proxy=""):
    """Download audio from Bilibili using yt-dlp."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{bvid}.mp3")
    if os.path.exists(output_path):
        return output_path

    cmd = [
        "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "-o", output_path,
        f"https://www.bilibili.com/video/{bvid}",
    ]
    if proxy:
        cmd.insert(1, "--proxy")
        cmd.insert(2, proxy)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[-200:]}")
    return output_path


def transcribe(audio_path, model_size="base", language="zh"):
    """Transcribe audio with faster-whisper. Returns (segments_list, info)."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    start = time.time()
    segments, info = model.transcribe(audio_path, language=language, beam_size=5)

    result = []
    full_text = ""
    for seg in segments:
        result.append({
            "start": round(seg.start, 1),
            "end": round(seg.end, 1),
            "text": seg.text.strip(),
        })
        full_text += seg.text

    elapsed = time.time() - start
    return result, full_text, elapsed, info.language, info.language_probability


def fuzzy_keyword_match(title, transcript, min_matches=2):
    """Keyword match with fuzzy tolerance for Whisper transcription errors.

    Chinese: split long phrases into 2-3 char sliding window words.
    English: prefix match for Whisper's phonetic errors (OpenClaw→OpenCore).
    """
    raw_words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', title)
    keywords = []
    for w in raw_words:
        if re.match(r'[a-zA-Z]+', w):
            keywords.append(w)
        elif len(w) <= 4:
            keywords.append(w)
        else:
            # Split long Chinese phrase into 2-char sliding window
            for i in range(len(w) - 1):
                chunk = w[i:i+2]
                if len(chunk) >= 2:
                    keywords.append(chunk)
    keywords = list(set(keywords))

    transcript_lower = transcript.lower()
    found = []
    seen = set()
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in transcript_lower and kw not in seen:
            found.append(kw)
            seen.add(kw)
            continue
        # Fuzzy: for English words, check if first 4+ chars match
        if re.match(r'[a-zA-Z]+', kw) and len(kw) >= 4:
            prefix = kw_lower[:4]
            if prefix in transcript_lower and kw not in seen:
                found.append(f"{kw}~")
                seen.add(kw)
    return len(found) >= min_matches, found


def main():
    parser = argparse.ArgumentParser(description="Transcribe Bilibili video with Whisper.")
    parser.add_argument("bvid", help="Bilibili BV ID")
    parser.add_argument("--output-dir", default="/tmp/bili_whisper")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"])
    parser.add_argument("--language", default="zh")
    parser.add_argument("--proxy", default=os.getenv("BILI_PROXY", ""))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--title", default="", help="Video title for keyword validation")
    args = parser.parse_args()

    # Download
    print(f"[*] Downloading audio: {args.bvid}", file=sys.stderr)
    audio_path = download_audio(args.bvid, args.output_dir, args.proxy)

    # Transcribe
    print(f"[*] Transcribing with model={args.model}...", file=sys.stderr)
    segments, full_text, elapsed, lang, confidence = transcribe(
        audio_path, model_size=args.model, language=args.language
    )

    # Save transcript
    transcript_path = os.path.join(args.output_dir, f"{args.bvid}_transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Save timestamped
    timestamped_path = os.path.join(args.output_dir, f"{args.bvid}_timestamped.txt")
    with open(timestamped_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"[{seg['start']:.0f}s] {seg['text']}\n")

    # Validate
    is_valid, matched = True, []
    if args.title:
        is_valid, matched = fuzzy_keyword_match(args.title, full_text)

    result = {
        "bvid": args.bvid,
        "transcript_path": transcript_path,
        "timestamped_path": timestamped_path,
        "chars": len(full_text),
        "segments": len(segments),
        "elapsed_s": round(elapsed, 1),
        "language": lang,
        "confidence": round(confidence, 3),
        "keyword_valid": is_valid,
        "keyword_matched": matched,
    }

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ {args.bvid} | {len(full_text)}字 | {len(segments)}段 | {elapsed:.1f}s | {lang}")
        if args.title:
            print(f"   关键词: {matched} | {'✅ 通过' if is_valid else '❌ 不匹配'}")
        print(f"   字幕: {transcript_path}")
        print(f"   时间戳: {timestamped_path}")


if __name__ == "__main__":
    main()
