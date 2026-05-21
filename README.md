# Bilibili Obsidian Daily Sync

把B站收藏夹视频自动同步为 Obsidian 笔记，用于个人知识库建设。

## 功能

- 按日期拉取B站收藏夹视频
- 自动获取AI字幕（带三层校验防错）
- LLM 生成结构化笔记（一句话总结 / 核心观点 / 启发）
- 写入 Obsidian Vault，支持增量同步

## 字幕获取方案

B站AI字幕系统存在哈希匹配bug（2026-05实测约60-70%不匹配），本skill采用三层瀑布方案：

```
① wbi API + 关键词/时长双层校验
② Whisper ASR 本地转写（faster-whisper, CPU ~10x realtime）
③ 视频简介回退
```

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/bilibili-obsidian-daily-sync.git
cd bilibili-obsidian-daily-sync
```

### 2. 安装依赖

```bash
# 核心依赖（字幕校验 + Obsidian渲染）
pip3 install requests

# Whisper ASR 兜底（可选，推荐）
pip3 install faster-whisper
pip3 install yt-dlp  # brew install yt-dlp
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

### 渲染 Obsidian 笔记

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
│   └── bilibili-subtitle-bug.md       # 字幕bug实测记录
└── templates/
    └── bilibili-note.md               # 笔记模板
```

## 已知问题

- B站AI字幕系统存在哈希匹配bug，约60-70%的视频字幕内容与视频不匹配
- 使用 `/x/player/wbi/v2` 端点比普通端点准确率高约20%
- 关键词校验对中文分词敏感，长句可能误报不匹配
- Whisper 对英文专有名词转写不稳定（OpenClaw→OpenCore）

## License

MIT
