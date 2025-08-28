# -*- coding: utf-8 -*-
"""
GameSawa 实时客服后端 (Flask + Flask-SocketIO)

关键特性：
- 会话 cid（前端带上 ?cid=xxx 或本地生成），按会话分房间：<cid>:clients / <cid>:agents
- 人工/机器人混合：人工“上线”时仅学习&给建议；“下线”或 30s 无响应 → 机器人介入自动回复
- 打字抑制：客服输入中短暂抑制机器人（默认 5s）
- 文本与图片消息，双端回显；机器人回复在两端都可见
- 翻译：优先 LibreTranslate；失败降级 deep_translator；（可选）HuggingFace M2M100，如未安装则自动跳过
- 自学习：把“最近客户问 + 客服答”写入 SQLite（见 bot_store.py）
- 知识检索：优先 bot_store.FTS5，失败回退 LIKE（见 bot_store.py）
- 规则/模板/礼貌短句：policy / templates_kb / responses（可空实现）


"""

from __future__ import annotations
import os
import re
import time
import logging
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room

import threading
import requests

# ========== 兼容导入（包方式 / 目录方式都能跑）==========
def _import_any():
    """
    兼容两种启动方式：
    - 包：gunicorn backend.app:app
    - 目录：cd backend && python app.py
    """
    # logic（业务规则兜底）
    try:
        from .logic import get_bot_reply as _get_bot_reply
    except Exception:
        try:
            from logic import get_bot_reply as _get_bot_reply
        except Exception:
            def _get_bot_reply(_text_zh: str) -> str:
                return ""  # 没有规则时返回空串，由上层继续走知识库/模板/默认兜底
    # bot_store（学习/检索）
    try:
        from .bot_store import init_db as _init_db, log_message as _log_msg, upsert_qa as _upsert_qa, retrieve_best as _retrieve_best
    except Exception:
        from bot_store import init_db as _init_db, log_message as _log_msg, upsert_qa as _upsert_qa, retrieve_best as _retrieve_best

    # policy（语言检测/主题分类/越界回复）
    try:
        from .policy import detect_lang as _detect_lang, classify_topic as _classify_topic, out_of_scope_reply as _oos_reply, ALLOWED_TOPICS as _ALLOWED
    except Exception:
        try:
            from policy import detect_lang as _detect_lang, classify_topic as _classify_topic, out_of_scope_reply as _oos_reply, ALLOWED_TOPICS as _ALLOWED
        except Exception:
            def _detect_lang(text: str) -> str:
                # 极简启发：有中文字符→zh；有重音拉丁+空格→fr；否则en
                if re.search(r"[\u4e00-\u9fff]", text or ""):
                    return "zh"
                if re.search(r"[éàèùâêîôûç]", text or ""):
                    return "fr"
                return "en"
            def _classify_topic(_text: str) -> Optional[str]:
                return None
            def _oos_reply(lang: str) -> str:
                # 多语言的“请留邮箱”提示（与产品约定）
                if lang.startswith("fr"):
                    return "Désolé, cette demande n’est pas prise en charge pour le moment. Veuillez laisser votre e-mail et nous vous contacterons sous 24 heures."
                if lang.startswith("sw"):
                    return "Samahani, swali hili halitumiki kwa sasa. Tafadhali acha barua pepe yako tutakupigia ndani ya masaa 24."
                if lang.startswith("ha"):
                    return "Yi hakuri, wannan tambaya ba a goyon bayan ta ba a halin yanzu. Don Allah ka bar adireshin imel ɗin ka za mu tuntube ka cikin awa 24."
                return "Sorry, this query is not supported at the moment. Please leave your email and we will contact you within 24 hours."
            _ALLOWED = set()

    # responses（礼貌口吻短句）
    try:
        from .responses import polite_short as _polite_short
    except Exception:
        try:
            from responses import polite_short as _polite_short
        except Exception:
            def _polite_short(text: str, _lang: str) -> str:
                return (text or "").strip()

    # templates（简短模板）
    try:
        from .templates_kb import render_template as _render_tmpl
    except Exception:
        try:
            from templates_kb import render_template as _render_tmpl
        except Exception:
            def _render_tmpl(_topic: str, _lang: str, _slots=None):
                return None

    return _get_bot_reply, _init_db, _log_msg, _upsert_qa, _retrieve_best, _detect_lang, _classify_topic, _oos_reply, _ALLOWED, _polite_short, _render_tmpl

(
    get_bot_reply,
    init_db,
    log_message,
    upsert_qa,
    retrieve_best,
    detect_lang,
    classify_topic,
    out_of_scope_reply,
    ALLOWED_TOPICS,
    polite_short,
    render_template,
) = _import_any()

# ========== 可选：HuggingFace 翻译（没有就跳过）==========
HF_AVAILABLE = False
try:
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer  # type: ignore
    # 只有当 PyTorch/SentencePiece 都存在时才可用，否则会 ImportError
    try:
        _model_m2m = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
        _tokenizer_m2m = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
        HF_AVAILABLE = True
    except Exception:
        HF_AVAILABLE = False
except Exception:
    HF_AVAILABLE = False

def _hf_translate(text: str, source_lang: str, target_lang: str) -> str:
    if not HF_AVAILABLE or not text:
        return text
    try:
        _tokenizer_m2m.src_lang = source_lang
        encoded = _tokenizer_m2m(text, return_tensors="pt")
        generated = _model_m2m.generate(
            **encoded,
            forced_bos_token_id=_tokenizer_m2m.get_lang_id(target_lang)
        )
        return _tokenizer_m2m.batch_decode(generated, skip_special_tokens=True)[0]
    except Exception:
        return text

# ========== 轻量翻译：LibreTranslate + deep_translator ==========
translator_lock = threading.Lock()

def _libre_translate(text: str, source: str, target: str) -> Optional[str]:
    """优先尝试 LibreTranslate，多节点任选其一。失败返回 None。"""
    if not text:
        return None
    endpoints = [
        "https://libretranslate.de/translate",
        "https://translate.argosopentech.com/translate",
    ]
    payload = {"q": text, "source": source, "target": target, "format": "text"}
    for ep in endpoints:
        try:
            r = requests.post(ep, json=payload, timeout=5)
            if r.ok:
                ans = (r.json() or {}).get("translatedText", "").strip()
                if ans:
                    return ans
        except Exception:
            continue
    return None

def translate_text(text: str, target: str, source: str = "auto", max_length: int = 4500) -> str:
    """混合策略：LibreTranslate → deep_translator → （可选）HF → 原文"""
    text = (text or "").strip()
    if not text:
        return text

    # 先 LibreTranslate
    src = source
    if source == "auto":
        # 简单自动源语：中文→zh，否则→fr 作为演示，也可 detect_lang(text)
        lang_guess = detect_lang(text)
        src = "zh" if lang_guess.startswith("zh") else "fr"
    res = _libre_translate(text, src, target)
    if res:
        return res

    # 再 deep_translator
    try:
        from deep_translator import GoogleTranslator  # 轻量，无需Torch
        with translator_lock:
            gt = GoogleTranslator(source=src, target=target)
            out = gt.translate(text)
            if out:
                return out
    except Exception:
        pass

    # 可选 HF
    if HF_AVAILABLE:
        out = _hf_translate(text, src, target)
        if out and out != text:
            return out

    # 兜底：原文
    return text

# ========== Flask 应用 ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path=""
)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",                # 与 geventwebsocket worker 匹配
    max_http_buffer_size=20 * 1024 * 1024
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ========== 配置中心 ==========
class ConfigStore:
    def __init__(self):
        base_url = os.getenv("API_BASE_URL", "http://0.0.0.0:5000")
        self.config = {
            "API_BASE_URL": base_url,
            "DEFAULT_CLIENT_LANG": "fr",   # 客户端目标语言
            "TRANSLATION_ENABLED": True,
            "MAX_MESSAGE_LENGTH": 500,
            "BOT_INACTIVITY_SEC": int(os.getenv("BOT_INACTIVITY_SEC", "30")),
            "BOT_SUPPRESS_SEC":  int(os.getenv("BOT_SUPPRESS_SEC", "5")),
        }

config_store = ConfigStore()

# ========== 学习存储 ==========
init_db()

# ========== 选项三：按会话状态 ==========
INACTIVITY_SEC = config_store.config["BOT_INACTIVITY_SEC"]
SUPPRESS_WINDOW_SEC = config_store.config["BOT_SUPPRESS_SEC"]

# 会话与状态
session_info = {}                     # sid -> {'role': 'agent'|'client', 'cid': str}
manual_online_by_cid = {}             # cid -> bool (True=人工上线；False=下线/机器人介入)
suppress_until_by_cid = {}            # cid -> epoch 秒（客服打字抑制到期时间）
last_agent_activity_by_cid = {}       # cid -> epoch 秒（客服上次活动时间）
last_client_by_cid = {}               # cid -> {'fr','zh','ts'}  用于自动学习
last_client_msg_ts_by_cid = {}        # cid -> 最近客户消息 token（时间戳）

# ========== 工具 ==========
def _cid_of_current() -> str:
    info = session_info.get(request.sid, {})
    return info.get('cid', 'default')

def _manual_online(cid: str) -> bool:
    return manual_online_by_cid.get(cid, True)

def _set_manual_online(cid: str, online: bool):
    manual_online_by_cid[cid] = bool(online)

def _update_agent_activity(cid: str):
    last_agent_activity_by_cid[cid] = time.time()

def _typing_suppressed(cid: str) -> bool:
    return time.time() < suppress_until_by_cid.get(cid, 0)

def _broadcast_agent_status(cid: str):
    socketio.emit('agent_status', {'cid': cid, 'online': _manual_online(cid)}, room=cid)

# ========== REST ==========
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })

# ========== WebSocket ==========
@socketio.on('connect')
def handle_connect():
    role = request.args.get("role", "client")
    cid  = request.args.get("cid", "default")
    session_info[request.sid] = {'role': role, 'cid': cid}

    # 会话房 + 角色房
    join_room(cid)
    if role == "agent":
        join_room(f"{cid}:agents")
        _update_agent_activity(cid)
    else:
        join_room(f"{cid}:clients")

    logging.info(f"{role} 连接: sid={request.sid}, cid={cid}")
    _broadcast_agent_status(cid)

@socketio.on('disconnect')
def handle_disconnect():
    info = session_info.pop(request.sid, None)
    logging.info(f"断开: sid={request.sid}, info={info}")

# —— 人工上下线（按会话）——
@socketio.on('agent_set_status')
def handle_agent_set_status(data):
    cid = _cid_of_current()
    want_online = bool((data or {}).get('online', True))
    _set_manual_online(cid, want_online)
    logging.info(f"[人工切换][cid={cid}] online={want_online}")
    _broadcast_agent_status(cid)

# —— 客服正在输入（抑制机器人）——
@socketio.on('agent_typing')
def handle_agent_typing(_data=None):
    cid = _cid_of_current()
    suppress_until_by_cid[cid] = time.time() + SUPPRESS_WINDOW_SEC
    _update_agent_activity(cid)

# —— 延时机器人代答任务 —— 
def _delayed_bot_reply(cid: str, token: float, msg_fr: str, msg_zh: str):
    """客户消息后启动的后台任务：在无人响应 INACTIVITY_SEC 后自动回复。"""
    deadline = token + INACTIVITY_SEC
    while time.time() < deadline:
        socketio.sleep(0.5)
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return  # 有更新的客户消息，取消
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return  # 有客服活动，取消

    # 超时复查
    if last_client_msg_ts_by_cid.get(cid, 0) != token:
        return
    if last_agent_activity_by_cid.get(cid, 0) > token:
        return
    # 打字抑制窗口
    while _typing_suppressed(cid):
        socketio.sleep(0.3)
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    # 取知识库/规则/模板/默认兜底
    reply_zh = None
    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
    if kb:
        reply_zh = kb["answer_zh"]
    if not reply_zh:
        # 业务规则（你原有的 logic.py）
        reply_zh = (get_bot_reply(msg_zh) or "").strip()
    if not reply_zh:
        # 可选模板（短句风格）
        topic = classify_topic(msg_zh) or ""
        tmpl = render_template(topic, "zh")
        if tmpl:
            reply_zh = tmpl
    if not reply_zh:
        # 超范围兜底
        reply_zh = out_of_scope_reply("fr")  # 客户端默认接收法语

    reply_zh = polite_short(reply_zh, "zh")
    reply_fr = translate_text(reply_zh, target="fr", source="zh") if config_store.config["TRANSLATION_ENABLED"] else reply_zh

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
    socketio.emit('new_message', payload, room=f"{cid}:agents")
    socketio.emit('new_message', payload, room=f"{cid}:clients")
    log_message("bot", "zh", reply_zh, conv_id=cid)
    log_message("bot", "fr", reply_fr, conv_id=cid)

# —— 客户端文本/图片 —— 
@socketio.on('client_message')
def handle_client_message(data):
    cid = _cid_of_current()
    msg_fr = (data or {}).get('message', '')
    image  = (data or {}).get('image')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if image:
        payload_img = {"cid": cid, "from": "client", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload_img, room=f"{cid}:agents")
        socketio.emit('new_message', payload_img, room=f"{cid}:clients")
        log_message("client", "img", "[image]", conv_id=cid)
        return

    msg_fr = (msg_fr or "").strip()
    if not msg_fr:
        return

    # FR → ZH（供客服阅读/学习）
    msg_zh = translate_text(msg_fr, target="zh", source="fr") if config_store.config["TRANSLATION_ENABLED"] else msg_fr

    # 记录 token
    token = time.time()
    last_client_msg_ts_by_cid[cid] = token
    last_client_by_cid[cid] = {"fr": msg_fr, "zh": msg_zh, "ts": token}

    # 日志
    log_message("client", "fr", msg_fr, conv_id=cid)
    log_message("client", "zh", msg_zh, conv_id=cid)

    # 先检索，用于“建议”给客服（人工在线时）
    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)

    # 广播客户消息
    payload = {
        "cid": cid,
        "from": "client",
        "original": msg_fr,
        "client_zh": msg_zh,
        "timestamp": ts
    }
    if _manual_online(cid) and kb:
        payload["suggest_zh"] = kb["answer_zh"]
    socketio.emit('new_message', payload, room=f"{cid}:agents")
    socketio.emit('new_message', payload, room=f"{cid}:clients")

    # 机器人介入逻辑
    if not _manual_online(cid):
        # 人工下线：立即自动回复
        reply_zh = None
        kb2 = kb or retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
        if kb2:
            reply_zh = kb2["answer_zh"]
        if not reply_zh:
            rule = (get_bot_reply(msg_zh) or "").strip()
            if rule:
                reply_zh = rule
        if not reply_zh:
            topic = classify_topic(msg_zh) or ""
            tmpl = render_template(topic, "zh")
            if tmpl:
                reply_zh = tmpl
        if not reply_zh:
            reply_zh = out_of_scope_reply("fr")

        reply_zh = polite_short(reply_zh, "zh")
        reply_fr = translate_text(reply_zh, target="fr", source="zh") if config_store.config["TRANSLATION_ENABLED"] else reply_zh

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
        socketio.emit('new_message', payload2, room=f"{cid}:agents")
        socketio.emit('new_message', payload2, room=f"{cid}:clients")
        log_message("bot", "zh", reply_zh, conv_id=cid)
        log_message("bot", "fr", reply_fr, conv_id=cid)
    else:
        # 人工在线：30s 后再检查是否需要机器人代答
        socketio.start_background_task(_delayed_bot_reply, cid, token, msg_fr, msg_zh)

# —— 客服端文本/图片 —— 
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
        socketio.emit('new_message', payload, room=f"{cid}:clients")
        log_message("agent", "img", "[image]", conv_id=cid)
        return

    if not msg:
        return

    translated = translate_text(msg, target=target_lang, source="auto") if config_store.config["TRANSLATION_ENABLED"] else msg

    payload = {
        "cid": cid,
        "from": "agent",
        "original": msg,          # 客服原文（中文）
        "translated": translated, # 客户端收到译文（法语）
        "timestamp": ts
    }
    socketio.emit('new_message', payload, room=f"{cid}:clients")
    log_message("agent", "zh", msg, conv_id=cid)
    log_message("agent", target_lang, translated, conv_id=cid)

    # 自动学习：把最近客户问 -> 当前客服答
    try:
        lc = last_client_by_cid.get(cid, {})
        if lc.get("zh") and (time.time() - lc.get("ts", 0) < 180):
            upsert_qa(q_fr=lc.get("fr", ""), q_zh=lc["zh"], a_zh=msg, source="agent_auto")
    except Exception as e:
        logging.warning(f"auto-learn failed: {e}")

# ========== 前端静态 ==========
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ========== 开发启动 ==========
if __name__ == "__main__" and os.getenv("FLASK_ENV") != "production":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(("0.0.0.0", 5000), app, handler_class=WebSocketHandler)
    logging.info("服务已启动: http://0.0.0.0:5000")
    server.serve_forever()
