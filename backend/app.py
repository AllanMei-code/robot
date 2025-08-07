from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许跨域，方便前端调试

@app.route("/api/chat", methods=["GET"])
def chat_get():
    return "接口 /api/chat 只支持 POST 请求，请使用 POST 方法调用。"

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"answer": "请提供问题"}), 400

    # 简单示例：根据关键词回答
    if "你好" in question:
        answer = "你好！有什么可以帮您的？"
    elif "天气" in question:
        answer = "今天天气晴朗，适合出门。"
    else:
        answer = "抱歉，我暂时无法回答您的问题。"

    return jsonify({"answer": answer})

if __name__ == "__main__":
    print("🚀 启动 Flask ...")
    app.run(host="0.0.0.0", port=5000)
