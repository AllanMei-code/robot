# responses.py
def polite_short(text: str, lang: str) -> str:
    # 模板已是短句礼貌，这里保留接口用于后续细化不同语言口吻
    return (text or "").strip()
