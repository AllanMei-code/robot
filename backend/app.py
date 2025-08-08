from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os


app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)  # 允许跨域，方便前端调试

# 示例答题库
REPLIES = {
    "你好": "你好！欢迎咨询，我们有什么可以帮您？",
    "价格": "我们的产品价格从100元起。",
    "发货": "订单将在1-2个工作日内发货。",
    "退货": "7天内无理由退货，详情请联系客服。",
}

# 聊天接口
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "").strip()
    print(f"💬 用户问题：{question}")
    answer = REPLIES.get(question, "抱歉，我暂时无法回答此问题。")
    return jsonify({"answer": answer})

# 所有其它 GET 请求都返回 React 的 index.html
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path != "" and os.path.exists(f"frontend/dist/{path}"):
        return send_from_directory("frontend/dist", path)
    else:
        return send_from_directory("frontend/dist", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
