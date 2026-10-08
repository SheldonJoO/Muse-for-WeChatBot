# iLink 协议备忘（第三方实现整理，部署前以实际响应为准）

## 鉴权头
- `Authorization: Bearer <bot_token>`
- `AuthorizationType: ilink_bot_token`
- `Content-Type: application/json`

## 接口
- 二维码：`GET /ilink/bot/get_bot_qrcode?bot_type=3`
  → `{qrcode, qrcode_img_content, ret}`。注意：裸调此接口拿到的码在微信扫码会提示无法使用，
  绑定必须走官方 CLI（`npx -y @tencent-weixin/openclaw-weixin-cli@latest install`），
  token 从 `~/.openclaw/openclaw-weixin/accounts/*-im-bot.json` 取。
- 登录状态：`GET /ilink/bot/get_qrcode_status?qrcode=<qrcode>`（官方 CLI 流程内已处理，一般不用直调）
- 收消息：`POST /ilink/bot/getupdates`，服务端长轮询约 35 秒；
  请求体带游标 `{"get_updates_buf": cursor}`，响应回 `msgs[]` + 新游标 `get_updates_buf`。
  inbound 消息关键字段：`from_user_id`、`message_id`、`context_token`、`item_list[].text_item.text`。
- 发纯文本：`POST /ilink/bot/sendmessage`
  ```json
  {"msg": {"to_user_id": "...", "message_type": 2, "message_state": 2,
           "context_token": "<原消息的 context_token>",
           "item_list": [{"type": 1, "text_item": {"text": "..."}}]}}
  ```

## 错误码
- `-14`：凭证/会话过期 → 立 NEED_RESCAN，等用户重扫，不要重试轰炸。
- `-2`：限流 → 退避重试。
- 非 0 的其他 errcode/ret：记日志退避，不丢游标。

## 解析兜底
inbound schema 以实际为准，解析时多字段兼容
（`from_user_id`/`from_user`/`sender_id`，`context_token`/`contextToken`，
`item_list`/`items`，`msg_id`/`message_id`/`id`），并打 raw sample 日志方便对账。
非文本消息记类型后给用户一句纯文本提示，不静默吞掉。
