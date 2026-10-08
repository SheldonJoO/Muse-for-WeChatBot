---
name: "muse_for_wechat_bot"
description: "把 Muse 接到用户微信：官方 CLI 扫码绑定 + 自研转发程序经腾讯 iLink 接口收发消息，hook 唤醒 Muse 回复。用于微信直连 Muse、微信消息桥接。"
---

# Muse for WeChat-Bot

## Purpose
通过腾讯 iLink 接口把 Muse 接到用户微信：在云端跑转发程序长轮询收消息，Muse 回复后发回微信，主聊天同步一份。全程只认绑定的一个人，回复纯文本，不经过 OpenClaw 网关。

## Workflow
1. 用户在手机微信「我 - 设置 - 插件」里启用 ClawBot。
2. 在云端用官方 CLI 扫码绑定（只借它拿 token，不跑它的网关）：
   `npx -y @tencent-weixin/openclaw-weixin-cli@latest install`
   按提示装好 openclaw 本体后，终端出二维码，微信扫码确认。token 落在
   `~/.openclaw/openclaw-weixin/accounts/*-im-bot.json` 的 `token` 字段。
   注意：裸调 `get_bot_qrcode` 接口拿到的码扫码会提示无法使用，必须走官方 CLI。
3. 把 token 写入桥接配置 `~/workspace/wechat-bridge/config.json`（0600 权限），
   `bash ~/workspace/wechat-bridge/start.sh` 启动转发程序。
4. 转发程序职责（`forwarder.py`，只发不出站、不开公网端口）：
   - `POST /ilink/bot/getupdates` 长轮询（约 35s），把绑定用户的消息写 `inbox/`；
   - 盯 `outbox/`，有回复就 `POST /ilink/bot/sendmessage` 发回微信，必须带上原消息的 `context_token`；
   - 只认第一个发消息的人为绑定用户，其他发送者静默丢弃；
   - 收到 errcode `-14` 立 `NEED_RESCAN` flag 并停收，等用户重扫（见 references/ilink-protocol.md）。
5. hook（`wechat-inbox`，每 20s）查 `inbox/`：有新消息唤醒 worker，worker 认领文件后上报主 agent；
   Muse 用纯文本（禁用 Markdown）写回复到 `outbox/`，转发程序发回微信，同一份回复在主聊天同步。
6. 看门狗 cron 每 5 分钟检查转发进程，挂掉或机器重启后自动拉起；`NEED_RESCAN` 存在时不重启。

## Output Contract
- 微信端收到 Muse 的纯文本回复；主聊天同步一份相同内容。
- 只有绑定用户能触发；token 永不出现在聊天记录、日志或 hook payload 里。

## Operating Rules
1. 凭据只存机器文件（0600），绝不在聊天里明文出现或复述。
2. 微信回复一律纯文本，不用 Markdown（微信不渲染）。
3. 遇到 `-14` 只立 flag 通知用户重扫，不循环重试。
4. OpenClaw 网关保持关闭，避免和转发程序抢同一个 token 的消息游标。
5. 绑定成功后必须让用户先发一句话做端到端测试，再声称链路打通。
