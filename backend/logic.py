# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    message = message.lower()

    if "bonjour" in message:
        return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"      # 你好 - 欢迎语
    elif "*" in message:
        return "Veuillez décrire en détail le problème que vous avez rencontré"       # 请详细描述问题
    elif "j'ai effectué un retrait que je n'ai pas encore reçu" in message:
        return "En raison de l'instabilité des canaux de paiement, veuillez patienter"  # 支付渠道不稳定，请耐心等待
    else:
        return "Désolé, je ne peux pas répondre à cette question pour le moment. Notre service client vous contactera dès que possible." # 默认答复
