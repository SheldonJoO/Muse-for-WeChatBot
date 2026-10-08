#!/usr/bin/env python3
"""WeChat bridge supervisor v3 — single persistent transport process.

Inspired by the official @tencent-weixin/openclaw-weixin plugin (v2.4.9) monitor.

Transport ONLY. Never composes replies, never touches reply logic.

- Long-poll ilink/bot/getupdates (35s); cursor (get_updates_buf) persisted to
  config.json and resumed on restart.
- Failure policy (mirrors official): 3 consecutive failures -> 30s backoff,
  otherwise 2s retry. Transport errors (dns/tcp/tls/timeout) are retriable,
  never fatal.
- errcode -14 (stale token): write NEED_RESCAN and exit. No retry loop.
  The watchdog sees NEED_RESCAN and will NOT restart; user must rescan.
- Watches outbox/: sends via ilink/bot/sendmessage, moves to sent/ on success.
- Single user: the first sender binds as allowed_user_id; others are silently
  ignored.
- notifyStart on boot (official lifecycle).
- Heartbeat log line every 10 successful empty polls (diagnostics).
"""

import base64
import json
import os
import random
import struct
import sys
import time
import urllib.request
import urllib.error
import uuid

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")
LOG = os.path.join(BASE, "supervisor.log")
NEED_RESCAN = os.path.join(BASE, "NEED_RESCAN")
INBOX = os.path.join(BASE, "inbox")
OUTBOX = os.path.join(BASE, "outbox")
SENT = os.path.join(BASE, "sent")

BASE_URL = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.4.9"
BOT_AGENT = "muse-wechat-bridge/3.0"

LONG_POLL_MS = 35_000
MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_MS = 30_000
RETRY_MS = 2_000
SEND_TIMEOUT = 15


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config():
    with open(CONFIG) as f:
        return json.load(f)


def save_config(cfg):
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG)


def headers(token):
    uin = base64.b64encode(struct.pack(">I", random.getrandbits(32))).decode()
    return {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": uin,
        "iLink-App-Id": "bot",
        "Authorization": f"Bearer {token}",
    }


def base_info():
    return {"channel_version": CHANNEL_VERSION, "bot_agent": BOT_AGENT}


def api_post(endpoint, token, body, timeout):
    req = urllib.request.Request(
        BASE_URL + endpoint,
        data=json.dumps(body).encode(),
        headers=headers(token),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:200]
        except Exception:
            detail = ""
        return None, {"_http_error": f"{e.code} {detail}"}
    except Exception as e:
        return None, {"_transport_error": classify_transport_error(e)}


def classify_transport_error(e):
    s = f"{type(e).__name__}: {e}"
    low = s.lower()
    if "timeout" in low or "timed out" in low:
        return f"timeout: {s[:100]}"
    if "name resolution" in low or "nodename" in low or "getaddrinfo" in low:
        return f"dns: {s[:100]}"
    if "connection refused" in low or "unreachable" in low or "reset by peer" in low:
        return f"tcp: {s[:100]}"
    if "ssl" in low or "certificate" in low:
        return f"tls: {s[:100]}"
    return f"unknown: {s[:100]}"


def notify_start(token):
    data, err = api_post("/ilink/bot/msg/notifystart", token,
                         {"base_info": base_info()}, SEND_TIMEOUT)
    if err:
        log(f"notifyStart failed (ignored): {err}")
    elif data and (data.get("ret") not in (None, 0) or data.get("errcode") not in (None, 0)):
        log(f"notifyStart ret={data.get('ret')} errcode={data.get('errcode')} (ignored)")


def extract_text(msg):
    parts = []
    for item in msg.get("item_list") or []:
        if item.get("type") == 1:  # TEXT
            t = (item.get("text_item") or {}).get("text")
            if t:
                parts.append(str(t))
    return "".join(parts).strip()


def handle_inbox(cfg, token, data):
    """Write new USER text messages from the bound user into inbox/."""
    for m in data.get("msgs") or []:
        if m.get("message_type") != 1:  # only USER messages
            continue
        from_user = m.get("from_user_id") or ""
        if not from_user:
            continue
        if not cfg.get("allowed_user_id"):
            cfg["allowed_user_id"] = from_user
            save_config(cfg)
            log(f"bound to user {from_user[:24]}...")
        elif from_user != cfg["allowed_user_id"]:
            continue  # silently ignore other senders
        text = extract_text(m)
        if not text:
            continue
        msg_id = str(m.get("message_id") or uuid.uuid4())
        path = os.path.join(INBOX, f"{msg_id}.json")
        if os.path.exists(path):
            continue
        item = {
            "msg_id": msg_id,
            "from_user": from_user,
            "text": text,
            "context_token": m.get("context_token") or "",
            "ts": time.time(),
        }
        with open(path, "w") as f:
            json.dump(item, f, ensure_ascii=False)
        log(f"inbox <- {msg_id}: {text[:40]}")


def send_outbox(token):
    """Send queued replies. Only true API success counts."""
    for fn in sorted(os.listdir(OUTBOX)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(OUTBOX, fn)
        try:
            with open(p) as f:
                item = json.load(f)
        except Exception as e:
            log(f"outbox {fn}: bad json ({e}), dropping")
            os.remove(p)
            continue
        text = (item.get("text") or "").strip()
        if not text:
            log(f"outbox {fn}: empty text, dropping")
            os.remove(p)
            continue
        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": item.get("to_user_id"),
                "client_id": str(uuid.uuid4()),
                "message_type": 2,   # BOT
                "message_state": 2,  # FINISH
                "item_list": [{"type": 1, "text_item": {"text": text}}],
                "context_token": item.get("context_token") or "",
            },
            "base_info": base_info(),
        }
        data, err = api_post("/ilink/bot/sendmessage", token, body, SEND_TIMEOUT)
        if err:
            log(f"send failed {fn} err={err} (will retry next cycle)")
            continue
        if data is None:
            log(f"send failed {fn}: empty response (will retry next cycle)")
            continue
        errcode = data.get("errcode")
        ret = data.get("ret")
        if errcode == -14 or ret == -14:
            log("sendmessage: stale token (-14)")
            open(NEED_RESCAN, "w").write("stale token from sendmessage\n")
            return "stale"
        if (errcode not in (None, 0)) or (ret not in (None, 0)):
            log(f"send failed {fn}: errcode={errcode} ret={ret} errmsg={data.get('errmsg')}")
            continue
        os.replace(p, os.path.join(SENT, fn))
        log(f"sent -> {fn}")


def main():
    for d in (INBOX, OUTBOX, SENT):
        os.makedirs(d, exist_ok=True)
    cfg = load_config()
    token = (cfg.get("bot_token") or "").strip()
    if not token:
        log("no bot_token in config.json, exiting")
        sys.exit(1)
    if os.path.exists(NEED_RESCAN):
        log("NEED_RESCAN exists, not starting")
        sys.exit(0)

    log(f"supervisor start. bound_user={cfg.get('allowed_user_id') or '(none yet)'}")
    notify_start(token)

    consecutive_failures = 0
    ok_polls = 0
    poll_timeout_ms = LONG_POLL_MS

    while True:
        try:
            data, err = api_post(
                "/ilink/bot/getupdates", token,
                {"get_updates_buf": cfg.get("get_updates_buf") or "",
                 "base_info": base_info()},
                timeout=poll_timeout_ms / 1000 + 10,
            )
            if err:
                raise RuntimeError(err)

            errcode = data.get("errcode")
            ret = data.get("ret")
            if errcode == -14 or ret == -14:
                log("getupdates: stale token (-14). Writing NEED_RESCAN and exiting.")
                open(NEED_RESCAN, "w").write("stale token from getupdates\n")
                sys.exit(0)
            if (errcode not in (None, 0)) or (ret not in (None, 0)):
                raise RuntimeError(f"api error errcode={errcode} ret={ret} "
                                   f"errmsg={data.get('errmsg')}")

            consecutive_failures = 0
            ok_polls += 1
            if ok_polls % 10 == 0:
                log(f"heartbeat: {ok_polls} ok polls, no errors")

            # Server may suggest a new long-poll timeout.
            suggested = data.get("longpolling_timeout_ms")
            if isinstance(suggested, (int, float)) and suggested > 0:
                poll_timeout_ms = int(suggested)

            new_buf = data.get("get_updates_buf")
            if new_buf:
                cfg["get_updates_buf"] = new_buf
                save_config(cfg)

            handle_inbox(cfg, token, data)

            if send_outbox(token) == "stale":
                sys.exit(0)

        except SystemExit:
            raise
        except Exception as e:
            consecutive_failures += 1
            log(f"getupdates error ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                log(f"{MAX_CONSECUTIVE_FAILURES} consecutive failures, backing off 30s")
                consecutive_failures = 0
                time.sleep(BACKOFF_MS / 1000)
            else:
                time.sleep(RETRY_MS / 1000)


if __name__ == "__main__":
    main()
