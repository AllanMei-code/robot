# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    print(f"[机器人收到消息] {message}")
    msg_lower = message.lower()
    withdraw_keywords = [
        "retrait", "retraits", "retirer", "paiement", "argent", "compte", "transfert",
        "提现", "支付", "钱", "账户", "转账"
    ]

    for keyword in withdraw_keywords:
        if keyword in msg_lower:
            print("[机器人命中关键词] 返回支付渠道不稳定")
            return "En raison de l'instabilité des canaux de paiement, veuillez patienter"

    if "bonjour" in msg_lower or "你好" in msg_lower:
        print("[机器人命中问候] 返回欢迎语")
        return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"
    if "*" in msg_lower:
        print("[机器人命中星号] 返回详细描述提示")
        return "Veuillez décrire en détail le problème que vous avez rencontré"
    if "j'ai effectué un retrait que je n'ai pas encore reçu" in msg_lower or "我已申请提现但尚未到账" in msg_lower:
        print("[机器人命中提现未到账] 返回支付渠道不稳定")
        return "En raison de l'instabilité des canaux de paiement, veuillez patienter"

    print("[机器人未命中任何关键词] 返回默认回复")
    return "Désolé, je ne peux pas répondre à cette question pour le moment. Notre service client vous contactera dès que possible."
