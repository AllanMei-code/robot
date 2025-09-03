from openai import OpenAI
import re

BASE_URL = "http://192.168.0.5:8080/v1"
API_KEY  = "sk-noauth"
MODEL    = "gpt-oss-20b"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

class MessageAfterTagStream:
    # 同时匹配多种分隔写法：<|message|>、<|channel|>final、assistantfinal、assistant
    SEP_RE = re.compile(
        r"(?:<\|message\|>|<\|channel\|>\s*final|assistantfinal|\bassistant\b)",
        re.IGNORECASE
    )

    def __init__(self):
        self.buf = ""
        self.started = False
        self.out = []

    @staticmethod
    def _strip_noise(s: str) -> str:
        # 去掉 <|...|> 标签
        s = re.sub(r"<\|[^>]*\|>", "", s)
        # 去掉这些“词元样式”噪音
        s = re.sub(r"(?i)\bassistantfinal\b", "", s)
        s = re.sub(r"(?i)\buserfinal\b", "", s)
        # 独立的 assistant / final（行首或空白后）
        s = re.sub(r"(?m)(?i)^\s*assistant\s*:?\.?\s*", "", s)
        s = re.sub(r"(?m)(?i)^\s*final\s*:?\.?\s*", "", s)
        return s

    def feed(self, chunk: str):
        if not chunk:
            return
        self.buf += chunk

        if not self.started:
            # 先找“最后一个分隔标记”
            last = None
            for m in self.SEP_RE.finditer(self.buf):
                last = m
            if last:
                self.buf = self.buf[last.end():]
                self.started = True
            else:
                # 没有标记？那就观察是否已经出现中文；有就从第一处中文开始
                m_cn = re.search(r"[\u4e00-\u9fff]", self.buf)
                if m_cn:
                    self.buf = self.buf[m_cn.start():]
                    self.started = True
                else:
                    # 还没见到标记/中文，限制缓冲大小避免膨胀
                    if len(self.buf) > 8192:
                        self.buf = self.buf[-4096:]
                    return

        cleaned = self._strip_noise(self.buf)
        if cleaned:
            print(cleaned, end="", flush=True)
            self.out.append(cleaned)
        self.buf = ""

    def result(self) -> str:
        text = "".join(self.out)
        return self._strip_noise(text).strip()

system_prompt = (
    "你是一名在线博彩游戏客服，名字叫「Leo」，24小时在线。"
    "职责：只回答与网站内「注册、登录、充值、提现、优惠、游戏规则、账号安全」相关的常见问题。"
    "要求：你就是真正的客服；无法解决的问题，让用户留下邮箱（不要引导去别的团队/客服）。"
    "充值/提现不到账：请让玩家提供游戏号和时间，回复“稍等，正在查询”，并让玩家留下邮箱。"
    "输出：简短、口语化、礼貌称谓；不透露技术细节或内部流程；使用玩家语言作答。"
    "仅按用户语言回复固定文本。"
    "禁止：不要暴露自己是 AI/机器人；不要出现“根据政策”“作为AI”等字样。"
)

# —— 对话历史（多轮）
messages = [
    {"role": "system", "content": system_prompt},
]

def chat_once(user_text: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
    messages.append({"role": "user", "content": user_text})

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
    )

    printer = MessageAfterTagStream()

    try:
        for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            c0 = choices[0] if len(choices) > 0 else None
            if not c0:
                continue
            delta = getattr(c0, "delta", None)
            if not delta:
                continue
            piece = getattr(delta, "content", None)
            if not piece:
                continue
            printer.feed(piece)
    except KeyboardInterrupt:
        print()
        return ""

    print()
    reply = printer.result() or "(空回复)"
    messages.append({"role": "assistant", "content": reply})

    # 裁剪历史（保留 system + 最近 12 轮）
    if len(messages) > 1 + 24:
        keep = [messages[0]] + messages[-24:]
        messages[:] = keep

    return reply

if __name__ == "__main__":
    print("已连接到本地模型（流式 + 多轮，仅输出 message/final 之后的文本）。输入 /exit 退出。")
    try:
        while True:
            user = input("> 你：").strip()
            if not user:
                continue
            if user.lower() in {"/exit", "exit", "quit", "/q"}:
                break
            reply = chat_once(user)
            print(f"Leo：{reply}")
    except (EOFError, KeyboardInterrupt):
        pass
