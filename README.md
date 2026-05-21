# Bilibili Obsidian Daily Sync

将 B 站收藏夹自动同步为 Obsidian 知识库笔记。

按日期读取 B 站收藏夹，解析视频的真实 `bvid + cid`，获取 B 站 AI/CC 字幕；当字幕缺失或疑似错配时，回退到 Whisper ASR 转写。最终生成适合 Obsidian / LLM Wiki 使用的结构化 Markdown 笔记。

适合用于：
- 定期整理 B 站收藏夹
- 把视频内容沉淀到个人知识库
- 为 AIPM、研究、学习类视频生成可检索笔记
- 避免"收藏夹吃灰"

## 功能

- **按日期拉取收藏夹** — 自动过滤指定日期的新增收藏
- **真实 cid 解析** — 从 view 接口实时获取 cid，避免缓存导致的字幕错配
- **三层字幕获取** — wbi API → Whisper ASR → 视频简介，逐级回退
- **双层校验** — 关键词匹配 + 时长校验，筛除错配字幕
- **结构化笔记** — 一句话总结 / 核心观点 / 时间戳 / 个人启发
- **增量同步** — 不覆盖用户已编辑的笔记

## 字幕获取方案

B 站部分视频的 AI 字幕存在字幕轨与实际视频不匹配的情况，尤其在使用缓存 cid、旧播放器接口或多分 P 视频时更明显。本 skill 采用三层瀑布方案：

```
① wbi API + 关键词/时长双层校验（首选）
② Whisper ASR 本地转写（faster-whisper, CPU ~10x realtime）
③ 视频简介回退
```

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/dowhatido/bilibili-obsidian-daily-sync.git
cd bilibili-obsidian-daily-sync
```

### 2. 安装依赖

```bash
# 核心依赖
pip3 install requests

# Whisper ASR 兜底（可选，推荐）
pip3 install faster-whisper
pip3 install yt-dlp  # 或 brew install yt-dlp
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的信息
```

**获取 BILI_COOKIE**：

1. 登录 bilibili.com
2. F12 → Network → 刷新页面 → 点击任意请求
3. 找 Request Headers 里的 `Cookie:` 行
4. 提取 `SESSDATA`、`bili_jct`、`DedeUserID` 三个值
5. SESSDATA 是 HttpOnly，**只能从 Network 面板获取**，Application 面板看不到

**获取收藏夹 ID**：

```bash
# 用你的 cookie 调 API
curl -H "Cookie: SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx" \
  "https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid=你的DedeUserID"
# 返回的 list[].id 就是 media_id，默认收藏夹 title = "默认收藏夹"
```

或直接打开B站收藏夹页面，URL 中的 `media_id=` 后面的数字。

## 使用

### 同步今日收藏

```bash
python3 scripts/list_today_favorites.py --output favorites.json
```

### 同步指定日期

```bash
python3 scripts/list_today_favorites.py --date 2026-05-20 --output favorites.json
```

### 单个视频字幕下载 + 校验

```bash
python3 scripts/fetch_and_validate_subtitles.py --favorites favorites.json --output-dir ./subtitles
```

### Whisper ASR 转写

```bash
python3 scripts/whisper_transcribe.py BV1xxxxx --title "视频标题" --model base
```

### 时长校验

```bash
python3 scripts/validate_subtitle_match.py --metadata video.json --subtitle subtitle.json
```

### 生成笔记

当前版本的 LLM 总结由 Agent 完成：脚本负责获取字幕 + 校验 + 渲染模板，summary 内容由 Agent（如 Codex、Claude、ChatGPT 等）基于 transcript 生成。后续可接 OpenAI-compatible API 实现全自动化。

```bash
python3 scripts/render_obsidian_note.py \
  --metadata video.json \
  --transcript transcript.txt \
  --summary summary.md \
  --vault "/path/to/ObsidianVault" \
  --inbox "Bilibili Inbox"
```

## 输出格式

笔记路径：`<vault>/<inbox>/<YYYY-MM-DD> - <标题> - <BVID>.md`

```markdown
---
source: bilibili
bvid: "BV1xxxxx"
url: "https://www.bilibili.com/video/BV1xxxxx"
title: "视频标题"
up: "UP主名"
favorited_at: "2026-05-21T23:06:49+08:00"
status: "summarized"
tags:
  - bilibili
  - llm-wiki
---

# 视频标题

## 一句话总结
...
## 核心观点
...
## 结构化笔记
...
## 关键时间戳
...
## 对我的启发
...
## 原始字幕
...
```

## 目录结构

```
├── SKILL.md                           # 工作流定义
├── .env.example                       # 环境变量模板
├── scripts/
│   ├── list_today_favorites.py        # 拉取收藏夹
│   ├── fetch_and_validate_subtitles.py # 批量字幕+关键词校验
│   ├── validate_subtitle_match.py     # 时长校验
│   ├── whisper_transcribe.py          # Whisper ASR 兜底
│   └── render_obsidian_note.py        # 渲染 Obsidian 笔记
├── references/
│   ├── bilibili-api-reference.md      # B站 API 速查
│   └── bilibili-subtitle-bug.md       # 字幕错配问题记录
└── templates/
    └── bilibili-note.md               # 笔记模板
```

## 已知限制

- 部分视频的 AI 字幕轨与视频内容不匹配，需要依赖校验 + 回退机制
- Whisper 对英文专有名词转写不稳定（如 OpenClaw 可能被转写为 OpenCore）
- 关键词校验对中文长句分词敏感，可能误报不匹配
- LLM 总结当前需 Agent 介入，非全自动

## License

MIT
