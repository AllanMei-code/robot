from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

REPLIES = {
    "你好": "你好！欢迎咨询，我们有什么可以帮您？",
    "价格": "我们的产品价格从100元起。",
    "发货": "订单将在1-2个工作日内发货。",
    "退货": "7天内无理由退货，详情请联系客服。",
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "").strip()
    print(f"💬 用户问题：{question}")
    answer = REPLIES.get(question, "抱歉，我暂时无法回答此问题。")
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)