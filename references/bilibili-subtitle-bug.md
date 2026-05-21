# B站 AI 字幕系统问题 (2026-05)

## 现象

B站 `player/v2` API 返回的 AI 字幕 URL，约 60-70% 的视频字幕内容与视频本身不匹配。

### 实测数据 (2026-05-21)

| 类型 | 字幕实际内容 | 端点 | 匹配 |
|------|-------------|------|------|
| 科技发布会 | 与视频标题一致 | wbi | ✅ |
| 工具教程 | 与视频主题一致 | wbi | ✅ |
| 商业思维 | 与视频内容一致 | wbi | ✅ |
| 技术对比 | 首次不匹配→实时cid后修正 | wbi | ✅(修正后) |
| 技术教程 | 返回脱口秀字幕 | wbi | ❌ |
| 学习路线 | 语义相关但不完全匹配 | wbi | ⚠️ |
| 产品对比 | 返回旅游视频字幕/无字幕 | wbi | ❌ |
| 看板教程 | 返回三国演义台词 | wbi | ❌ |

## 根因分析（两个层面）

### 层面1：四元组绑定不正确（可修复）

收藏夹API返回的 `ugc.first_cid` 是**缓存值**，可能与实际播放cid不一致。

**错误做法**：
```
favorites.json → items[].ugc.first_cid → 直接用
```

**正确做法**：
```
bvid → GET /x/web-interface/view → 实时获取 data.pages[0].cid
```

实测案例：某技术视频用 first_cid 拿到无关字幕，用实时 cid 拿到正确字幕。

### 层面2：B站字幕哈希匹配系统bug（不可修复）

即使四元组绑定正确，`/x/player/v2` 仍可能返回错误字幕：
- URL路径是内容哈希（`/bfs/ai_subtitle/prod/{hash}`），不是视频ID
- 相似音频的视频会被错误关联
- `/x/player/wbi/v2` 端点准确率更高（~60% vs ~30%）

## WBI vs 普通端点

| | 普通 `/x/player/v2` | WBI `/x/player/wbi/v2` |
|---|---|---|
| 签名 | 不需要 | 需要 w_rid + wts |
| 字幕准确率 | ~30% | ~60% |
| 返回数据 | 可能被降级 | 更完整 |

WBI 是签名机制（w_rid=MD5签名, wts=时间戳），不是版本升级。
签名流程：`/x/web-interface/nav` 拿 img_key/sub_key → 混淆表 → mixin_key → 参数排序+时间戳 → MD5。

## MCP 工具限制

Hermes 的 MCP `bilibili` 工具（get_subtitles、get_video_info）不使用用户 cookie，因此：
- 看不到需要登录态的 AI 字幕
- 只能获取公开的 CC 字幕和弹幕

**解决方案**: 直接调用 B站 API 并携带用户 cookie。

## 验证方法

**Layer 1 — 关键词校验**：
```python
# 中文标题按2-4字分词，不要整句当一个关键词
# "去年涨粉70万" → ["去年", "涨粉", "70万"]
import re
words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', title)
keywords = [w for w in words if len(w) >= 2]
found = [kw for kw in keywords if kw.lower() in transcript.lower()]
is_valid = len(found) >= 2
```

**Layer 2 — 时长校验**：
```bash
python3 scripts/validate_subtitle_match.py --metadata video.json --subtitle subtitle.json
```

> **盲区**：时长校验只能抓到"长vs短"的明显不匹配，无法抓到同长度区间的错配（如400秒视频拿到420秒的无关字幕）。

## 替代方案 (按优先级)

1. **实时cid + wbi端点 + 双层校验** — 当前最佳方案
2. **Whisper ASR** — 下载音频本地转写，准确但慢（~10x realtime CPU）
3. **视频简介** — 很多 UP 主会写详细简介，可作为信息源
4. **手动标注** — 标记 `no_subtitle`，等待 B站 修复

## 何时可以移除此文档

当 B站 修复了字幕哈希匹配 bug，命中率恢复到 >90% 时，可以移除验证步骤。
测试方法：批量获取10个视频字幕，检查匹配率。
