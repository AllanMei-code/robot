from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator
from logic import get_bot_reply

app = Flask(__name__)
CORS(app)

translator = Translator()

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "请输入内容"}), 200

    # 1. 检测用户语言
    detected = translator.detect(user_message)
    user_lang = detected.lang

    # 2. 如果不是中文，先翻译成中文（方便后端逻辑理解）
    if user_lang != "zh-cn":
        try:
            translated_to_cn = translator.translate(user_message, src=user_lang, dest="zh-cn").text
        except Exception:
            translated_to_cn = user_message  # 翻译失败回退原文
    else:
        translated_to_cn = user_message

    # 3. 调用机器人逻辑，传入翻译后的消息（这里逻辑里是法语关键词，中文也可以直接用）
    # 你也可以改成传入原文，只要逻辑支持即可
    reply_cn = get_bot_reply(translated_to_cn)

    # 4. 如果用户语言不是中文，则翻译回复成用户语言
    if user_lang != "zh-cn":
        try:
            answer_translated = translator.translate(reply_cn, src="zh-cn", dest=user_lang).text
        except Exception:
            answer_translated = reply_cn  # 翻译失败回退中文回复
    else:
        answer_translated = reply_cn

    return jsonify({"reply": answer_translated})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
