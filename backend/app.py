# -*- coding: utf-8 -*-
"""
Flask + Socket.IO（geventwebsocket）客服后端
- 会话级手动上线/下线（人工在线=只学习；人工下线=机器人介入）
- 无人响应超时（默认 30s）自动机器人介入
- 客服打字抑制（默认 5s）期间不介入
- 双向翻译：客户端语言<->中文（M2M100 + LibreTranslate 优先）
- 自动学习：近 3 分钟内的“客户问 -> 客服答”写入知识库
"""

import os
import re
import time
import logging
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room

import threading
import requests

# 翻译
from deep_translator import GoogleTranslator
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

# ====== 包内相对导入（关键！）======
from .bot_store import init_db, log_message, upsert_qa, retrieve_best
from .policy import detect_lang, classify_topic, out_of_scope_reply, ALLOWED_TOPICS
from .templates_kb import render_template
from .responses import polite_short
from .logic import get_bot_reply
# =================================

# 项目根目录（frontend 静态资源使用）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ========== 初始化 Hugging Face 模型 ==========
# 注意：模型较大，建议生产中用单 worker 或在冷启动阶段提前拉起
model_m2m = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
tokenizer_m2m = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")

def huggingface_translate(text: str, source_lang: str, target_lang: str) -> str:
    tokenizer_m2m.src_lang = source_lang
    encoded = tokenizer_m2m(text, return_tensors="pt")
    generated = model_m2m.generate(
        **encoded,
        forced_bos_token_id=tokenizer_m2m.get_lang_id(target_lang)
    )
    return tokenizer_m2m.batch_decode(generated, skip_special_tokens=True)[0]

def hybrid_translate(text: str, source="fr", target="zh") -> str:
    """混合策略：优先 LibreTranslate，失败再用 M2M100"""
    try:
        resp = requests.post("https://libretranslate.de/translate", json={
            "q": text, "source": source, "target": target, "format": "text"
        }, timeout=5)
        if resp.ok:
            result = resp.json().get("translatedText", "").strip()
            if result:
                return result
    except Exception as e:
        logging.warning(f"LibreTranslate failed, fallback to HF: {e}")

    return huggingface_translate(text, source, target)

translator_lock = threading.Lock()

def translate_text(text: str, target="zh-CN", source="auto", max_length=4500) -> str:
    """deep_translator + 句子切分，适配长文本"""
    text = (text or "").strip()
    if not text:
        return text
    try:
        sentences = re.split(r'(?<=[\.\!\?。！？；;，,])\s+', text)
        chunks, buf = [], ""
        for sent in sentences:
            if not sent:
                continue
            if len(buf) + len(sent) + 1 > max_length:
                chunks.append(buf)
                buf = sent
            else:
                buf = (buf + " " + sent).strip() if buf else sent
        if buf:
            chunks.append(buf)

        gt = GoogleTranslator(source=source, target=target)
        try:
            out = gt.translate_batch(chunks)
        except Exception:
            out = [GoogleTranslator(source=source, target=target).translate(c) for c in chunks]

        result = " ".join(out).strip()
        if source == "auto" and len(result) < max(12, int(len(text) * 0.55)):
            try:
                forced = GoogleTranslator(source="fr", target=target).translate(text)
                if len(forced) > len(result) * 1.2:
                    result = forced
            except Exception:
                pass
        return result or text
    except Exception as e:
        logging.warning(f"[翻译失败] {e}")
        return text

# ============== Flask / SocketIO 初始化 ==============
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path=""
)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://3.71.28.18:3000"]}})

socketio = SocketIO(
    app,
    cors_allowed_origins=["http://3.71.28.18:3000"],
    async_mode="gevent",
    max_http_buffer_size=20 * 1024 * 1024
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# 配置中心
class ConfigStore:
    def __init__(self):
        base_url = os.getenv("API_BASE_URL", "http://3.71.28.18:5000")
        self.config = {
            "API_BASE_URL": base_url,
            "DEFAULT_CLIENT_LANG": "fr",
            "TRANSLATION_ENABLED": True,
            "MAX_MESSAGE_LENGTH": 500
        }
config_store = ConfigStore()

# ===== 学习DB =====
init_db()

# ===== 选项三：按会话状态 =====
INACTIVITY_SEC    = int(os.getenv("BOT_INACTIVITY_SEC", "30"))   # 无人响应阈值（秒）
SUPPRESS_WINDOW_SEC = int(os.getenv("BOT_SUPPRESS_SEC", "5"))     # 打字抑制窗口（秒）

# 会话状态字典
session_info = {}                         # sid -> {'role': 'agent'|'client', 'cid': str}
manual_online_by_cid = {}                 # cid -> bool (True=人工上线/不介入; False=下线/介入)
suppress_until_by_cid = {}                # cid -> epoch 秒（客服打字抑制到期时间）
last_agent_activity_by_cid = {}           # cid -> epoch 秒（客服上次活动时间）
last_client_by_cid = {}                   # cid -> {'fr','zh','ts'}  用于自动学习
last_client_msg_ts_by_cid = {}            # cid -> 最近一条客户消息的 token (timestamp)

def _cid_of_current() -> str:
    info = session_info.get(request.sid, {})
    return info.get('cid', 'default')

def _manual_online(cid: str) -> bool:
    # 默认为 True（人工在线）
    return manual_online_by_cid.get(cid, True)

def _set_manual_online(cid: str, online: bool):
    manual_online_by_cid[cid] = bool(online)

def _update_agent_activity(cid: str):
    last_agent_activity_by_cid[cid] = time.time()

def _typing_suppressed(cid: str) -> bool:
    return time.time() < suppress_until_by_cid.get(cid, 0)

def broadcast_agent_status(cid: str):
    socketio.emit('agent_status', {'cid': cid, 'online': _manual_online(cid)}, room=cid)

# ============== REST API（保留） ==============
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

# ============== WebSocket 事件 ==============
@socketio.on('connect')
def handle_connect():
    role = request.args.get("role", "client")
    cid  = request.args.get("cid", "default")
    session_info[request.sid] = {'role': role, 'cid': cid}

    # 加入“会话房间” & “角色房间”
    join_room(cid)
    if role == "agent":
        join_room(f"{cid}:agents")
        _update_agent_activity(cid)  # 连接也算一次活动
    else:
        join_room(f"{cid}:clients")

    logging.info(f"{role} 连接成功: sid={request.sid}, cid={cid}")
    broadcast_agent_status(cid)

@socketio.on('disconnect')
def handle_disconnect():
    info = session_info.pop(request.sid, None)
    logging.info(f"连接断开: sid={request.sid}, info={info}")

# ===== 手动切换：上线/下线（按会话）=====
@socketio.on('agent_set_status')
def handle_agent_set_status(data):
    cid = _cid_of_current()
    want_online = bool((data or {}).get('online', True))
    _set_manual_online(cid, want_online)
    logging.info(f"[人工切换][cid={cid}] online={want_online}")
    broadcast_agent_status(cid)

# ===== 客服正在输入（按会话，抑制机器人）=====
@socketio.on('agent_typing')
def handle_agent_typing(_data=None):
    cid = _cid_of_current()
    suppress_until_by_cid[cid] = time.time() + SUPPRESS_WINDOW_SEC
    _update_agent_activity(cid)

# ===== 延时检查：必要时由机器人代答 =====
def _delayed_bot_reply(cid: str, token: float, msg_fr: str, msg_zh: str):
    """客户消息后启动的后台任务：按 token + 超时阈值进行延时检查。"""
    deadline = token + INACTIVITY_SEC
    while time.time() < deadline:
        socketio.sleep(0.5)
        # 有新客户消息 => token 变化，取消
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        # 客服期间有任何活动 => 取消
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    # 超时点二次检查
    if last_client_msg_ts_by_cid.get(cid, 0) != token:
        return
    if last_agent_activity_by_cid.get(cid, 0) > token:
        return

    # 若处于打字抑制窗口，等待其结束（仍随时可能被取消）
    while _typing_suppressed(cid):
        socketio.sleep(0.3)
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    # 仍需机器人代答：取知识库/规则回复并广播
    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
    if kb:
        reply_zh = kb["answer_zh"]
    else:
        reply_zh = (get_bot_reply(msg_zh) or msg_zh)
    reply_fr = hybrid_translate(reply_zh, source="zh", target="fr")

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

# ===== 客户端消息（按会话）=====
@socketio.on('client_message')
def handle_client_message(data):
    cid   = _cid_of_current()
    msg_fr = (data or {}).get('message', '')
    image  = (data or {}).get('image')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 图片
    if image:
        payload_img = {"cid": cid, "from": "client", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload_img, room=f"{cid}:agents")
        socketio.emit('new_message', payload_img, room=f"{cid}:clients")
        log_message("client", "img", "[image]", conv_id=cid)
        return

    msg_fr = (msg_fr or "").strip()
    if not msg_fr:
        return

    # 翻译→中文
    msg_zh = hybrid_translate(msg_fr, source="fr", target="zh")

    # token（时间戳）标记本条客户消息
    token = time.time()
    last_client_msg_ts_by_cid[cid] = token

    # 记录最近客户问题（用于自动学习）
    last_client_by_cid[cid] = {"fr": msg_fr, "zh": msg_zh, "ts": token}

    # 日志
    log_message("client", "fr", msg_fr, conv_id=cid)
    log_message("client", "zh", msg_zh, conv_id=cid)

    # 知识库检索（人工在线时仅作为“建议”给客服端）
    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)

    # 先把客户消息广播给两端
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

    # —— 机器人介入逻辑 —— #
    if not _manual_online(cid):
        # 人工下线：立即自动回复
        kb2 = kb or retrieve_best(query_fr=msg_fr, query_zh=msg_zh)
        if kb2:
            reply_zh = kb2["answer_zh"]
        else:
            reply_zh = (get_bot_reply(msg_zh) or msg_zh)
        reply_fr = hybrid_translate(reply_zh, source="zh", target="fr")
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
        # 人工在线：30s 后再检查（无应答则机器人介入）
        socketio.start_background_task(_delayed_bot_reply, cid, token, msg_fr, msg_zh)

# ===== 客服端消息（按会话）=====
@socketio.on('agent_message')
def handle_agent_message(data):
    cid = _cid_of_current()
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    _update_agent_activity(cid)  # 任何客服动作都更新活跃时间

    if image:
        payload = {"cid": cid, "from": "agent", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload, room=f"{cid}:clients")
        log_message("agent", "img", "[image]", conv_id=cid)
        return

    if not msg:
        return

    # 客服发中文 → 客户端显示目标语言
    translated = translate_text(msg, target=target_lang, source="auto") \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    payload = {
        "cid": cid,
        "from": "agent",
        "original": msg,
        "translated": translated,
        "timestamp": ts
    }
    socketio.emit('new_message', payload, room=f"{cid}:clients")
    log_message("agent", "zh", msg, conv_id=cid)
    log_message("agent", target_lang, translated, conv_id=cid)

    # 自动学习（最近客户问 -> 本次客服答）
    try:
        lc = last_client_by_cid.get(cid, {})
        if lc.get("zh") and (time.time() - lc.get("ts", 0) < 180):
            upsert_qa(q_fr=lc.get("fr",""), q_zh=lc["zh"], a_zh=msg, source="agent_auto")
    except Exception as e:
        logging.warning(f"auto-learn failed: {e}")

# ============== 前端静态文件 ==============
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ============== 启动（开发） ==============
if __name__ == "__main__" and os.getenv("FLASK_ENV") != "production":
    from gevent import monkey; monkey.patch_all()
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(
        ("0.0.0.0", 5000),
        app,
        handler_class=WebSocketHandler
    )
    logging.info("服务已启动: http://0.0.0.0:5000")
    server.serve_forever()
