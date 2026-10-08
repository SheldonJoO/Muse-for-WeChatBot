# Muse for WeChat-Bot

在微信里直接跟 Muse 聊天，不用切 App。不走 OpenClaw 网关，消息直达 Muse 本人。

A skill that connects Muse to WeChat via Tencent's ClawBot (iLink) plugin: a cloud forwarder long-polls messages, Muse replies, and the reply is sent back to WeChat with a synced copy in the main chat.

## 🚀 v3 一键安装（最新）

```bash
git clone https://github.com/SheldonJoO/Muse-for-WeChatBot.git
cd Muse-for-WeChatBot/v3
bash install.sh
```

v3 参考腾讯官方 `@tencent-weixin/openclaw-weixin` 插件设计：单个 supervisor 常驻进程负责传输（35s 长轮询、游标落盘、官方级退避），一个常驻 channel agent 专职写回复（单写者，无竞态）。详见 [`v3/README.md`](v3/README.md)。

## 工作方式 / How it works（v3）

```
微信 → supervisor.py（长轮询 getupdates，官方协议）→ inbox/
     → channel agent（常驻，单写者）→ 纯文本回复 → outbox/
     → sendmessage 发回微信
```

## 关键步骤 / Key steps

1. 手机微信「我 → 设置 → 插件」启用 ClawBot
2. 跑官方 CLI 扫码绑定（只借它拿 token，不跑它的网关）：
   `npx -y @tencent-weixin/openclaw-weixin-cli@latest install`
   ⚠️ 自己调 `get_bot_qrcode` 接口拿的码扫码会提示无法使用，必须走官方 CLI
3. `bash v3/install.sh` 一键安装（自动读 token、写 config、启动 supervisor）
4. 在 Muse 里按 `v3/channel-agent/PROMPT.md` 拉起回复 agent，按 `v3/watchdog/CRON.md` 建看门狗
5. 只认第一个发消息的人（自动绑定），其他人静默丢弃；回复一律纯文本

## 文件 / Files

- `v3/` — v3 完整实现（一键安装包）
- `SKILL.md` — 完整工作流（绑定 → 转发 → 唤醒 → 回复 → 看门狗）
- `references/ilink-protocol.md` — iLink 接口备忘（鉴权、收发、错误码）

## 安全 / Security

- token 只存机器文件（0600），绝不进聊天记录
- errcode `-14`（token 过期）→ 等用户重扫，不循环重试
- 全程只发出站请求，不开放公网端口
