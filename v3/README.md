# Muse 微信桥 v3

在微信 ClawBot 里直接和 Muse 对话。v3 架构参考腾讯官方 `@tencent-weixin/openclaw-weixin` 插件（v2.4.9）的设计：

- **协议对齐官方**：`ilink/bot/getupdates` 长轮询 + `ilink/bot/sendmessage`，header、消息格式与官方插件一致
- **两个角色，职责切干净**：
  - `supervisor.py`：单个常驻进程，只管传输。35s 长轮询、游标落盘、3 次连续失败退 30s、`-14`（凭证过期）写 `NEED_RESCAN` 并退出、传输错误分类重试
  - Channel Agent：常驻子 agent，**唯一的回复写作者**（单写者，无竞态、无重复发送）
- **看门狗**：5 分钟一轮，supervisor 挂了拉起来，agent 心跳停了重拉

## 一键安装

```bash
bash install.sh
```

安装脚本会：检查 python3、创建目录、尝试从官方 CLI 账号文件读取 token（找不到则提示你先扫码）、写入 `config.json`（权限 0600）、启动 supervisor。

### 前置：获取 token（官方流程）

```bash
npx -y @tencent-weixin/openclaw-weixin-cli@latest install
```

按提示用微信扫码绑定 ClawBot，token 会存到 `~/.openclaw/openclaw-weixin/accounts/`，安装脚本会自动读取。

### 回复侧（Muse）

传输跑起来后，在 Muse 里：

1. 按 `channel-agent/PROMPT.md` 拉起常驻回复 agent
2. 按 `watchdog/CRON.md` 创建 5 分钟看门狗
3. 在微信 ClawBot 里发第一句话，自动绑定你的账号（之后只回复你一个人）

## 诚实说明

- 回复延迟 30 秒到 1 分钟：iLink 只有轮询接口，这是接口形态决定的，官方插件也一样
- `-14` 表示凭证过期：supervisor 会停服并写 `NEED_RESCAN`，重新跑官方 CLI 扫码即可
- 只认第一个绑定的微信用户，其他人消息静默忽略

## 文件

| 文件 | 说明 |
|---|---|
| `supervisor.py` | 传输进程（收/发，不写回复） |
| `install.sh` | 一键安装 |
| `start.sh` | 启动 supervisor（可重复执行） |
| `config.example.json` | 配置模板 |
| `channel-agent/PROMPT.md` | 回复 agent 提示词 |
| `watchdog/CRON.md` | 看门狗 cron 定义 |

## License

MIT
