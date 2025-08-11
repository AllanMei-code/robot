# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    message = message.lower()
    # 法语关键词举例
    withdraw_keywords = [
        "retrait",       # 提现
        "retraits",      # 提现复数
        "retirer",       # 提款动词
        "paiement",      # 支付
        "argent",        # 钱
        "compte",        # 账户
        "transfert"      # 转账
    ]

    for keyword in withdraw_keywords:
        if keyword in message:
            return "En raison de l'instabilité des canaux de paiement, veuillez patienter"  # 支付渠道不稳定，请耐心等待
        if "bonjour" in message:
            return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"      # 你好 - 欢迎语
        if "*" in message:
            return "Veuillez décrire en détail le problème que vous avez rencontré"       # 请详细描述问题
        if "j'ai effectué un retrait que je n'ai pas encore reçu" in message:
            return "En raison de l'instabilité des canaux de paiement, veuillez patienter"  # 支付渠道不稳定，请耐心等待
    return "Désolé, je ne peux pas répondre à cette question pour le moment. Notre service client vous contactera dès que possible." # 默认答复
