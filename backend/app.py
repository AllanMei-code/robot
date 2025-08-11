from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

translator = Translator()

# 客户消息处理
def process_customer_message(raw_msg):
    detected_lang = translator.detect(raw_msg).lang
    if detected_lang != 'zh-cn':
        msg_cn = translator.translate(raw_msg, src=detected_lang, dest='zh-cn').text
    else:
        msg_cn = raw_msg

    reply_cn = get_bot_reply(msg_cn)  # 机器人逻辑处理中文

    if detected_lang != 'zh-cn':
        reply_for_customer = translator.translate(reply_cn, src='zh-cn', dest=detected_lang).text
    else:
        reply_for_customer = reply_cn

    return msg_cn, reply_cn, reply_for_customer


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "请输入内容"}), 200

    # 调用消息处理函数
    msg_cn, reply_cn, reply_for_customer = process_customer_message(user_message)

    # 返回给客户的回复（法语或客户原始语言）
    return jsonify({"reply": reply_for_customer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
