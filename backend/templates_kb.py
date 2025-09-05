# templates_kb.py
from typing import Optional

TEMPLATES = {
    "registration": {
        "en": "Hi! You can sign up with phone or email. It just takes a minute.",
        "fr": "Bonjour ! Vous pouvez vous inscrire avec votre téléphone ou e‑mail. Ça prend une minute.",
        "sw": "Habari! Unaweza kujisajili kwa simu au barua pepe. Inachukua dakika moja tu.",
        "ha": "Sannu! Za ka iya rijista da waya ko imel. Yana ɗaukar ɗan lokaci kaɗan.",
    },
    "login": {
        "en": "Hi there! Please log in with your account and password. If you forgot it, use 'Forgot Password'.",
        "fr": "Bonjour ! Connectez-vous avec votre compte et mot de passe. Mot de passe oublié ? Utilisez 'Mot de passe oublié'.",
        "sw": "Habari! Ingia kwa akaunti na nenosiri. Umesahau? Tumia 'Forgot Password'.",
        "ha": "Sannu! Shiga da asusunka da kalmar sirri. Ka manta? Yi amfani da 'Forgot Password'.",
    },
    "deposit": {
        "en": "Hi! You can top up via {channels}. Most payments arrive within {eta}.",
        "fr": "Bonjour ! Rechargez via {channels}. La plupart des paiements arrivent sous {eta}.",
        "sw": "Habari! Unaweza kuweka kupitia {channels}. Malipo mengi hufika ndani ya {eta}.",
        "ha": "Sannu! Za ka iya ajiya ta {channels}. Yawanci kuɗi na iso cikin {eta}.",
    },
    "withdraw": {
        "en": "Hello! Withdrawals are processed in {eta}. Please use a real-name account.",
        "fr": "Bonjour ! Les retraits sont traités sous {eta}. Merci d’utiliser un compte au vrai nom.",
        "sw": "Habari! Utoaji hushughulikiwa ndani ya {eta}. Tafadhali tumia akaunti yenye jina halisi.",
        "ha": "Sannu! Ana kammala cire kudi cikin {eta}. Don Allah yi amfani da asusun da ke da sunan gaskiya.",
    },
    "promo": {
        "en": "Hi! Current promos are in 'Promotions'. Check rules and time limits before joining.",
        "fr": "Bonjour ! Les promos en cours sont dans 'Promotions'. Vérifiez les règles et délais avant de participer.",
        "sw": "Habari! Promosheni ziko kwenye 'Promotions'. Tafadhali soma kanuni na muda kabla ya kujiunga.",
        "ha": "Sannu! Tallace-tallace suna cikin 'Promotions'. Duba ƙa’idoji da lokaci kafin shiga.",
    },
    "rules": {
        "en": "Hello! Game rules and odds are listed in each game page. Please check before you play.",
        "fr": "Bonjour ! Les règles et cotes se trouvent sur chaque page de jeu. Merci de vérifier avant de jouer.",
        "sw": "Habari! Kanuni na 'odds' ziko kwenye ukurasa wa kila mchezo. Tafadhali angalia kabla ya kucheza.",
        "ha": "Sannu! Ka’idoji da odds suna shafin kowane wasa. Don Allah duba kafin ka fara.",
    },
    "security": {
        "en": "Hi! For your safety, enable 2FA and keep your password private.",
        "fr": "Bonjour ! Pour votre sécurité, activez 2FA et gardez votre mot de passe privé.",
        "sw": "Habari! Kwa usalama, wezesha 2FA na tuliza nenosiri lako.",
        "ha": "Sannu! Don tsaro, kunna 2FA kuma ka kare kalmar sirri.",
    },
    # ===== 常用回复（中文/法语） =====
    "withdraw_conditions": {
        "zh": "提现是有条件的，请仔细查看页面文字，会有详细的描述",
        "fr": "Le retrait est conditionnel. Veuillez lire attentivement la page pour une description détaillée.",
    },
    "provide_game_account": {
        "zh": "请提供你的游戏账号，我帮你查一下",
        "fr": "Veuillez fournir votre compte de jeu et je le vérifierai pour vous.",
    },
    "register_before_login": {
        "zh": "请先注册成功后，才能登录",
        "fr": "Veuillez vous inscrire avec succès avant de vous connecter",
    },
    "register_operator_phone": {
        "zh": "请用运营商号+电话号来注册",
        "fr": "Veuillez vous inscrire avec votre numéro d'opérateur + numéro de téléphone",
    },
    "payment_unstable_try_more": {
        "zh": "由于支付渠道不稳定，请多次尝试",
        "fr": "Étant donné que le canal de paiement est instable, veuillez essayer plusieurs fois",
    },
    "have_fun": {
        "zh": "祝你玩的愉快",
        "fr": "Amusez-vous!",
    },
    "find_in_withdraw_ui": {
        "zh": "在提现界面中可以找到",
        "fr": "Vous pouvez le trouver dans l'interface de retrait",
    },
    "check_withdraw_conditions": {
        "zh": "请检查是否满足提现条件",
        "fr": "Veuillez vérifier si vous remplissez les conditions de retrait",
    },
    "check_deposit_ui": {
        "zh": "请查看充值界面的内容",
        "fr": "Veuillez vérifier le contenu de l'interface de recharge",
    },
    "feedback_to_operator": {
        "zh": "好的，我已经反馈给运营者了，他们有回复后，我会通知你的",
        "fr": "OK, j'ai signalé cela à l'opérateur, je vous ferai savoir quand il répondra.",
    },
    "apology_local_payment_unstable": {
        "zh": "由于本地支付环境的问题导致充值和提现都不稳定，给玩家们造成了不必要的困扰，我们深感抱歉，我们已经积极的在和支付通道沟通，后期会有所改善的",
        "fr": "En raison de problèmes liés à l'environnement de paiement local, les recharges et les retraits sont instables, ce qui a causé des problèmes inutiles aux joueurs. Nous en sommes profondément désolés. Nous avons activement communiqué avec le canal de paiement et nous améliorerons la situation ultérieurement.",
    },
    "apology_operator_network_issue": {
        "zh": "我们对目前的情况深表歉意。目前，运营商网络出现问题，导致充值或提现无法进行。感谢您的耐心等待；支付服务恢复后，您将可以再次进行充值或提现。",
        "fr": "Nous vous présentons nos sincères excuses pour la situation actuelle. Actuellement, il y a un problème de réseau du côté de l'opérateur, ce qui empêche de procéder à des recharges ou des retraits. Merci de votre patience ; dès que le service de paiement sera rétabli, vous pourrez à nouveau effectuer des recharges ou des retraits.",
    },
    "need_participate_platform_activities": {
        "zh": "需要参加平台的活动，并完成平台的任务",
        "fr": "Besoin de participer aux activités de la plateforme et d'accomplir les tâches de la plateforme",
    },
    "complete_tasks_get_rewards": {
        "zh": "按照游戏规则完成任务就可以获得奖励，请确保你已经完成了任务",
        "fr": "Vous pouvez obtenir des récompenses en accomplissant des tâches selon les règles du jeu. Assurez-vous d'avoir terminé les tâches.",
    },
    "payment_unstable_wait": {
        "zh": "由于支付渠道不稳定，请耐心等待",
        "fr": "En raison de l'instabilité des canaux de paiement, veuillez patienter",
    },
    "withdraw_issue_wait": {
        "zh": "如果是提现问题，请耐心等待。支付渠道不稳定，很多付款都会卡住，所以请耐心等待处理",
        "fr": "S'il s'agit d'un problème de retrait, veuillez patienter. Le canal de paiement est instable et de nombreux paiements sont bloqués. Veuillez donc patienter pendant le traitement.",
    },
    "transaction_delay_48h": {
        "zh": "由于支付渠道网络环境不稳定，导致交易有延迟，所以请耐心等待，一般这个时间周期在48小时。",
        "fr": "En raison de l'environnement réseau instable du canal de paiement, les transactions sont retardées, alors veuillez attendre patiemment. Généralement, cette période est de 48 heures.",
    },
    "welcome_gamesawa": {
        "zh": "欢迎来到gamesawa",
        "fr": "Bienvenue sur Gamesawa",
    },
    "describe_issue_detail": {
        "zh": "请详细描述一下你遇到的问题",
        "fr": "Veuillez décrire en détail le problème que vous avez rencontré",
    },
}

DEFAULT_SLOTS = {
    "channels": "bank card, e-wallet or mobile pay",
    "eta": "10–30 minutes",
}

def render_template(topic: str, lang: str, slots: dict = None) -> Optional[str]:
    topic = (topic or "").lower()
    lang = (lang or "en")[:2]
    data = TEMPLATES.get(topic)
    if not data:
        return None
    text = data.get(lang) or data.get("en")
    if not text:
        return None
    merged = dict(DEFAULT_SLOTS)
    if slots:
        merged.update(slots)
    return text.format(**merged)
