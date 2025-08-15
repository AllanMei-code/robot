import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from googletrans import Translator
import threading
import logging
from datetime import datetime


base_url = os.getenv("API_BASE_URL", "http://3.71.28.18:5000")  # 第二个参数是默认值

# 初始化Flask应用
app = Flask(__name__, static_folder='../frontend')

CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
#添加路由方法验证
@app.before_request
def check_method():
    if request.method not in ['POST', 'OPTIONS']:
        return jsonify({
            "error": "Method not allowed",
            "allowed_methods": ["POST"]
        }), 405

# 线程安全的翻译器
translator_lock = threading.Lock()
translator = Translator(service_urls=['translate.google.com'])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

# 动态配置存储
class ConfigStore:
    def __init__(self):
        self.config = {
            "API_BASE_URL": os.getenv("API_BASE_URL", "http://3.71.28.18:5000"),
            "DEFAULT_CLIENT_LANG": "fr",
            "TRANSLATION_ENABLED": True,
            "MAX_MESSAGE_LENGTH": 500,
            "VERSION": "1.0.0"
        }

config_store = ConfigStore()

# ==================== API端点 ====================

@app.route('/api/v1/config', methods=['GET'])
def get_config():
    """动态获取前端配置"""
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/chat', methods=['POST','OPTIONS'])
def handle_chat():
    """处理客户消息（自动检测语言并翻译）"""
    try:
        # 验证输入
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Invalid request format"}), 400
            
        message = data['message'].strip()
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
        if len(message) > config_store.config["MAX_MESSAGE_LENGTH"]:
            return jsonify({"error": "Message too long"}), 400

        # 检测语言
        with translator_lock:
            detected = translator.detect(message[:100])  # 检测前100字符提高性能
            lang = detected.lang

            # 如果不是中文则翻译
            if lang != 'zh-cn' and config_store.config["TRANSLATION_ENABLED"]:
                translated = translator.translate(
                    message, 
                    src=lang, 
                    dest='zh-cn'
                ).text
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
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/api/v1/agent/reply', methods=['POST'])
def handle_agent_reply():
    """处理客服回复（翻译为目标语言）"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Invalid request format"}), 400

        message = data['message'].strip()
        target_lang = data.get('target_lang', config_store.config["DEFAULT_CLIENT_LANG"])

        # 验证目标语言
        if target_lang not in ['fr', 'en', 'es', 'de']:  # 支持的语言列表
            target_lang = 'fr'

        with translator_lock:
            translated = translator.translate(
                message,
                src='zh-cn',
                dest=target_lang
            ).text

        return jsonify({
            "status": "success",
            "original": message,
            "translated": translated,
            "target_lang": target_lang,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logging.error(f"Agent reply error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Translation service unavailable"
        }), 503

#添加调试端点检查已注册路由
@app.route('/debug/routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "path": str(rule),
            "methods": sorted(rule.methods)
        })
    return jsonify(sorted(routes, key=lambda x: x['path']))

# ==================== 静态文件服务 ====================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path.startswith('api/'):
        return jsonify({"error": "Not Found"}), 404
    file_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(file_path) and not os.path.isdir(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ==================== 管理接口 ====================

@app.route('/api/v1/admin/config/update', methods=['POST'])
def update_config():
    """动态更新配置（密码保护示例）"""
    if request.headers.get('X-Admin-Secret') != 'your-secret-key':
        return jsonify({"error": "Unauthorized"}), 401

    try:
        new_config = request.get_json()
        config_store.config.update(new_config)
        
        logging.warning(f"Config updated: {new_config}")
        return jsonify({
            "status": "success",
            "updated_config": config_store.config
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==================== 健康检查 ====================

@app.route('/api/v1/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "translation": "operational",
            "database": "not_configured"
        }
    })

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        "status": "error",
        "message": "Method not allowed",
        "allowed_methods": list(e.valid_methods)
    }), 405
# ==================== 启动应用 ====================

if __name__ == '__main__':
    # 生产环境应使用Gunicorn
    app.run(
        host='0.0.0.0',
        port=5000,
        threaded=True,
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )