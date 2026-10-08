# Muse for WeChat-Bot

在微信里直接跟 Muse 聊天，不用切 App。不走 OpenClaw 网关，消息直达 Muse 本人。

A skill that connects Muse to WeChat via Tencent's ClawBot (iLink) plugin: a cloud forwarder long-polls messages, Muse replies, and the reply is sent back to WeChat with a synced copy in the main chat.

## 工作方式 / How it works

```
微信 → forwarder.py（长轮询 getupdates）→ inbox/
     → hook（20s）唤醒 Muse → 纯文本回复 → outbox/
     → sendmessage 发回微信 → 主聊天同步
```

## 关键步骤 / Key steps

1. 手机微信「我 → 设置 → 插件」启用 ClawBot
2. 云端跑官方 CLI 扫码绑定（只借它拿 token，不跑它的网关）：
   `npx -y @tencent-weixin/openclaw-weixin-cli@latest install`
   ⚠️ 自己调 `get_bot_qrcode` 接口拿的码扫码会提示无法使用，必须走官方 CLI
3. token 写入 `~/workspace/wechat-bridge/config.json`（0600），启动转发程序
4. 只认第一个发消息的人（自动绑定），其他人静默丢弃；回复一律纯文本

## 文件 / Files

- `SKILL.md` — 完整工作流（绑定 → 转发 → 唤醒 → 回复 → 看门狗）
- `references/ilink-protocol.md` — iLink 接口备忘（鉴权、收发、错误码）

## 安全 / Security

- token 只存机器文件（0600），绝不进聊天记录
- errcode `-14`（token 过期）→ 等用户重扫，不循环重试
- 全程只发出站请求，不开放公网端口
