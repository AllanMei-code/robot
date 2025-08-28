# --------- 兼容两种启动方式的导入（包/目录）---------
try:
    # 包方式：在项目根启动，使用 backend.app:app
    from .logic import get_bot_reply
except Exception:
    try:
        # 目录方式：cd 到 backend/ 启动，使用 app:app
        from logic import get_bot_reply
    except Exception:
        # 兜底：没有 logic.py 时给一个空实现，保证服务能启动
        def get_bot_reply(text_zh: str) -> str:
            return ""
# ---------------------------------------------------





# -*- coding: utf-8 -*-
import os
import re
import time
import logging
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import threading
import requests

# 翻译
from deep_translator import GoogleTranslator
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

# 业务规则兜底（可空实现）
from logic import get_bot_reply

# 学习/检索
from .bot_store import init_db, log_message, upsert_qa, retrieve_best
from .policy import detect_lang, classify_topic, out_of_scope_reply, ALLOWED_TOPICS
from .templates_kb import render_template
from .responses import polite_short
from .logic import get_bot_reply

# 新增：主题/语言策略 & 模板礼貌回复
from policy import detect_lang, classify_topic, out_of_scope_reply, ALLOWED_TOPICS
from templates_kb import render_template
from responses import polite_short

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ========== 初始化 Hugging Face 模型 ==========
model_m2m = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
tokenizer_m2m = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")

def huggingface_translate(text, source_lang, target_lang):
    tokenizer_m2m.src_lang = source_lang
    encoded = tokenizer_m2m(text, return_tensors="pt")
    generated = model_m2m.generate(
        **encoded,
        forced_bos_token_id=tokenizer_m2m.get_lang_id(target_lang)
    )
    return tokenizer_m2m.batch_decode(generated, skip_special_tokens=True)[0]

def hybrid_translate(text, source="fr", target="zh"):
    text = (text or "").strip()
    if not text:
        return text
    try:
        resp = requests.post("https://libretranslate.de/translate", json={
            "q": text, "source": source, "target": target, "format": "text"
        }, timeout=5)
        if resp.ok:
            result = resp.json().get("translatedText", "").strip()
            if result:
                return result
    except Exception as e:
        logging.warning(f"LibreTranslate failed, fallback to HF: {e}")
    # HuggingFace 兜底
    try:
        return huggingface_translate(text, source, target)
    except Exception as e:
        logging.warning(f"HF translate failed: {e}")
        return text

# ============== 翻译封装（分片） ==============
translator_lock = threading.Lock()
def translate_text(text, target="zh-CN", source="auto", max_length=4500):
    text = (text or "").strip()
    if not text:
        return text
    try:
        sentences = re.split(r'(?<=[\.\!\?。！？；;，,])\s+', text)
        chunks, buf = [], ""
        for sent in sentences:
            if not sent:
                continue
            if len(buf) + len(sent) + 1 > max_length:
                chunks.append(buf); buf = sent
            else:
                buf = (buf + " " + sent).strip() if buf else sent
        if buf: chunks.append(buf)

        gt = GoogleTranslator(source=source, target=target)
        try:
            out = gt.translate_batch(chunks)
        except Exception:
            out = [GoogleTranslator(source=source, target=target).translate(c) for c in chunks]

        result = " ".join(out).strip()
        if source == "auto" and len(result) < max(12, int(len(text) * 0.55)):
            try:
                forced = GoogleTranslator(source="fr", target=target).translate(text)
                if len(forced) > len(result) * 1.2:
                    result = forced
            except Exception:
                pass
        return result or text
    except Exception as e:
        logging.warning(f"[翻译失败] {e}")
        return text

# ============== Flask / SocketIO ==============
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "frontend"),
    static_url_path=""
)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://3.71.28.18:3000"]}})

socketio = SocketIO(
    app,
    cors_allowed_origins=["http://3.71.28.18:3000"],
    async_mode="gevent",
    max_http_buffer_size=20 * 1024 * 1024
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ============== 配置中心 ==============
class ConfigStore:
    def __init__(self):
        base_url = os.getenv("API_BASE_URL", "http://3.71.28.18:5000")
        self.config = {
            "API_BASE_URL": base_url,
            "DEFAULT_CLIENT_LANG": "fr",  # 没检测到时默认发给客户端的语言
            "TRANSLATION_ENABLED": True,
            "MAX_MESSAGE_LENGTH": 500
        }
config_store = ConfigStore()

# ============== 学习DB 初始化 ==============
init_db()

# ============== 选项三状态机（按会话） ==============
INACTIVITY_SEC    = int(os.getenv("BOT_INACTIVITY_SEC", "30"))  # 无人响应阈值
SUPPRESS_WINDOW_SEC = int(os.getenv("BOT_SUPPRESS_SEC", "5"))    # 打字抑制窗口

# sid -> {'role': 'agent'|'client', 'cid': str}
session_info = {}
# cid -> bool (True=人工上线/不介入; False=下线/介入)
manual_online_by_cid = {}
# cid -> epoch 秒（客服打字抑制到期时间）
suppress_until_by_cid = {}
# cid -> epoch 秒（客服上次活动时间）
last_agent_activity_by_cid = {}
# cid -> 最近客户消息（用于学习）
last_client_by_cid = {}
# cid -> 最近一条客户消息 token（时间戳）
last_client_msg_ts_by_cid = {}
# cid -> 上一次识别的用户语言（用于把客服汉字翻译成玩家语）
last_user_lang_by_cid = {}

def _cid_of_current():
    info = session_info.get(request.sid, {})
    return info.get('cid', 'default')

def _manual_online(cid):
    # 默认为 True（人工在线）
    return manual_online_by_cid.get(cid, True)

def _set_manual_online(cid, online: bool):
    manual_online_by_cid[cid] = bool(online)

def _update_agent_activity(cid):
    last_agent_activity_by_cid[cid] = time.time()

def _typing_suppressed(cid):
    return time.time() < suppress_until_by_cid.get(cid, 0)

def broadcast_agent_status(cid):
    socketio.emit('agent_status', {'cid': cid, 'online': _manual_online(cid)}, room=cid)

# ============== REST（保留） ==============
@app.route('/api/v1/config', methods=['GET'])
def get_config():
    return jsonify({
        "status": "success",
        "config": config_store.config,
        "timestamp": datetime.now().isoformat()
    })

# ============== Socket 事件 ==============
@socketio.on('connect')
def handle_connect():
    role = request.args.get("role", "client")
    cid  = request.args.get("cid", "default")
    session_info[request.sid] = {'role': role, 'cid': cid}

    # 会话房间 + 角色房间
    join_room(cid)
    if role == "agent":
        join_room(f"{cid}:agents")
        _update_agent_activity(cid)  # 连接也算活动
    else:
        join_room(f"{cid}:clients")

    logging.info(f"{role} connected: sid={request.sid}, cid={cid}")
    broadcast_agent_status(cid)

@socketio.on('disconnect')
def handle_disconnect():
    info = session_info.pop(request.sid, None)
    logging.info(f"disconnect: sid={request.sid}, info={info}")

# ===== 人工上线/下线 =====
@socketio.on('agent_set_status')
def handle_agent_set_status(data):
    cid = _cid_of_current()
    want_online = bool((data or {}).get('online', True))
    _set_manual_online(cid, want_online)
    logging.info(f"[manual toggle][cid={cid}] online={want_online}")
    broadcast_agent_status(cid)

# ===== 客服输入中（抑制机器人）=====
@socketio.on('agent_typing')
def handle_agent_typing(_data=None):
    cid = _cid_of_current()
    suppress_until_by_cid[cid] = time.time() + SUPPRESS_WINDOW_SEC
    _update_agent_activity(cid)

# ===== 延时检查：无人响应 → 机器人代答 =====
def _delayed_bot_reply(cid, token, msg_original, msg_zh, user_lang):
    """客户消息后启动的后台任务：token + 超时阈值检查。"""
    deadline = token + INACTIVITY_SEC
    while time.time() < deadline:
        socketio.sleep(0.5)
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return  # 有新客户消息
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return  # 客服活动了

    # 超时点二次确认
    if last_client_msg_ts_by_cid.get(cid, 0) != token:
        return
    if last_agent_activity_by_cid.get(cid, 0) > token:
        return

    # 若处于打字抑制窗口，等待结束（仍可能随时被取消）
    while _typing_suppressed(cid):
        socketio.sleep(0.3)
        if last_client_msg_ts_by_cid.get(cid, 0) != token:
            return
        if last_agent_activity_by_cid.get(cid, 0) > token:
            return

    # 仍需机器人代答：模板/知识库/规则
    kb = retrieve_best(query_fr=msg_original, query_zh=msg_zh)
    if kb:
        reply_zh = kb["answer_zh"]
    else:
        rule = get_bot_reply(msg_zh)
        reply_zh = rule or msg_zh

    ans_lang = hybrid_translate(reply_zh, source="zh", target=user_lang)
    ts_send = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "cid": cid,
        "from": "client",
        "original": msg_original,
        "client_zh": msg_zh,
        "bot_reply": True,
        "reply_zh": polite_short(reply_zh, "zh"),
        "reply_fr": ans_lang,  # 字段名兼容前端，实际是用户语言文本
        "timestamp": ts_send
    }
    socketio.emit('new_message', payload, room=f"{cid}:agents")
    socketio.emit('new_message', payload, room=f"{cid}:clients")
    log_message("bot", "zh", reply_zh, conv_id=cid)
    log_message("bot", user_lang, ans_lang, conv_id=cid)

# ===== 客户端消息 =====
@socketio.on('client_message')
def handle_client_message(data):
    cid = _cid_of_current()

    msg_in = (data or {}).get('message', '')
    image  = (data or {}).get('image')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 图片
    if image:
        payload_img = {"cid": cid, "from": "client", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload_img, room=f"{cid}:agents")
        socketio.emit('new_message', payload_img, room=f"{cid}:clients")
        log_message("client", "img", "[image]", conv_id=cid)
        return

    msg_in = (msg_in or "").strip()
    if not msg_in:
        return

    # 识别语言 & 内部转中文
    user_lang = detect_lang(msg_in)  # en/fr/sw/ha/...
    last_user_lang_by_cid[cid] = user_lang
    msg_zh = hybrid_translate(msg_in, source=user_lang, target="zh")

    # token & 最近客户问
    token = time.time()
    last_client_msg_ts_by_cid[cid] = token
    last_client_by_cid[cid] = {"fr": msg_in, "zh": msg_zh, "ts": token}

    log_message("client", user_lang, msg_in, conv_id=cid)
    log_message("client", "zh", msg_zh, conv_id=cid)

    # 主题分类 & 越界拦截
    topic = classify_topic(msg_in) or "other"
    if topic not in ALLOWED_TOPICS:
        oos = out_of_scope_reply(user_lang)
        payload_oos = {
            "cid": cid, "from": "client",
            "original": msg_in, "client_zh": msg_zh,
            "bot_reply": True,
            "reply_zh": hybrid_translate(oos, source=user_lang, target="zh"),
            "reply_fr": oos,
            "timestamp": ts
        }
        socketio.emit('new_message', payload_oos, room=f"{cid}:agents")
        socketio.emit('new_message', payload_oos, room=f"{cid}:clients")
        log_message("bot", user_lang, oos, conv_id=cid)
        return

    # 模板优先
    tpl_lang_ans = render_template(topic, user_lang, slots={})
    tpl_zh = hybrid_translate(tpl_lang_ans, source=user_lang, target="zh") if tpl_lang_ans else None

    # 检索建议
    kb = retrieve_best(query_fr=msg_in, query_zh=msg_zh)

    # 广播来话（附“建议”给客服端）
    payload_in = {
        "cid": cid, "from": "client",
        "original": msg_in, "client_zh": msg_zh,
        "timestamp": ts
    }
    suggest_zh = tpl_zh or (kb and kb.get("answer_zh"))
    if _manual_online(cid) and suggest_zh:
        payload_in["suggest_zh"] = polite_short(suggest_zh, "zh")

    socketio.emit('new_message', payload_in, room=f"{cid}:agents")
    socketio.emit('new_message', payload_in, room=f"{cid}:clients")

    # 机器人是否立即回
    def _compose_reply(ans_zh: str):
        ans_lang = hybrid_translate(ans_zh, source="zh", target=user_lang)
        return {
            "cid": cid, "from": "client",
            "original": msg_in, "client_zh": msg_zh,
            "bot_reply": True,
            "reply_zh": polite_short(ans_zh, "zh"),
            "reply_fr": ans_lang,  # 兼容字段名
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    if not _manual_online(cid):
        # 人工下线：立刻回
        ans_zh = suggest_zh or (get_bot_reply(msg_zh) or msg_zh)
        payload2 = _compose_reply(ans_zh)
        socketio.emit('new_message', payload2, room=f"{cid}:agents")
        socketio.emit('new_message', payload2, room=f"{cid}:clients")
        log_message("bot", "zh", ans_zh, conv_id=cid)
        log_message("bot", user_lang, payload2["reply_fr"], conv_id=cid)
    else:
        # 人工在线：启动 30s 延迟兜底
        socketio.start_background_task(_delayed_bot_reply, cid, token, msg_in, msg_zh, user_lang)

# ===== 客服端消息 =====
@socketio.on('agent_message')
def handle_agent_message(data):
    cid = _cid_of_current()
    msg = (data or {}).get('message', '').strip()
    image = (data or {}).get('image')
    target_lang = (data or {}).get('target_lang') or last_user_lang_by_cid.get(cid) or config_store.config["DEFAULT_CLIENT_LANG"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    _update_agent_activity(cid)

    if image:
        payload = {"cid": cid, "from": "agent", "image": image, "timestamp": ts}
        socketio.emit('new_message', payload, room=f"{cid}:clients")
        log_message("agent", "img", "[image]", conv_id=cid)
        return

    if not msg:
        return

    translated = translate_text(msg, target=target_lang, source="auto") \
        if config_store.config["TRANSLATION_ENABLED"] else msg

    payload = {
        "cid": cid,
        "from": "agent",
        "original": msg,          # 中文
        "translated": translated, # 用户语言
        "timestamp": ts
    }
    socketio.emit('new_message', payload, room=f"{cid}:clients")
    log_message("agent", "zh", msg, conv_id=cid)
    log_message("agent", target_lang, translated, conv_id=cid)

    # ===== 自动学习：把最近客户问 -> 当前人工答，收敛成中文答案 =====
    try:
        lc = last_client_by_cid.get(cid, {})
        if lc.get("zh") and (time.time() - lc.get("ts", 0) < 180):
            upsert_qa(q_fr=lc.get("fr",""), q_zh=lc["zh"], a_zh=msg, source="agent_auto")
    except Exception as e:
        logging.warning(f"auto-learn failed: {e}")

# ============== 前端静态文件 ==============
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ============== 启动 ==============
if __name__ == "__main__" and os.getenv("FLASK_ENV") != "production":
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(
        ("0.0.0.0", 5000),
        app,
        handler_class=WebSocketHandler
    )
    logging.info("服务已启动: http://0.0.0.0:5000")
    server.serve_forever()
