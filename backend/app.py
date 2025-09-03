# -*- coding: utf-8 -*-
"""
App 服务（Socket.IO + REST）
- 会话（cid）隔离 + 客户端/客服端分房间
- 人工/机器切换（在线=只学习，离线/超时=机器人代答）
- 打字抑制（客服正在输入时，不触发机器人）
- 多端点 LibreTranslate 级联翻译（无第三方大模型依赖）
"""

import os
import re
import time
import json
import logging
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room

import requests
import threading
from typing import Any, cast

# ---------- 业务模块（保持你的原有功能） ----------
# 兼容包方式（backend.app:app）与目录方式（app:app）启动
try:
    from .logic import get_bot_reply
    from .bot_store import init_db, log_message, upsert_qa, retrieve_best
    from .policy import detect_lang, classify_topic, out_of_scope_reply, ALLOWED_TOPICS
    from .templates_kb import render_template
    from .responses import polite_short
except Exception:
    from logic import get_bot_reply
    from bot_store import init_db, log_message, upsert_qa, retrieve_best
    from policy import detect_lang, classify_topic, out_of_scope_reply, ALLOWED_TOPICS
    from templates_kb import render_template
    from responses import polite_short

# ============== 基础配置 ==============
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path=""
)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": [os.getenv("FRONTEND_ORIGIN", "http://3.71.28.18:3000")]}})

socketio = SocketIO(
    app,
    cors_allowed_origins=[os.getenv("FRONTEND_ORIGIN", "http://3.71.28.18:3000")],
    async_mode="gevent",
    max_http_buffer_size=20 * 1024 * 1024
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ============== 配置中心 ==============
class ConfigStore:
    def __init__(self):
        base_url = os.getenv("API_BASE_URL", "http://3.71.28.18:5000")
        self.config = {
            "API_BASE_URL": base_url,
            "DEFAULT_CLIENT_LANG": os.getenv("DEFAULT_CLIENT_LANG", "fr"),
            "TRANSLATION_ENABLED": os.getenv("TRANSLATION_ENABLED", "true").lower() != "false",
            "MAX_MESSAGE_LENGTH": int(os.getenv("MAX_MESSAGE_LENGTH", "500"))
        }

config_store = ConfigStore()

# ============== 翻译层（无重依赖，纯 requests） ==============
LIBRE_ENDPOINTS = [
    # 多个公共端点，任何可用即可
    "https://libretranslate.de/translate",
    "https://translate.astian.org/translate",
    "https://libretranslate.com/translate",
]

def safe_translate_old(text: str, target: str, source: str = "auto", timeout: float = 5.0) -> str:
    """
    使用多个 LibreTranslate 端点级联翻译。
    - 成功：返回译文
    - 失败：返回原文，并在日志打印告警
    """
    text = (text or "").strip()
    if not text or not config_store.config["TRANSLATION_ENABLED"]:
        return text

    payload = {"q": text, "source": source or "auto", "target": target, "format": "text"}
    headers = {"Content-Type": "application/json"}

    for url in LIBRE_ENDPOINTS:
        try:
            resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=timeout)
            if resp.ok:
                data = resp.json()
                out = (data.get("translatedText") or "").strip()
                if out:
                    return out
                else:
                    logging.warning(f"[翻译失败-空返回] endpoint={url}")
            else:
                logging.warning(f"[翻译失败-HTTP{resp.status_code}] endpoint={url} text={text[:60]}")
        except Exception as e:
            logging.warning(f"[翻译异常] endpoint={url} err={e}")

    logging.warning("[翻译失败-已回退原文] (可能网络不可达或端点限流) text=%s", text[:80])
    return text


# 兼容覆盖：改进版 safe_translate（优先 JSON，其次表单；auto 时先检测语种；超时可配置）
TRANSLATION_TIMEOUT = float(os.getenv("TRANSLATION_TIMEOUT_SEC", "5.0"))


def safe_translate(text: str, target: str, source: str = "auto", timeout: float = TRANSLATION_TIMEOUT) -> str:
    text = (text or "").strip()
    if not text or not config_store.config["TRANSLATION_ENABLED"]:
        return text

    try:
        if (source or "auto").lower() == "auto":
            try:
                from .policy import detect_lang  # 包内导入
            except Exception:
                from policy import detect_lang   # 兼容脚本方式
            source = detect_lang(text) or "auto"
    except Exception:
        pass

    payload = {"q": text, "source": source or "auto", "target": target, "format": "text"}

    for url in LIBRE_ENDPOINTS:
        try:
            # 先尝试 JSON 提交
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.ok:
                data = resp.json()
                out = (data.get("translatedText") or "").strip()
                if out:
                    return out
                else:
                    logging.warning(f"[翻译失败-空返回] endpoint={url}")
            else:
                # 若 JSON 返回 400/415/422 等，尝试表单回退
                if resp.status_code in (400, 415, 422):
                    try:
                        resp2 = requests.post(url, data=payload, timeout=timeout)
                        if resp2.ok:
                            data2 = resp2.json()
                            out2 = (data2.get("translatedText") or "").strip()
                            if out2:
                                return out2
                        else:
                            logging.warning(f"[翻译失败-HTTP{resp2.status_code}-form] endpoint={url} text={text[:60]}")
                    except Exception as e2:
                        logging.warning(f"[翻译异常-form] endpoint={url} err={e2}")
                else:
                    logging.warning(f"[翻译失败-HTTP{resp.status_code}] endpoint={url} text={text[:60]}")
        except Exception as e:
            logging.warning(f"[翻译异常] endpoint={url} err={e}")

    logging.warning("[翻译失败-已回退原文] (可能网络不可达或端点限流) text=%s", text[:80])
    return text

# ============== 状态与会话 ==============
init_db()  # 初始化学习库

INACTIVITY_SEC = int(os.getenv("BOT_INACTIVITY_SEC", "30"))   # 无人响应阈值（秒）
SUPPRESS_WINDOW_SEC = int(os.getenv("BOT_SUPPRESS_SEC", "5")) # 打字抑制窗口（秒）

session_info = {}                         # sid -> {'role': 'agent'|'client', 'cid': str}
manual_online_by_cid = {}                 # cid -> bool (True=人工上线/不介入; False=下线/介入)
suppress_until_by_cid = {}                # cid -> epoch 秒（客服打字抑制到期时间）
last_agent_activity_by_cid = {}           # cid -> epoch 秒（客服上次活动时间）
last_client_by_cid = {}                   # cid -> {'fr','zh','ts'}  用于自动学习
last_client_msg_ts_by_cid = {}            # cid -> 最近一条客户消息 token

def _get_sid() -> str:
    # Flask's request type stub lacks 'sid' provided by Flask-SocketIO at runtime
    return str(getattr(request, "sid", ""))


def _cid_of_current():
    info = session_info.get(_get_sid(), {})
    return info.get('cid', 'default')

def _manual_online(cid):
    return manual_online_by_cid.get(cid, True)

def _set_manual_online(cid, online: bool):
    manual_online_by_cid[cid] = bool(online)

def _update_agent_activity(cid):
    last_agent_activity_by_cid[cid] = time.time()

def _typing_suppressed(cid):
    return time.time() < suppress_until_by_cid.get(cid, 0)

def broadcast_agent_status(cid):
    socketio.emit('agent_status', {'cid': cid, 'online': _manual_online(cid)}, to=cid)

# ============== REST ==============
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

# ============== Socket.IO 事件 ==============
@socketio.on('connect')
def handle_connect():
    role = request.args.get("role", "client")
    cid  = request.args.get("cid", "default")
    sid = _get_sid()
    session_info[sid] = {'role': role, 'cid': cid}

    join_room(cid)
    if role == "agent":
        join_room(f"{cid}:agents")
        _update_agent_activity(cid)
    else:
        join_room(f"{cid}:clients")

    logging.info(f"{role} connected: sid={sid}, cid={cid}")
    broadcast_agent_status(cid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = _get_sid()
    info = session_info.pop(sid, None)
    logging.info(f"disconnected: sid={sid}, info={info}")

@socketio.on('agent_set_status')
def handle_agent_set_status(data):
    cid = _cid_of_current()
    want_online = bool((data or {}).get('online', True))
    _set_manual_online(cid, want_online)
    logging.info(f"[人工切换][cid={cid}] online={want_online}")
    broadcast_agent_status(cid)

@socketio.on('agent_typing')
def handle_agent_typing(_data=None):
    cid = _cid_of_current()
    suppress_until_by_cid[cid] = time.time() + SUPPRESS_WINDOW_SEC
    _update_agent_activity(cid)

def _delayed_bot_reply(cid, token, msg_fr, msg_zh):
    deadline = token + INACTIVITY_SEC
    while time.time() < deadline:
        socketio.sleep(0.5)  # type: ignore[arg-type]
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    if last_client_msg_ts_by_cid.get(cid, 0) != token:
        return
    if last_agent_activity_by_cid.get(cid, 0) > token:
        return

    while _typing_suppressed(cid):
        socketio.sleep(0.3)  # type: ignore[arg-type]
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
    if kb:
        reply_zh = kb["answer_zh"]
    else:
        reply_zh = (get_bot_reply(msg_zh, cid) or msg_zh)

    reply_fr = safe_translate(reply_zh, target="fr", source="zh")
    ts_send = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "cid": cid,
        "from": "client",
        "original": msg_fr,
        "client_zh": msg_zh,
        "bot_reply": True,
        "reply_zh": reply_zh,
        "reply_fr": reply_fr,
        "timestamp": ts_send
    }
    socketio.emit('new_message', payload, to=f"{cid}:agents")
    socketio.emit('new_message', payload, to=f"{cid}:clients")
    log_message("bot", "zh", reply_zh, conv_id=cid)
    log_message("bot", "fr", reply_fr, conv_id=cid)

@socketio.on('client_message')
def handle_client_message(data):
    cid = _cid_of_current()
    msg_fr = (data or {}).get('message', '')
    image  = (data or {}).get('image')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 图片
    if image:
        payload_img = {"cid": cid, "from": "client", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload_img, to=f"{cid}:agents")
        socketio.emit('new_message', payload_img, to=f"{cid}:clients")
        log_message("client", "img", "[image]", conv_id=cid)
        return

    msg_fr = (msg_fr or "").strip()
    if not msg_fr:
        return
    
    # 统一用 auto → zh，容错多语言
    msg_zh = safe_translate(msg_fr, target="zh", source="auto")

    token = time.time()
    last_client_msg_ts_by_cid[cid] = token
    last_client_by_cid[cid] = {"fr": msg_fr, "zh": msg_zh, "ts": token}

    log_message("client", "fr", msg_fr, conv_id=cid)
    log_message("client", "zh", msg_zh, conv_id=cid)

    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)

    payload = {
        "cid": cid,
        "from": "client",
        "original": msg_fr,   # 客户端原文（常见为法语）
        "client_zh": msg_zh,  # 给客服看的中文
        "timestamp": ts
    }
    if _manual_online(cid) and kb:
        payload["suggest_zh"] = kb["answer_zh"]

    socketio.emit('new_message', payload, to=f"{cid}:agents")
    socketio.emit('new_message', payload, to=f"{cid}:clients")

    # 机器人介入逻辑
    if not _manual_online(cid):
        kb2 = kb or retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
        if kb2:
            reply_zh = kb2["answer_zh"]
        else:
            reply_zh = (get_bot_reply(msg_zh, cid) or msg_zh)
        reply_fr = safe_translate(reply_zh, target=config_store.config["DEFAULT_CLIENT_LANG"], source="zh")
        payload2 = {
            "cid": cid,
            "from": "client",
            "original": msg_fr,
            "client_zh": msg_zh,
            "bot_reply": True,
            "reply_zh": reply_zh,
            "reply_fr": reply_fr,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        socketio.emit('new_message', payload2, to=f"{cid}:agents")
        socketio.emit('new_message', payload2, to=f"{cid}:clients")
        log_message("bot", "zh", reply_zh, conv_id=cid)
        log_message("bot", "fr", reply_fr, conv_id=cid)
    else:
        socketio.start_background_task(_delayed_bot_reply, cid, token, msg_fr, msg_zh)

@socketio.on('agent_message')
def handle_agent_message(data):
    cid = _cid_of_current()
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    _update_agent_activity(cid)

    if image:
        payload = {"cid": cid, "from": "agent", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload, to=f"{cid}:clients")
        log_message("agent", "img", "[image]", conv_id=cid)
        return

    if not msg:
        return

    # 客服发中文 → 客户端显示目标语（如 fr）
    translated = safe_translate(msg, target=target_lang, source="auto")

    payload = {
        "cid": cid,
        "from": "agent",
        "original": msg,          # 客服端原文（中文）
        "translated": translated, # 客户端收到的翻译
        "timestamp": ts
    }
    socketio.emit('new_message', payload, to=f"{cid}:clients")
    log_message("agent", "zh", msg, conv_id=cid)
    log_message("agent", target_lang, translated, conv_id=cid)

    # 自动学习（最近客户问 → 本次客服答）
    try:
        lc = last_client_by_cid.get(cid, {})
        if lc.get("zh") and (time.time() - lc.get("ts", 0) < 180):
            upsert_qa(q_fr=lc.get("fr", ""), q_zh=lc["zh"], a_zh=msg, source="agent_auto")
    except Exception as e:
        logging.warning(f"auto-learn failed: {e}")

# ============== 前端静态文件 ==============
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = cast(str, app.static_folder)
    if path and os.path.exists(os.path.join(static_dir, path)):
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, 'index.html')

# ============== 启动（开发模式） ==============
if __name__ == "__main__" and os.getenv("FLASK_ENV") != "production":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(
        ("0.0.0.0", 5000),
        app,
        handler_class=WebSocketHandler
    )
    logging.info("服务已启动: http://0.0.0.0:5000")
    server.serve_forever()
