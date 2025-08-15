from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from deep_translator import GoogleTranslator

app = Flask(__name__, static_folder='../frontend', static_url_path='')
# 允许跨域
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# app.py 里加一个配置接口
@app.route("/api/v1/config", methods=["GET"])
def get_config():
    return jsonify({
        "API_BASE_URL": "http://3.71.28.18:5000",
        "DEFAULT_CLIENT_LANG": "fr"
    })

# 客户端发消息
@socketio.on("client_message")
def handle_client_message(data):
    msg = data.get("message", "").strip()
    if not msg:
        return

    # 翻译成中文发给客服
    translated = GoogleTranslator(source='auto', target='zh-cn').translate(msg)

    # 广播消息（所有连接都收到）
    emit("new_message", {
        "from": "client",
        "original": msg,
        "translated": translated
    }, broadcast=True)

# 客服端发消息
@socketio.on("agent_message")
def handle_agent_message(data):
    msg = data.get("message", "").strip()
    target_lang = data.get("target_lang", "fr")
    if not msg:
        return

    # 翻译成客户语言
    translated = GoogleTranslator(source='auto', target=target_lang).translate(msg)

    # 广播消息
    emit("new_message", {
        "from": "agent",
        "original": msg,
        "translated": translated
    }, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
