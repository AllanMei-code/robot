# -*- coding: utf-8 -*-
"""
基于 OpenAI 兼容接口的 LLM 机器人适配层：
- 为每个会话（cid）维护独立的多轮上下文
- 返回中文回复，便于上层统一做多语言翻译
"""

from __future__ import annotations

from typing import Dict, List
from openai import OpenAI
import os, logging

# 可通过环境变量或直接在此处配置网关（默认对齐本机/标准别名）
BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
API_KEY = os.getenv("LLM_API_KEY", "sk-noauth")
MODEL = os.getenv("LLM_MODEL", "qwen2.5-3b-instruct-q5_k_m")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
logging.getLogger(__name__).info(
    "[LLM] base_url=%s model=%s (set via env LLM_BASE_URL/LLM_MODEL)", BASE_URL, MODEL
)

SYSTEM_PROMPT = (
    "你是一名在线博彩游戏客服，名字叫「Leo」，24小时在线，精通法语、英语、斯瓦希里语。\n"
    "职责：只回答与网站内「注册、登录、充值、提现、优惠、游戏规则、账号安全」相关的常见问题。\n"
    "要求：你就是真正的客服；无法解决的问题，让用户留下邮箱。\n"
    "充值/提现不到账：请让玩家提供游戏号和时间，回复“请耐心等待，这笔交易正在处理中。”，并让玩家留下邮箱。\n"
    "输出：简短、口语化；默认使用中文输出（上层会统一翻译给客户端）。\n"
    "禁止：不要暴露自己是 AI/机器人；不要出现“根据政策”等字样。\n"
    "只输出最终给用户看的回复文本，不要输出任何分析、解释或标签。\n"
)


def _extract_message(raw: str) -> str:
    if not raw:
        return ""
    tag = "<|message|>"
    idx = raw.rfind(tag)
    if idx != -1:
        return raw[idx + len(tag):].strip()
    return raw.strip()


# 每个会话独立上下文
_messages_by_cid: Dict[str, List[Dict[str, str]]] = {}


def reply_zh(cid: str, user_text_zh: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
    cid = cid or "default"
    if cid not in _messages_by_cid:
        _messages_by_cid[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if not user_text_zh:
        return ""

    history = _messages_by_cid[cid]
    history.append({"role": "user", "content": user_text_zh})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=history,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    raw = resp.choices[0].message.content or ""
    out = _extract_message(raw)
    history.append({"role": "assistant", "content": out})

    # 历史裁剪：保留 system + 最近 12 轮（24 条）
    if len(history) > 25:
        _messages_by_cid[cid] = [history[0]] + history[-24:]
    return out
