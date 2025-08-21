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

def translate_text(text, target="zh-CN", max_length=4000):
    if not text:
        return text
    try:
        with translator_lock:
            # 分段翻译
            if len(text) > max_length:
                parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
                translated = [
                    GoogleTranslator(source="auto", target=target).translate(part)
                    for part in parts
                ]
                return ''.join(translated)
            else:
                return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        logging.warning(f"[翻译失败] {e}")
        return text

# ============== 初始化 ==============
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path=""
)
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "http://3.71.28.18:3000"
])

socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3000", "http://3.71.28.18:3000"],
    async_mode="gevent",              # ✅ 用 gevent 模式
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
    msg = data.get('message', '')
    # 直接用原文做机器人匹配（不翻译）
    bot_reply = get_bot_reply(msg)
    # 客服端显示中文（翻译机器人回复为中文）
    reply_zh = GoogleTranslator(source='auto', target='zh-CN').translate(bot_reply)
    # 客户端显示法语（翻译机器人回复为法语）
    reply_fr = GoogleTranslator(source='auto', target='fr').translate(bot_reply)
    return jsonify({
        'reply_fr': reply_fr,
        'reply_zh': reply_zh
    })

# ============== WebSocket 事件 ==============
@socketio.on('client_message')
def handle_client_message(data):
    """客户发消息"""
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')

    if image:
        emit('new_message', {"from": "client", "image": image}, broadcast=True)
        return

    if not msg:
        return

    # 机器人逻辑用原文做匹配
    bot_reply = get_bot_reply(msg)
    # 翻译机器人回复为中文
    translated_zh = translate_text(bot_reply, target="zh-CN")
    # 翻译机器人回复为法语
    translated_fr = translate_text(bot_reply, target="fr")

    emit('new_message', {
        "from": "client",
        "original": msg,
        "bot_reply": bot_reply,
        "reply_zh": translated_zh,
        "reply_fr": translated_fr
    }, broadcast=True)

@socketio.on('agent_message')
def handle_agent_message(data):
    """客服发消息"""
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])

    if image:
        emit('new_message', {"from": "agent", "image": image}, broadcast=True)
        return

    if not msg:
        return

    translated_client = translate_text(msg, target=target_lang) \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    emit('new_message', {
        "from": "agent",
        "original": msg,
        "translated": translated_client
    }, broadcast=True)

# ============== 前端静态文件 ==============

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ============== 启动 ==============

if __name__ == "__main__" and os.getenv("FLASK_ENV") != "production":
    # ✅ gevent 启动方式
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(
        ("0.0.0.0", 5000),
        app,
        handler_class=WebSocketHandler
    )
    logging.info("服务已启动: http://0.0.0.0:5000")
    server.serve_forever()
