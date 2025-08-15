from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from googletrans import Translator
import os, threading, logging
from datetime import datetime

app = Flask(__name__, static_folder='../frontend')

CORS(app, resources={
    r"/api/v1/*": {
        "origins": ["http://3.71.28.18:3000", "http://localhost:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

translator_lock = threading.Lock()
translator = Translator(service_urls=['translate.google.com'])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('server.log'), logging.StreamHandler()]
)

class ConfigStore:
    def __init__(self):
        base_url = os.getenv("API_BASE_URL", "http://3.71.28.18:5000")
        if ':22' in base_url:
            base_url = base_url.replace(':22', ':5000')
        if not base_url.startswith(('http://', 'https://')):
            base_url = f'http://{base_url}'
        self.config = {
            "API_BASE_URL": base_url,
            "DEFAULT_CLIENT_LANG": "fr",
            "TRANSLATION_ENABLED": True,
            "MAX_MESSAGE_LENGTH": 500,
            "VERSION": "1.0.0"
        }

config_store = ConfigStore()

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
            detected = translator.detect(message[:200])  # 提高准确率
            lang = detected.lang
            confidence = detected.confidence
            app.logger.info(f"检测到语言: {lang} (置信度: {confidence})")
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
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/api/v1/agent/reply', methods=['POST'])
def handle_agent_reply():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Invalid request format"}), 400
        message = data['message'].strip()
        target_lang = data.get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])
        if target_lang not in ['fr', 'en', 'es', 'de']:
            target_lang = 'fr'

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
        return jsonify({"status": "error", "message": "Translation service unavailable"}), 503

@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    allowed_origins = ["http://3.71.28.18:3000", "http://localhost:3000"]

    if origin in allowed_origins:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')  # 关键：支持携带 cookie
    else:
        response.headers.add('Access-Control-Allow-Origin', '*')

    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Cache-Control')
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
