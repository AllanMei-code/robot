import re
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from deep_translator import GoogleTranslator
import threading
from logic import get_bot_reply

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg_fr = data.get('message', '')
    msg_zh = GoogleTranslator(source='fr', target='zh-CN').translate(msg_fr)
    bot_reply_zh = get_bot_reply(msg_zh)
    bot_reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(bot_reply_zh)
    return jsonify({
        'msg_zh': msg_zh,
        'reply_zh': bot_reply_zh,
        'reply_fr': bot_reply_fr
    })

# ============== WebSocket 事件 ==============
@socketio.on('client_message')
def handle_client_message(data):
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')

    if image:
        emit('new_message', {
            "from": "client",
            "image": image,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }, broadcast=True)
        return

    if not msg:
        return

    client_msg_zh = translate_text(msg, target="zh-CN", source="fr")
    client_msg_fr = msg
    bot_reply_zh = get_bot_reply(client_msg_zh)
    bot_reply_fr = translate_text(bot_reply_zh, target="fr", source="zh-CN")

    emit('new_message', {
        "from": "client",
        "original": msg,
        "client_zh": client_msg_zh,
        "client_fr": client_msg_fr,
        "bot_reply": bot_reply_zh,
        "reply_zh": bot_reply_zh,
        "reply_fr": bot_reply_fr,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }, broadcast=True)

@socketio.on('agent_message')
def handle_agent_message(data):
    """客服发消息 -> 翻译给客户，并且不回发给自己"""
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 图片直接广播
    if image:
        socketio.emit('new_message', {
            "from": "agent",
            "image": image,
            "timestamp": ts
        }, broadcast=True, include_self=False)   # 关键：不回发给自己
        return

    if not msg:
        return

    # 翻译客服消息（中文 -> 客户语言，默认 fr）
    translated = translate_text(msg, target=target_lang, source="auto") \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    # 统一字段名：客户界面用 translated，客服界面用 original
    payload = {
        "from": "agent",
        "original": msg,
        "translated": translated,
        "timestamp": ts
    }

    socketio.emit('new_message', payload, broadcast=True, include_self=False)  # 关键：不回发给自己



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
