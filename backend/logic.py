# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    msg_lower = message.lower()
    withdraw_keywords = [
        "retrait",
        "retraits",
        "retirer",
        "paiement",
        "argent",
        "compte",
        "transfert"
    ]

    for keyword in withdraw_keywords:
        if keyword in msg_lower:
            return "En raison de l'instabilité des canaux de paiement, veuillez patienter"

    if "bonjour" in msg_lower:
        return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"
    if "*" in msg_lower:
        return "Veuillez décrire en détail le problème que vous avez rencontré"
    if "j'ai effectué un retrait que je n'ai pas encore reçu" in msg_lower:
        return "En raison de l'instabilité des canaux de paiement, veuillez patienter"

    return "Désolé, je ne peux pas répondre à cette question pour le moment. Notre service client vous contactera dès que possible."
