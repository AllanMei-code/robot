# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    message = message.lower()

    if "你好" in message:
        return "你好！有什么可以帮您？"
    elif "退款" in message:
        return "关于退款，请提供订单号，我们将尽快为您处理。"
    elif "营业时间" in message:
        return "我们的营业时间是每天9:00 - 18:00。"
    else:
        return "抱歉，我暂时无法回答此问题，我们的人工客服会尽快联系您。"
