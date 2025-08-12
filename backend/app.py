from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

translator = Translator()

# 客户端发消息（可能是法语、中文等）
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    # 检测语言
    detected_lang = translator.detect(user_message).lang

    # 翻译成中文给客服看
    if detected_lang != 'zh-cn':
        msg_cn = translator.translate(user_message, src=detected_lang, dest='zh-cn').text
    else:
        msg_cn = user_message

    # 机器人生成中文回复
    reply_cn = get_bot_reply(msg_cn)

    # 翻译成客户语言
    if detected_lang != 'zh-cn':
        reply_for_customer = translator.translate(reply_cn, src='zh-cn', dest=detected_lang).text
    else:
        reply_for_customer = reply_cn

    return jsonify({
        "customer_view": user_message,        # 客户界面看到原文（法语）
        "agent_view": msg_cn,                 # 客服界面看到翻译后的中文
        "reply_fr": reply_for_customer,       # 客户界面显示的回复（法语）
        "reply_zh": reply_cn                   # 客服界面显示的中文回复
    })


# 客服端发消息（中文）
@app.route("/agent", methods=["POST"])
def agent():
    data = request.get_json()
    agent_message = data.get("message", "").strip()
    if not agent_message:
        return jsonify({"error": "Empty message"}), 400

    # 翻译成法语给客户
    reply_for_customer = translator.translate(agent_message, src='zh-cn', dest='fr').text

    return jsonify({
        "customer_view": reply_for_customer,  # 客户界面显示法语
        "agent_view": agent_message           # 客服界面显示中文
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
