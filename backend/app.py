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
    """
    更稳的翻译：
    - 按标点分句拼块，避免长句被截断
    - 默认允许指定源语言（法语时建议 source='fr'）
    - 若返回长度明显异常，自动换用指定源语重试
    """
    text = (text or "").strip()
    if not text:
        return text

    try:
        # 1) 先按句号/问号/感叹号/逗号等分句
        sentences = re.split(r'(?<=[\.\!\?。！？；;，,])\s+', text)
        chunks = []
        buf = ""

        for sent in sentences:
            if not sent:
                continue
            # 控制块大小，避免超过 google 接口解析阈值
            if len(buf) + len(sent) + 1 > max_length:
                chunks.append(buf)
                buf = sent
            else:
                buf = (buf + " " + sent).strip() if buf else sent
        if buf:
            chunks.append(buf)

        gt = GoogleTranslator(source=source, target=target)

        # 2) 逐块翻译（优先 batch，失败再单块）
        out = []
        try:
            out = gt.translate_batch(chunks)
        except Exception:
            # 某些版本/网络下 batch 可能失败，逐块兜底
            out = [GoogleTranslator(source=source, target=target).translate(c) for c in chunks]

        result = " ".join(out).strip()

        # 3) 结果健康度检查：若明显偏短，自动重试（仅当 source='auto' 时）
        # 经验阈值：< 原文长度的 55% 判为可疑
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
    msg_fr = data.get('message', '')

    # 客户消息翻译成中文（客服端用）
    msg_zh = GoogleTranslator(source='fr', target='zh-CN').translate(msg_fr)

    # 用中文去匹配机器人逻辑（逻辑库应该是中文的）
    bot_reply_zh = get_bot_reply(msg_zh)

    # 翻译机器人回复成法语，给客户显示
    bot_reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(bot_reply_zh)

    return jsonify({
        'msg_zh': msg_zh,             # 客户端发的消息（中文）
        'reply_zh': bot_reply_zh,     # 机器人回复（中文）
        'reply_fr': bot_reply_fr      # 机器人回复（法语）
    })


# ============== WebSocket 事件 ==============
@socketio.on('client_message')
def handle_client_message(data):
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')

    if image:
        emit('new_message', {"from": "client", "image": image}, broadcast=True)
        return

    if not msg:
        return

    # 1) 客户消息翻译
    client_msg_zh = translate_text(msg, target="zh-CN", source="fr")   # 法语 -> 中文
    client_msg_fr = msg  # 原文就是法语

    # 2) 机器人逻辑（用中文消息匹配）
    bot_reply_zh = get_bot_reply(client_msg_zh)

    # 3) 翻译机器人回复 -> 法语
    bot_reply_fr = translate_text(bot_reply_zh, target="fr", source="zh-CN")

    # 4) 广播
    emit('new_message', {
        "from": "client",
        "original": msg,            # 客户发的法语
        "client_zh": client_msg_zh, # 客服界面显示
        "client_fr": client_msg_fr, # 客户界面显示

        "bot_reply": bot_reply_zh,  # 原始中文回复
        "reply_zh": bot_reply_zh,   # 客服界面机器人中文
        "reply_fr": bot_reply_fr    # 客户界面机器人法语
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
