from flask import Flask, request, jsonify, render_template
import os
import json

app = Flask(__name__, template_folder="templates")

# 加载答题库
QA_FILE = os.path.join(os.path.dirname(__file__), "qa.json")
with open(QA_FILE, "r", encoding="utf-8") as f:
    qa_dict = json.load(f)

@app.route("/")
def index():
     return render_template("index.html")  # ✅ 加载 HTML 页面

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(force=True)
    print("💬 收到数据：", data)

    question = data.get("question", "").strip()

    # 查找匹配答案（支持模糊包含匹配）
    for key, answer in qa_dict.items():
        if key in question:
            return jsonify({"answer": answer})

    # 没匹配到
    return jsonify({"answer": "抱歉，我暂时无法回答此问题。"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)