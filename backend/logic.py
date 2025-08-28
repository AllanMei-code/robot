# -*- coding: utf-8 -*-
"""
最小可用的机器人知识匹配（命中返回中文答案；未命中返回空字符串）
留空字符串的意义：让上层逻辑去走 bot_store / 模型 / 默认兜底。
你可以按需扩展 rules。
"""

from typing import Dict, List

_RULES: Dict[str, str] = {
    # 关键词(小写) : 中文回答
    "注册": "您好，注册只需手机/邮箱即可完成，1分钟内通过验证码激活账号。",
    "登录": "您好，登录支持账号+密码或短信验证码。如忘记密码可在登录页找回。",
    "充值": "您好，充值支持银行卡、电子钱包等方式，实时到账，无手续费。",
    "提现": "您好，提现提交后一般 5-30 分钟到账，请确保账户已完成实名与绑定。",
    "优惠": "您好，当前有新手礼包与每日返利，详情请在“优惠活动”页面查看。",
    "规则": "您好，游戏规则可在对应游戏入口的“玩法说明”查看，简明易懂。",
    "安全": "您好，为保障账号安全，请开启二次验证并勿泄露验证码与密码。",
}

# 允许多关键词命中（任一命中即可）
_ALIASES: Dict[str, List[str]] = {
    "注册": ["开户", "开通"],
    "登录": ["登入", "登陆"],
    "充值": ["存款", "入金", "top up", "deposit"],
    "提现": ["取款", "出金", "withdraw"],
    "优惠": ["活动", "折扣", "返利", "bonus", "promotion"],
    "规则": ["玩法", "规则", "how to play"],
    "安全": ["账号安全", "风控", "安全"],
}

def get_bot_reply(text_zh: str) -> str:
    if not text_zh:
        return ""
    q = text_zh.strip().lower()
    # 直接命中
    for key, ans in _RULES.items():
        if key in q:
            return ans
    # 别名命中
    for canonical, words in _ALIASES.items():
        if any(w in q for w in words):
            return _RULES.get(canonical, "")
    return ""  # 未命中：留给上层兜底
