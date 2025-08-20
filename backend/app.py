import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from googletrans import Translator
import threading
import logging
from datetime import datetime

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "http://3.71.28.18:3000"
])

# 关键：允许较大的 Socket 传输（图像）
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3000", "http://3.71.28.18:3000"],
    async_mode="eventlet",                 # 或 "gevent"；开发下用内置也行
    max_http_buffer_size=20 * 1024 * 1024  # 20MB，按需增减
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

translator_lock = threading.Lock()
translator = Translator(service_urls=['translate.google.com'])

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

# ============== REST（保留你现有的） ==============
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

# 其余 REST 路由略……（你已有的可保留）

# ============== WebSocket 事件 ==============
def translate_safe(text, src, dest):
    if not text:
        return text
    try:
        with translator_lock:
            return translator.translate(text, src=src, dest=dest).text
    except Exception as e:
        logging.warning(f"translate_safe failed: {e}")
        return text  # 失败就回退原文，避免中断

@socketio.on('client_message')
def handle_client_message(data):
    """
    客户发来文本或图片：
    - 文本：翻译成中文给客服端（agent 看到中文）
    - 图片：原样广播（两端都能看）
    """
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')

    if image:
        emit('new_message', {
            "from": "client",
            "image": image
        }, broadcast=True)
        return

    if not msg:
        return

    # 检测语言并翻译 -> 中文（给客服端看的）
    try:
        with translator_lock:
            det = translator.detect(msg[:100])
            lang = det.lang
    except Exception:
        lang = 'auto'

    translated_zh = translate_safe(msg, src=lang if lang else 'auto', dest='zh-cn') \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    emit('new_message', {
        "from": "client",
        "original": msg,           # 客户端页面看原文（右侧）
        "translated": translated_zh  # 客服端页面显示中文（左侧）
    }, broadcast=True)

@socketio.on('agent_message')
def handle_agent_message(data):
    """
    客服发来文本或图片：
    - 文本：从中文翻译成目标语言给客户端
    - 图片：原样广播
    """
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])

    if image:
        emit('new_message', {
            "from": "agent",
            "image": image
        }, broadcast=True)
        return

    if not msg:
        return

    translated_client = translate_safe(msg, src='zh-cn', dest=target_lang) \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    emit('new_message', {
        "from": "agent",
        "original": msg,             # 客服端页面看原文（右侧，中文）
        "translated": translated_client  # 客户端页面显示目标语（左侧）
    }, broadcast=True)

# ============== 静态文件（保留） ==============
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == "__main__":
    # 开发环境直接跑；生产用 gunicorn -k eventlet 启动也可以
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
