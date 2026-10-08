#!/bin/bash
# Muse 微信桥 v3 — 一键安装脚本
# 用法：bash install.sh
# 要求：python3，Linux/macOS
set -e

B="$(cd "$(dirname "$0")" && pwd)"
echo "=== Muse 微信桥 v3 一键安装 ==="

# 1. 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：需要 python3，请先安装。"
  exit 1
fi
echo "[1/5] python3 OK"

# 2. 创建目录结构
mkdir -p "$B/inbox" "$B/processing" "$B/processed" "$B/outbox" "$B/sent" "$B/channel-agent"
echo "[2/5] 目录结构 OK"

# 3. 获取 bot_token
TOKEN=""
ACCT_FILE="$HOME/.openclaw/openclaw-weixin/accounts/de13fdcc1ee0-im-bot.json"
# 尝试从官方 CLI 的账号文件读取
for f in "$ACCT_FILE" "$HOME/.openclaw/openclaw-weixin/accounts/"*.json; do
  if [ -f "$f" ]; then
    T=$(python3 -c "import json,sys; d=json.load(open('$f')); print((d.get('token') or d.get('bot_token') or '').strip())" 2>/dev/null || true)
    if [ -n "$T" ]; then TOKEN="$T"; echo "[3/5] 从官方 CLI 账号文件读取到 token"; break; fi
  fi
done
if [ -z "$TOKEN" ]; then
  echo ""
  echo "未找到官方 CLI 的 token。请先运行官方命令扫码绑定："
  echo "  npx -y @tencent-weixin/openclaw-weixin-cli@latest install"
  echo ""
  echo "扫码完成后，把 token 粘贴到这里（或直接回车稍后手动填 config.json）："
  read -r -s -p "bot_token: " TOKEN; echo ""
fi
if [ -z "$TOKEN" ]; then
  echo "警告：token 为空，config.json 已创建模板，请稍后填入再启动。"
fi

# 4. 写 config.json（0600）
python3 - "$B/config.json" "$TOKEN" <<'PYEOF'
import json, sys, os
path, token = sys.argv[1], sys.argv[2]
cfg = {"bot_token": token, "base_url": "https://ilinkai.weixin.qq.com",
       "get_updates_buf": "", "allowed_user_id": ""}
with open(path, "w") as f:
    json.dump(cfg, f)
os.chmod(path, 0o600)
print("[4/5] config.json 已写入（权限 0600）")
PYEOF

# 5. 启动 supervisor
if [ -n "$TOKEN" ]; then
  bash "$B/start.sh"
  echo "[5/5] supervisor 已启动"
else
  echo "[5/5] 跳过启动（无 token）。填入 token 后运行 bash start.sh"
fi

echo ""
echo "=== 安装完成 ==="
echo "下一步（回复侧，需在 Muse 里操作）："
echo "1. 让 Muse 按 channel-agent/PROMPT.md 拉起常驻回复 agent"
echo "2. 按 watchdog/CRON.md 创建 5 分钟看门狗"
echo "3. 在微信 ClawBot 里发第一句话，自动绑定你的账号"
echo ""
echo "详见 README.md"
