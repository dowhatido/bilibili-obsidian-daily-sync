---
name: bilibili-obsidian-daily-sync
description: Sync Bilibili favorites into Obsidian notes. Triggers: bilibili obsidian sync, b站收藏同步, bilibili字幕, b站视频总结, 收藏夹同步到obsidian. Handles subtitle fetching (with known B站 bug workarounds), Whisper ASR fallback, LLM summarization, and Obsidian note rendering.
---

# Bilibili Obsidian Daily Sync

Sync newly favorited Bilibili videos into Obsidian notes with AI-generated summaries.

## Prerequisites

Create a `.env` file in the working directory:

```dotenv
BILI_COOKIE="SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
BILI_FAV_MEDIA_IDS="YOUR_MEDIA_ID_HERE"
OBSIDIAN_VAULT="/absolute/path/to/Obsidian/Vault"
OBSIDIAN_INBOX="Bilibili Inbox"
BILI_SYNC_TZ="Asia/Shanghai"
```

### Getting BILI_COOKIE

1. Login to bilibili.com
2. F12 → Network → refresh → click any request
3. Find `Cookie:` in Request Headers
4. Need at minimum: `SESSDATA`, `bili_jct`, `DedeUserID`
5. **SESSDATA is HttpOnly** — won't show in Application tab, must get from Network request headers

### Finding Favorite Folder IDs

Call API with user's cookie:
```
curl -H "Cookie: $BILI_COOKIE" "https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid=$DedeUserID"
```
Default favorites folder title is "默认收藏夹".

## Workflow

### Step 1: List Favorites

```bash
cd /path/to/skill && python3 scripts/list_today_favorites.py --date YYYY-MM-DD --output favorites.json
```

### Step 2: Resolve Playback Target

For each unsynced video, resolve the exact playback target **in real-time** before fetching subtitles:

1. **实时获取 cid**（不要用收藏夹缓存的 first_cid）：
   ```bash
   GET /x/web-interface/view?bvid={bvid}
   → data.pages[0].cid    # 单P视频
   → data.pages[N].cid    # 多P视频，N=目标页码
   → data.duration         # 视频时长（秒）
   ```
2. 对于多-part 视频，**never assume the first `cid`**；use the target page from the video URL or user selection.
3. Cache subtitles by `bvid + cid + lang + subtitle_url`, not by title or `bvid` alone.

> **Pitfall (2026-05 实测)**：收藏夹API返回的 `ugc.first_cid` 可能是缓存值，与实际播放cid不一致，导致字幕关联错误。必须从 view 接口实时获取 cid。

### Step 3: Get AI Subtitles (with cookie)

The MCP `bilibili` tools do NOT use user cookies and cannot see AI-generated subtitles. Must call the API directly:

```python
# Get subtitle list (requires cookie for AI subtitles)
# IMPORTANT: use /x/player/wbi/v2, NOT /x/player/v2
# wbi endpoint returns more accurate subtitle associations
url = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}"
# Headers: Cookie + Referer + User-Agent
# Response: data.subtitle.subtitles[].subtitle_url
# Download: https:{subtitle_url} (no cookie needed for download)
```

Use `scripts/fetch_and_validate_subtitles.py` for batch fetching with built-in keyword validation.

### Step 4: Validate Subtitles (CRITICAL — two-layer check)

**B站 AI 字幕系统有严重bug** (as of 2026-05): `player/v2` API returns subtitle URLs where content does NOT match the video ~60-70% of the time. The subtitle hash-based matching system returns wrong files.

**Layer 1 — 关键词校验** (content match):
```python
# After downloading subtitle, check keywords
# IMPORTANT: split Chinese phrases into individual words, not whole phrases
# "去年涨粉70万" → ["去年", "涨粉", "70万"] — NOT ["去年涨粉70万"] as one keyword
keywords_from_title = extract_keywords(video_title)  # split into 2-4 char words
found = [kw for kw in keywords_from_title if kw.lower() in transcript.lower()]
is_valid = len(found) >= 2  # at least 2 title keywords in transcript
```
> **Pitfall (2026-05)**：中文标题的长短语（如"去年涨粉"、"涨粉就是不务正业"）如果当一个关键词，字幕里拆成"涨了大概70万的粉丝"+"不务正业"就匹配不上。必须按2-4字分词。

**Layer 2 — 时长校验** (duration match):
```bash
python3 scripts/validate_subtitle_match.py \
  --metadata video.json \
  --subtitle subtitle.json \
  --tolerance 8.0 \
  --min-ratio 0.25
```
- `mismatch`: subtitle end exceeds video duration + tolerance → reject
- `suspicious`: subtitle end < 25% of video duration → flag for review
- `ok`: duration plausible

If either layer fails:
1. **Whisper ASR fallback** (recommended):
   ```bash
   python3 scripts/whisper_transcribe.py <BV_ID> \
     --title "视频标题" \
     --model base \
     --proxy http://127.0.0.1:7897
   ```
   - Uses `faster-whisper` (CPU, ~10x realtime, base model)
   - Downloads audio via yt-dlp, transcribes locally
   - Built-in fuzzy keyword matching (tolerates Whisper's English name transcription errors)
   - Output: `{bvid}_transcript.txt` + `{bvid}_timestamped.txt`
2. Fall back to video description/intro if Whisper also fails or is too slow
3. Flag for manual review if all methods fail

> **Pitfall — 时长校验的盲区 (2026-05 实测)**
> B站字幕哈希bug会导致"时长相近但内容完全不同"的视频互相拿到对方的字幕。
> 例如：400秒的对比视频拿到了420秒的无关字幕，时长校验通过但内容完全错误。
> 时长校验只能抓到"长视频字幕 vs 短视频"或反过来的明显不匹配，无法抓到同长度区间的错配。
> 当前方案的局限：关键词校验可以补充但用户认为过度工程化，暂不采用。
> 实际兜底：简介质量足够时直接用简介生成笔记，不依赖字幕。

### Step 5: Summarize

Use LLM to generate from transcript (or intro if subtitle failed):
- One-sentence summary
- 3-5 core points (bullet list)
- Structured notes by topic
- Timestamped highlights (if SRT available)
- AIPM/personal insights section

### Step 6: Render Obsidian Note

```bash
python3 scripts/render_obsidian_note.py \
  --metadata video.json \
  --transcript transcript.txt \
  --summary summary.md \
  --vault "$OBSIDIAN_VAULT" \
  --inbox "${OBSIDIAN_INBOX:-Bilibili Inbox}"
```

Or write directly. Note path: `<vault>/<inbox>/<YYYY-MM-DD> - <safe_title> - <BVID>.md`

> **Best practice (Codex 2026-05)**：输出目录和文件名带 `bvid+cid`（如 `BV1xxx-38474483986`），防止缓存按bvid alone复用导致串字幕。

### Step 7: Sync State

Never overwrite notes with user edits. Track synced BVIDs to avoid re-processing.

## Safety Rules

- Treat `BILI_COOKIE`, `SESSDATA`, `bili_jct` as secrets — never write to notes
- No aggressive scraping, proxy rotation, or CAPTCHA bypass
- B站 risk_control errors → stop and report, don't retry aggressively
- If subtitles appear mismatched, do not summarize. Re-resolve `cid` and fetch again.
- Keep sync low frequency and incremental

## Output Report

After sync, report:
- Folders scanned / videos found / notes created-skipped-failed
- Failed BVIDs with reasons
- Subtitle validation results (how many matched vs mismatched)
- Videos needing ASR or manual handling

## Known Issues

See `references/bilibili-subtitle-bug.md` for details on the B站 AI subtitle mismatch bug and workarounds.

## Related Skills

- `bilibili-subtitle-downloader` — Standalone skill for single-video subtitle download + chunking. Uses `bilibili-api-python` library with QR code login. Good for one-off video transcription when you don't have a cookie file.
