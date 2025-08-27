import re
import os
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from deep_translator import GoogleTranslator
import threading
from logic import get_bot_reply
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import requests

# 学习存储
from bot_store import init_db, log_message, upsert_qa, retrieve_best

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ========== 初始化 Hugging Face 模型 ==========
model_m2m = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
tokenizer_m2m = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")

def huggingface_translate(text, source_lang, target_lang):
    tokenizer_m2m.src_lang = source_lang
    encoded = tokenizer_m2m(text, return_tensors="pt")
    generated = model_m2m.generate(
        **encoded,
        forced_bos_token_id=tokenizer_m2m.get_lang_id(target_lang)
    )
    return tokenizer_m2m.batch_decode(generated, skip_special_tokens=True)[0]

def hybrid_translate(text, source="fr", target="zh"):
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

def translate_text(text, target="zh-CN", source="auto", max_length=4500):
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
                chunks.append(buf); buf = sent
            else:
                buf = (buf + " " + sent).strip() if buf else sent
        if buf: chunks.append(buf)

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

# ============== 初始化 ==============
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
INACTIVITY_SEC = int(os.getenv("BOT_INACTIVITY_SEC", "30"))   # 无人响应阈值（秒）
SUPPRESS_WINDOW_SEC = int(os.getenv("BOT_SUPPRESS_SEC", "5")) # 打字抑制窗口（秒）

# 会话状态字典
session_info = {}                         # sid -> {'role': 'agent'|'client', 'cid': str}
manual_online_by_cid = {}                 # cid -> bool (True=人工上线/不介入; False=下线/介入)
suppress_until_by_cid = {}                # cid -> epoch 秒（客服打字抑制到期时间）
last_agent_activity_by_cid = {}           # cid -> epoch 秒（客服上次活动时间）
last_client_by_cid = {}                   # cid -> {'fr','zh','ts'}

def _cid_of_current():
    info = session_info.get(request.sid, {})
    return info.get('cid', 'default')

def _manual_online(cid):
    return manual_online_by_cid.get(cid, True)

def _set_manual_online(cid, online: bool):
    manual_online_by_cid[cid] = bool(online)

def _update_agent_activity(cid):
    last_agent_activity_by_cid[cid] = time.time()

def _inactive_too_long(cid):
    last = last_agent_activity_by_cid.get(cid, 0)
    return (time.time() - last) > INACTIVITY_SEC

def _typing_suppressed(cid):
    return time.time() < suppress_until_by_cid.get(cid, 0)

def broadcast_agent_status(cid):
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

    # 房间：cid（所有人） + 角色房间
    join_room(cid)
    if role == "agent":
        join_room(f"{cid}:agents")
        _update_agent_activity(cid)  # 连接也算活动，避免刚连上就触发空闲兜底
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

# ===== 客户端消息（按会话）=====
@socketio.on('client_message')
def handle_client_message(data):
    cid = _cid_of_current()

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

    # 记录最近客户问题
    last_client_by_cid[cid] = {"fr": msg_fr, "zh": msg_zh, "ts": time.time()}
    log_message("client", "fr", msg_fr, conv_id=cid)
    log_message("client", "zh", msg_zh, conv_id=cid)

    # 先查知识库
    kb = retrieve_best(query_fr=msg_fr, query_zh=msg_zh)

    payload = {
        "cid": cid,
        "from": "client",
        "original": msg_fr,
        "client_zh": msg_zh,
        "timestamp": ts
    }

    # 机器人是否介入：手动下线 或（手动上线但已空闲超时），且未处于打字抑制
    manual_online = _manual_online(cid)
    inactive = _inactive_too_long(cid)
    suppressed = _typing_suppressed(cid)
    should_bot_reply = ((not manual_online) or inactive) and (not suppressed)

    if should_bot_reply:
        if kb:
            reply_zh = kb["answer_zh"]
        else:
            reply_zh = get_bot_reply(msg_zh) or msg_zh
        reply_fr = hybrid_translate(reply_zh, source="zh", target="fr")
        payload.update({
            "bot_reply": True,
            "reply_zh": reply_zh,
            "reply_fr": reply_fr
        })
        log_message("bot", "zh", reply_zh, conv_id=cid)
        log_message("bot", "fr", reply_fr, conv_id=cid)
    else:
        # 人工上线&未超时：可选给客服建议
        if kb:
            payload.update({"suggest_zh": kb["answer_zh"]})

    # 广播到本会话
    socketio.emit('new_message', payload, room=f"{cid}:agents")
    socketio.emit('new_message', payload, room=f"{cid}:clients")

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

    # 自动学习（最近客户问 → 本次客服答）
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

# ============== 启动 ==============
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
