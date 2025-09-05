# -*- coding: utf-8 -*-
"""
最小可用的机器人知识匹配（命中返回中文答案；未命中返回空字符串）
留空字符串的意义：让上层逻辑去走 bot_store / 模型 / 默认兜底。
你可以按需扩展 rules。
"""

from typing import Dict, List, Optional
import logging
import re

# 可选模板渲染
try:
    from .templates_kb import render_template
except Exception:
    from templates_kb import render_template

_RULES: Dict[str, str] = {
    # 关键字（小写）: 中文回答
    "注册": "您好，注册只需手机号/邮箱即可完成，几分钟内通过验证码激活账号。",
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

# 基于用户输入（已在上层翻译为中文 msg_zh）的模板匹配规则
TEMPLATE_PATTERNS: Dict[str, List[str]] = {
    "withdraw_conditions": [r"提现.*条件", r"条件.*提现", r"提现.*要求", r"满足.*提现"],
    "provide_game_account": [r"游戏(账?号|账户|ID)", r"提供.*账号", r"发.*账号", r"查.*账号"],
    "register_before_login": [r"(无法|不能|没法).*登录", r"登录.*(失败|不了|不行)", r"先.*注册.*(才能|再).*登录"],
    "register_operator_phone": [r"运营商号.*注册", r"(手机号|电话号).*(注册)", r"注册.*(运营商|手机号|电话)"],
    "payment_unstable_try_more": [r"(支付|充值|通道).*(不稳定|失败|繁忙|错误)", r"充值.*(不到账|延迟)"],
    "have_fun": [r"(玩得?开心|愉快)", r"祝.*(愉快|开心)", r"加油"],
    "find_in_withdraw_ui": [r"(在哪|哪里|怎么).*找.*提现", r"提现.*在哪里", r"提现界面"],
    "check_withdraw_conditions": [r"(无法|不能|没法).*提现", r"提现.*(失败|被拒|受限|限制)"],
    "check_deposit_ui": [r"(充值界面)", r"(怎么|如何).*充值", r"充值.*在哪里"],
    "feedback_to_operator": [r"(反馈|上报|报告|联系).*(运营|客服)", r"(投诉|建议).*运营"],
    "apology_local_payment_unstable": [r"(充值|提现).*(不稳定|问题|异常)", r"支付.*(不稳定|异常)"],
    "apology_operator_network_issue": [r"(运营商|运营).*网络.*(问题|异常)"],
    "need_participate_platform_activities": [r"(参加|参与).*活动", r"平台.*任务"],
    "complete_tasks_get_rewards": [r"完成.*任务.*(奖励|赠)", r"怎么.*奖励"],
    "payment_unstable_wait": [r"(支付|充值|通道).*(不稳定|维护|延迟).*等待", r"请.*等待"],
    "withdraw_issue_wait": [r"提现.*(卡住|排队|等待|审核)", r"提现.*(延迟|慢)"],
    "transaction_delay_48h": [r"(延迟|延时|要多久|多久).*(交易|到账)", r"48\s*小时", r"两天"],
    "welcome_gamesawa": [r"^(你好|您好|hello|hi|嗨|bonjour).*$", r"gamesawa", r"欢迎"],
    # 作为兜底提示：请详细描述问题
    "describe_issue_detail": [r"(不明白|看不懂|怎么回事|出问题了|有问题)", r"帮忙.*(看看|处理)"]
}

def _match_template_key(text_zh: str) -> Optional[str]:
    t = (text_zh or "").strip().lower()
    if not t:
        return None
    for key, pats in TEMPLATE_PATTERNS.items():
        for pat in pats:
            try:
                if re.search(pat, t, flags=re.I):
                    return key
            except re.error:
                continue
    return None


def get_bot_reply(text_zh: str, conv_id: Optional[str] = None) -> str:
    if not text_zh:
        return ""
    q = text_zh.strip().lower()
    # 模板优先匹配（根据中文输入生成固定回复）
    key = _match_template_key(q)
    if key:
        try:
            out = render_template(key, 'zh')
            if out:
                return out
        except Exception:
            pass
    # 直接命中
    for key, ans in _RULES.items():
        if key in q:
            return ans
    # 别名命中
    for canonical, words in _ALIASES.items():
        if any(w in q for w in words):
            return _RULES.get(canonical, "")
    # 未命中：调用 LLM 机器人做兜底（中文回复）
    try:
        try:
            from .llm_bot import reply_zh  # 包内导入
        except Exception:
            from llm_bot import reply_zh   # 兼容脚本方式运行
        logging.info("[BOT] fallback to LLM for reply (conv_id=%s)", conv_id)
        return reply_zh(conv_id or "default", text_zh)
    except Exception:
        return ""  # 若模型不可用，则仍由上层继续兜底
