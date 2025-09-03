from openai import OpenAI

BASE_URL = "http://192.168.196.184:8080/v1"
API_KEY  = "sk-noauth"
MODEL    = "gpt-oss-20b"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

system_prompt = (
    "你是一名在线博彩游戏客服，名字叫「Leo」，24小时在线 精通法语 英语 斯瓦西里语。\n"
    "职责：只回答与网站内「注册、登录、充值、提现、优惠、游戏规则、账号安全」相关的常见问题。\n"
    "要求：你就是真正的客服；无法解决的问题，让用户留下邮箱。\n"
    "充值/提现不到账：请让玩家提供游戏号和时间，回复“请耐心等待 这笔交易正在处理中..”，并让玩家留下邮箱。\n"
    "输出：简短、口语化；一定使用和玩家相同的语言作答。\n"
    "禁止：不要暴露自己是 AI/机器人；不要出现“根据政策”等字样。\n"
    "只输出最终给用户看的回复文本，不要输出任何分析、解释或标签。"
)

messages = [{"role": "system", "content": system_prompt}]

def extract_message(raw: str) -> str:
    """
    只返回 <|message|> 之后的文本；如果没有该锚点，原样返回（满足你的“无锚点则输出全部”的要求）。
    用 rfind 确保取“最后一个” <|message|>，避免上游多次吐标记时误切。
    """
    if not raw:
        return ""
    tag = "<|message|>"
    idx = raw.rfind(tag)
    if idx != -1:
        return raw[idx + len(tag):].strip()
    return raw.strip()

def chat_once(user_text: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
    messages.append({"role": "user", "content": user_text})
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    raw = resp.choices[0].message.content or ""
    reply = extract_message(raw)
    print(reply)
    messages.append({"role": "assistant", "content": reply})

    # 历史裁剪：保留 system + 最近 12 轮
    if len(messages) > 25:
        messages[:] = [messages[0]] + messages[-24:]
    return reply

if __name__ == "__main__":
    print("已连接：仅输出 <|message|> 之后；无锚点则原样输出。输入 /exit 退出。")
    try:
        while True:
            user = input("> 你：").strip()
            if user.lower() in {"/exit", "exit", "quit", "/q"}:
                break
            if not user:
                continue
            chat_once(user)
    except (EOFError, KeyboardInterrupt):
        pass
