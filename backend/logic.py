# logic.py —— 简单规则匹配机器人，可后期扩展为 AI 或数据库等逻辑

def get_bot_reply(message: str) -> str:
    message = message.lower()

    if "Bonjour" in message:
        return "Bonjour, bienvenue chez gamesawa，Comment puis-je vous aider ?"      #你好       你好-欢迎语    有什么能帮你
    elif "*" in message:
        return "Veuillez décrire en détail le problème que vous avez rencontré" #请详细描述您遇到的问题
    elif "J'ai effectué un retrait que je n'ai pas encore reçu" in message :    #我提现了还没到账
        return "En raison de l'instabilité des canaux de paiement, veuillez patienter" #由于支付渠道不稳定，请您耐心等待
    else:
        return "Désolé, je ne peux pas répondre à cette question pour le moment. Notre service client vous contactera dès que possible." #抱歉，我暂时无法回答这个问题，我们的客服会尽快联系您。
     
