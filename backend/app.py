from flask import Flask, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 客户端发消息（法语），返回法语和中文回复
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # 检测语言
    detected_lang = translator.detect(user_message).lang
    if detected_lang != 'zh-cn':
        msg_cn = translator.translate(user_message, src=detected_lang, dest='zh-cn').text
    else:
        msg_cn = user_message

    # 机器人中文回复
    reply_cn = get_bot_reply(msg_cn)

    # 回复翻译成客户语言
    if detected_lang != 'zh-cn':
        reply_for_customer = translator.translate(reply_cn, src='zh-cn', dest=detected_lang).text
    else:
        reply_for_customer = reply_cn

    return jsonify({
        "customer_view": reply_for_customer,  # 客户界面显示
        "agent_view": msg_cn,                  # 客服界面显示翻译后的客户消息
        "agent_reply_view": reply_cn           # 客服界面显示中文回复
    })


# 客服端发消息（中文），返回法语翻译
@app.route("/agent", methods=["POST"])
def agent():
    data = request.get_json()
    agent_message = data.get("message", "").strip()
    if not agent_message:
        return jsonify({"error": "Empty message"}), 400

    # 翻译成法语
    reply_for_customer = translator.translate(agent_message, src='zh-cn', dest='fr').text

    return jsonify({
        "customer_view": reply_for_customer,  # 客户界面显示法语
        "agent_view": agent_message           # 客服界面显示中文
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
