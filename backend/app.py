import os
import logging
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from googletrans import Translator

# ==================== 初始化 ====================
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",
    "http://3.71.28.18:3000"
])

# 启用 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

translator_lock = threading.Lock()
translator = Translator(service_urls=['translate.google.com'])


# ==================== 配置存储 ====================
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


# ==================== REST API ====================
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/v1/chat', methods=['POST'])
def handle_chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Invalid request format"}), 400
        message = data['message'].strip()
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
        if len(message) > config_store.config["MAX_MESSAGE_LENGTH"]:
            return jsonify({"error": "Message too long"}), 400

        with translator_lock:
            detected = translator.detect(message[:100])
            lang = detected.lang
            if lang != 'zh-cn' and config_store.config["TRANSLATION_ENABLED"]:
                translated = translator.translate(message, src=lang, dest='zh-cn').text
            else:
                translated = message

        logging.info(f"Translation: {lang} -> zh-cn | {message[:20]}... -> {translated[:20]}...")

        return jsonify({
            "status": "success",
            "original": message,
            "translated": translated,
            "detected_lang": lang,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/v1/agent/reply', methods=['POST'])
def handle_agent_reply():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        target_lang = data.get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
        with translator_lock:
            translated = translator.translate(message, src='zh-cn', dest=target_lang).text
        return jsonify({
            "status": "success",
            "original": message,
            "translated": translated,
            "target_lang": target_lang,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Agent reply error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== SocketIO 事件 ====================
@socketio.on('client_message')
def handle_client_message(data):
    try:
        message = data.get('message', '').strip()
        if not message:
            return
        with translator_lock:
            detected = translator.detect(message[:100])
            lang = detected.lang
            translated = translator.translate(message, src=lang, dest='zh-cn').text
        emit('new_message', {
            "from": "client",
            "original": message,
            "translated": translated,
            "detected_lang": lang
        }, broadcast=True)
    except Exception as e:
        logging.error(f"Socket client_message error: {str(e)}")


@socketio.on('agent_message')
def handle_agent_message(data):
    try:
        message = data.get('message', '').strip()
        target_lang = data.get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
        if not message:
            return
        with translator_lock:
            translated = translator.translate(message, src='zh-cn', dest=target_lang).text
        emit('new_message', {
            "from": "agent",
            "original": message,
            "translated": translated,
            "target_lang": target_lang
        }, broadcast=True)
    except Exception as e:
        logging.error(f"Socket agent_message error: {str(e)}")


# ==================== 前端静态文件 ====================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ==================== 启动 ====================
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
