from flask import Flask, request, jsonify
from logic import get_bot_reply
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许跨域请求（前端 HTML 页面需要）

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '').strip()
    reply = get_bot_reply(message)
    return jsonify({'reply': reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
