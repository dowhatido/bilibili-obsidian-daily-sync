# B站 API 速查

## WBI 签名机制

WBI 端点 = 需要签名参数的 API 接口（路径带 `/wbi/`，要求 `w_rid` + `wts`）。
普通端点 = 不需要签名，最多只需要 Cookie/Referer/User-Agent。

### 端点分类

| 类型 | Cookie | WBI签名 | 用途 |
|------|--------|---------|------|
| 普通端点 | 看接口 | 不需要 | 基础信息、公开视频数据 |
| Cookie端点 | 要 | 不一定 | 收藏夹、登录用户信息 |
| WBI端点 | 不一定 | 要 w_rid+wts | Web端风控后的查询接口 |
| Cookie+WBI | 要 | 要 | 最像真实网页访问 |

### WBI 签名流程

1. `GET /x/web-interface/nav` → 获取 `img_key` + `sub_key`
2. 用固定混淆表生成 `mixin_key`
3. 请求参数排序 + 时间戳 → MD5 → 得到 `w_rid`

缺少或签错不会报错，而是返回空数据/风控信息/v_voucher。

参考：[BAC Document - WBI 签名](https://github.com/SocialSisterYi/bilibili-API-collect)

## 与字幕同步相关的端点

| 端点 | 作用 | 类型 |
|------|------|------|
| `/x/web-interface/nav` | 登录状态、WBI key | 普通（用于生成签名） |
| `/x/v3/fav/resource/list` | 收藏夹视频列表 | Cookie |
| `/x/v3/fav/folder/created/list-all` | 收藏夹列表 | Cookie |
| `/x/web-interface/view` | 视频元数据、分P、cid | 普通/可能风控 |
| `/x/player/wbi/v2` | 播放器信息、字幕列表、AI字幕 | **Cookie+WBI** |
| `/x/player/v2` | 老版播放器信息/字幕 | 普通（稳定性差） |
| `/x/player/pagelist` | 分P列表 | 普通 |
| 字幕JSON URL | 下载字幕内容 | 无需签名（auth_key内含鉴权） |

## 字幕获取关键

**字幕不匹配的根因**：不是 WBI 本身，而是没有用正确的四元组去请求。

必须保证 `bvid + cid + page + duration` 绑定正确：
- `bvid` — 视频ID
- `cid` — 分P的cid（多P视频不能用 first_cid）
- `page` — 分P页码
- `duration` — 用于校验字幕时长是否合理

## 收藏夹列表

```
GET /x/v3/fav/folder/created/list-all?up_mid={DedeUserID}
Headers: Cookie, Referer, User-Agent
Response: data.list[].{id, fid, title, media_count}
```

- `id` 就是 `media_id`，用于收藏夹内容查询
- 默认收藏夹 title = "默认收藏夹"

## 收藏夹内容

```
GET /x/v3/fav/resource/list?media_id={id}&pn={page}&ps={size}&order=mtime
Headers: Cookie, Referer, User-Agent
Response: data.medias[].{bvid, title, upper, fav_time, ugc.first_cid}
```

- `order=mtime` 按收藏时间排序（最新在前）
- `ugc.first_cid` 是单P视频的cid

## 播放器信息 + 字幕

```
GET /x/player/wbi/v2?bvid={bvid}&cid={cid}
Headers: Cookie, Referer, User-Agent（+ WBI签名参数）
Response: data.subtitle.subtitles[].{lan, lan_doc, subtitle_url}
```

- **推荐用 wbi 版本**，字幕关联更准确
- **需要 Cookie 才能看到 AI 字幕**
- `lan="ai-zh"` 是中文AI字幕
- `subtitle_url` 以 `//` 开头，需要加 `https:` 前缀

## 字幕下载

```
GET https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/{hash}?auth_key=...
Response: {body: [{from, to, content, sid}]}
```

- **不需要 Cookie**（auth_key 已内含鉴权）
- `body[].from` 是开始时间（秒）
- `body[].content` 是字幕文本

## 频率控制

- 建议每次请求间隔 0.5-1 秒
- 收藏夹翻页间隔 1 秒
- B站风控会返回非0 code，此时应停止

## 已知问题 (2026-05)

B站 AI 字幕系统有哈希匹配 bug，约 60-70% 的视频字幕内容与视频不匹配。
详见 `references/bilibili-subtitle-bug.md`。

**改善方案**：使用 `/x/player/wbi/v2` 端点 + 四元组校验 + 关键词/时长双层验证 + Whisper ASR 兜底。
