import re
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO,emit
from flask_socketio import join_roomemit
from deep_translator import GoogleTranslator
import threading
from logic import get_bot_reply
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
import requests, logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ========== 初始化 Hugging Face 模型 ==========
model_m2m = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
tokenizer_m2m = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")

def huggingface_translate(text, source_lang, target_lang):
    """使用 HuggingFace M2M100 翻译"""
    tokenizer_m2m.src_lang = source_lang
    encoded = tokenizer_m2m(text, return_tensors="pt")
    generated = model_m2m.generate(
        **encoded,
        forced_bos_token_id=tokenizer_m2m.get_lang_id(target_lang)
    )
    return tokenizer_m2m.batch_decode(generated, skip_special_tokens=True)[0]


def hybrid_translate(text, source="fr", target="zh"):
    """Hybrid 混合策略: 先 LibreTranslate, 再 HuggingFace"""
    # 1. 优先尝试 LibreTranslate
    try:
        resp = requests.post("https://libretranslate.de/translate", json={
            "q": text,
            "source": source,
            "target": target,
            "format": "text"
        }, timeout=5)
        if resp.ok:
            result = resp.json().get("translatedText", "").strip()
            if result:
                return result
    except Exception as e:
        logging.warning(f"LibreTranslate failed, fallback to HF: {e}")

    # 2. 兜底使用 HuggingFace M2M100
    return huggingface_translate(text, source, target)

# ============== 翻译封装 ==============
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

# ============== REST API ==============
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "")

    # 翻译 (法语 -> 中文)
    translated_text = hybrid_translate(user_msg, source="fr", target="zh")

    # 如果有机器人逻辑就调用，否则直接返回翻译
    # bot_reply = get_bot_reply(translated_text)   # 如果有 logic.py
    bot_reply = translated_text  # 没有逻辑库就直接返回翻译

    return jsonify({
        "user_msg": user_msg,
        "reply": bot_reply
    })

# ============== WebSocket 事件 ==============
    #============== 客户端消息 ==============
@socketio.on('connect')
def handle_connect():
    role = request.args.get("role", "client")  # 连接时传 ?role=agent 或 ?role=client
    if role == "agent":
        join_room("agents")
        logging.info(f"客服端连接成功: {request.sid}")
    else:
        join_room("clients")
        logging.info(f"客户端连接成功: {request.sid}")


@socketio.on('client_message')
def handle_client_message(data):
    msg_fr = (data or {}).get('message', '').strip()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not msg_fr:
        return

    # 1. 翻译用户消息成中文
    msg_zh = hybrid_translate(msg_fr, source="fr", target="zh")

    # 2. 答题库匹配
    bot_reply_zh = get_bot_reply(msg_zh) or msg_zh

    # 3. 翻译回法语
    bot_reply_fr = hybrid_translate(bot_reply_zh, source="zh", target="fr")

    payload = {
        "from": "client",
        "original": msg_fr,       # 客户端原始输入（法语）
        "client_zh": msg_zh,      # 翻译成中文（客服端用）
        "reply_zh": bot_reply_zh, # 机器人中文回复（客服端用）
        "reply_fr": bot_reply_fr, # 机器人法语回复（客户端用）
        "timestamp": ts
    }

    # ✅ 发给客服端
    socketio.emit('new_message', payload, room="agents")
    # ✅ 同时发回客户端（带翻译的机器人回复）
    socketio.emit('new_message', payload, room="clients")


@socketio.on('agent_message')
def handle_agent_message(data):
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if image:
        payload = {
            "from": "agent",
            "image": image,
            "timestamp": ts
        }
        # ✅ 客服发图片 → 客户端收到
        socketio.emit('new_message', payload, room="clients")
        return

    if not msg:
        return

    translated = translate_text(msg, target=target_lang, source="auto") \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    payload = {
        "from": "agent",
        "original": msg,        # 客服端原文（中文）
        "translated": translated, # 客户端收到的翻译（法语）
        "timestamp": ts
    }

    # ✅ 客服发消息 → 客户端收到翻译
    socketio.emit('new_message', payload, room="clients")

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
