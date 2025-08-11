from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator

app = Flask(__name__)
CORS(app)

translator = Translator()

# 模拟答题库
qa_list = {
    "你好": "你好，很高兴为您服务！",
    "你是谁": "我是您的客服机器人。"
}

def get_answer(question):
    return qa_list.get(question, "抱歉，我暂时无法回答此问题，我们的人工客服会尽快联系您。")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "请输入内容"}), 200

    # 检测用户语言
    detected = translator.detect(user_message)
    user_lang = detected.lang

    # 如果不是中文，先翻译成中文
    if user_lang != "zh-cn":
        translated_to_cn = translator.translate(user_message, src=user_lang, dest="zh-cn").text
    else:
        translated_to_cn = user_message

    # 在答题库中匹配
    answer_cn = get_answer(translated_to_cn)

    # 如果用户语言不是中文，则将答案翻译回用户语言
    if user_lang != "zh-cn":
        answer_translated = translator.translate(answer_cn, src="zh-cn", dest=user_lang).text
    else:
        answer_translated = answer_cn

    return jsonify({"reply": answer_translated})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
