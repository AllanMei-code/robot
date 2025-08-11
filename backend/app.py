from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

translator = Translator()

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        # 浏览器预检请求，直接返回200
        return jsonify({"status": "OK"}), 200

    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "请输入内容"}), 200

    # 语言检测和翻译逻辑同之前
    detected = translator.detect(user_message)
    user_lang = detected.lang

    if user_lang != "zh-cn":
        try:
            translated_to_cn = translator.translate(user_message, src=user_lang, dest="zh-cn").text
        except Exception:
            translated_to_cn = user_message
    else:
        translated_to_cn = user_message

    reply_cn = get_bot_reply(translated_to_cn)

    if user_lang != "zh-cn":
        try:
            answer_translated = translator.translate(reply_cn, src="zh-cn", dest=user_lang).text
        except Exception:
            answer_translated = reply_cn
    else:
        answer_translated = reply_cn

    return jsonify({"reply": answer_translated})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
