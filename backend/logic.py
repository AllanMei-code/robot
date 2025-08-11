# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    message = message.lower()

    if "Bonjour" in message:
        return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"
    elif "*" in message:
        return "Veuillez décrire en détail le problème que vous avez rencontré"
    elif "J'ai effectué un retrait que je n'ai pas encore reçu" in message :
        return "En raison de l'instabilité des canaux de paiement, veuillez patienter" 
    else:
        return "抱歉，我暂时无法回答此问题，我们的人工客服会尽快联系您。"
     
