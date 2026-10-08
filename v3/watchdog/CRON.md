# Watchdog — 看门狗 Cron 定义（Muse）

在 Muse 里创建一个每 5 分钟运行的 cron，任务内容如下：

---

微信桥 v3 看门狗（每 5 分钟）。保持安静是默认：一切正常时不要给用户发任何消息。

## 1. 检查 supervisor 进程

运行：`pgrep -f "[s]upervisor.py" | grep -v pgrep`（注意 bracket 写法，避免匹配到 pgrep 自身）。

- 如果有进程 → 正常，跳到第 2 步。
- 如果没有进程：
  - 如果 `<安装目录>/NEED_RESCAN` 存在 → 凭证过期，不要重启。在主聊天提醒用户重新扫码绑定（先检查看门狗标记文件避免重复提醒；提醒后创建标记）。
  - 否则执行 `bash <安装目录>/start.sh` 重启，并在主聊天说一声"微信转发程序刚才停了，已自动重启"。

## 2. 检查 channel agent 心跳

读 `<安装目录>/channel-agent/heartbeat.json`（JSON：`{agent_id, ts}`，ts 为 epoch 秒）。

- 如果文件不存在，或 `now - ts > 360`（6 分钟）→ 用 subagent 拉起一个新的 channel agent，prompt 用 `channel-agent/PROMPT.md` 全文，把 agent ID 替换为一个随机值。
- 否则 → 正常，什么都不做。

## 3. 报告

- 只有在你实际重启了 supervisor、或发现 NEED_RESCAN 需要用户处理时，才在主聊天说一声。
- 其他情况保持安静，不要打扰用户。
