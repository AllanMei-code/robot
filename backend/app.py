from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(
    __name__,
    static_folder='../frontend/dist',   # ✅ 这里指向打包后的目录
    static_url_path='/'               # ✅ 让 / 映射到 index.html
)
CORS(app)


# ====== 聊天接口 ======
REPLIES = {
    "你好": "你好！欢迎咨询，我们有什么可以帮您？",
    "价格": "我们的产品价格从100元起。",
    "发货": "订单将在1-2个工作日内发货。",
    "退货": "7天内无理由退货，详情请联系客服。",
}

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "").strip()
    answer = REPLIES.get(question, "抱歉，我暂时无法回答此问题。")
    return jsonify({"answer": answer})


# ====== 加载 index.html 页面（SPA） ======

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")



@app.route("/<path:path>")
def serve_static(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    else:
        # 所有前端路由都交给 index.html 处理（SPA）
        return send_from_directory(app.static_folder, "index.html")

# ====== 启动 ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
