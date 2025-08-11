from flask import Flask, request, jsonify
from flask_cors import CORS
from googletrans import Translator
from deep_translator import GoogleTranslator
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


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '')
    msg_zh = GoogleTranslator(source='fr', target='zh-CN').translate(msg)
    reply_zh = get_bot_reply(msg_zh)
    reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(reply_zh)
    return jsonify({'reply_fr': reply_fr, 'reply_zh': reply_zh})

@app.route('/agent', methods=['POST'])
def agent():
    data = request.json
    msg_zh = data.get('message', '')
    # 中文转法语
    reply_fr = GoogleTranslator(source='zh-CN', target='fr').translate(msg_zh)
    return jsonify({'reply': reply_fr})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
