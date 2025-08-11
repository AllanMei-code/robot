from flask import Flask, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 客户端发消息（法语），返回法语和中文回复
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '')
    # 法语转中文
    msg_zh = GoogleTranslator(source='fr', target='zh-CN').translate(msg)
    # 机器人逻辑处理（中文）
    reply_zh = get_bot_reply(msg_zh)
    # 中文转法语
    reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(reply_zh)
    # 返回法语和中文
    return jsonify({'reply_fr': reply_fr, 'reply_zh': reply_zh})

# 客服端发消息（中文），返回法语翻译
@app.route('/agent', methods=['POST'])
def agent():
    data = request.json
    msg_zh = data.get('message', '')
    # 中文转法语
    reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(msg_zh)
    return jsonify({'reply': reply_fr})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
