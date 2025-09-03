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

