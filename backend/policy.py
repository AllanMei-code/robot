# policy.py
import os, re, requests, logging
from typing import Optional

ALLOWED_TOPICS = [
    "registration", "login", "deposit", "withdraw", "promo", "rules", "security"
]

KEYS = {
    "registration": [r"register|sign ?up|create account", r"s'inscrire|créer un compte", r"jisajili|kujiandikisha", r"rijista|yin rijista"],
    "login":        [r"log ?in|sign ?in|password|otp", r"se connecter|mot de passe", r"ingia|nenosiri|OTP", r"shiga|kalmar sirri|OTP"],
    "deposit":      [r"deposit|top\s*up|recharge|pay in", r"dépôt|recharger|payer", r"weka\s*fedha|amāna", r"ajiya|caji"],
    "withdraw":     [r"withdraw|cash\s*out|payout", r"retrait|retirer", r"toa pesa|ondo[aá] pesa|toleo", r"cire kudi|fitar da kudi"],
    "promo":        [r"bonus|promo|promotion|coupon|offer", r"bonus|promotion|code promo|offre", r"bonasi|promosheni", r"bônus|tallace|kudin kari"],
    "rules":        [r"rule|how to play|odds|limit", r"règles|comment jouer|cotes|limite", r"kanuni|jinsi ya kucheza|odds|kikomo", r"ka'ida|yadda ake wasa|odds|iyaka"],
    "security":     [r"security|safe|verify|kyc|bind|2fa", r"sécurité|sécuriser|vérifier|KYC|2FA", r"usalama|thibitisha|KYC|2FA", r"tsaro|tabbatar|KYC|2FA"],
}

OUT_OF_SCOPE = {
    "en": "Sorry, this query is not supported at the moment. Please leave your email and we will contact you within 24 hours.",
    "fr": "Désolé, cette demande n’est pas prise en charge pour le moment. Veuillez laisser votre e-mail et nous vous contacterons sous 24 heures.",
    "sw": "Samahani, swali hili halitumiki kwa sasa. Tafadhali acha barua pepe yako tutakupigia ndani ya masaa 24.",
    "ha": "Yi hakuri, wannan tambaya ba a goyon bayan ta ba a halin yanzu. Don Allah ka bar adireshin imel ɗin ka za mu tuntube ka cikin awa 24.",
    "en_fallback": "Sorry, this query is not supported at the moment. Please leave your email and we will contact you within 24 hours.",
}

def _detect_endpoints() -> list:
    eps = []
    # 1) 优先从环境变量 LIBRE_DETECT_ENDPOINTS 读取（逗号分隔，完整 /detect 路径）
    env_eps = os.getenv("LIBRE_DETECT_ENDPOINTS", "").strip()
    if env_eps:
        eps.extend([u.strip() for u in env_eps.split(",") if u.strip()])

    # 2) 兼容：从 LIBRE_ENDPOINTS 推导，将 /translate 替换为 /detect 或在末尾加 /detect
    env_tr = os.getenv("LIBRE_ENDPOINTS", "").strip()
    if env_tr:
        for u in [x.strip() for x in env_tr.split(",") if x.strip()]:
            if "/translate" in u:
                eps.append(u.replace("/translate", "/detect"))
            else:
                eps.append(u.rstrip("/") + "/detect")

    # 3) 公共备选（可能不稳定）
    eps.append("https://libretranslate.de/detect")
    return eps


def detect_lang(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "en"
    # 先尝试可配置/本地的 detect 端点，再回退公共端点
    for url in _detect_endpoints():
        try:
            r = requests.post(url, json={"q": text}, timeout=3)
            if r.ok:
                data = r.json()
                if data and isinstance(data, list):
                    code = (data[0].get("language") or "en").lower()
                    return code[:2]
                else:
                    logging.info(f"detect_lang empty response from {url}")
            else:
                logging.info(f"detect_lang HTTP{r.status_code} from {url}")
        except Exception as e:
            logging.info(f"detect_lang fallback on {url}: {e}")

    # 启发式：法语简单标记
    fr_markers = [" le ", " la ", " de ", " je ", "vous", "avoir", "être", "pour", " s'"]
    if any(m in text.lower() for m in fr_markers): return "fr"
    if re.search(r"[áéíóúñçàèùâêîôûëïüœ]", text.lower()): return "fr"
    return "en"

def classify_topic(text: str) -> str:
    t = (text or "").lower()
    for topic, patterns in KEYS.items():
        for pat in patterns:
            if re.search(pat, t, flags=re.I):
                return topic
    return "other"

def out_of_scope_reply(lang: str) -> str:
    lang = (lang or "en")[:2]
    msg = OUT_OF_SCOPE.get(lang)
    return msg or OUT_OF_SCOPE["en_fallback"]
