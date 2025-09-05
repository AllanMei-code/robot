"""
批量将 templates_kb.py 中的模板写入知识库（bot_store.db）。

运行方式（在项目根目录）：
  python backend/import_templates_to_kb.py

或（作为模块）：
  python -m backend.import_templates_to_kb
"""

from __future__ import annotations

import sys
from typing import Dict, Tuple

try:
    # 包内导入
    from .bot_store import init_db, upsert_qa
    from .templates_kb import TEMPLATES
except Exception:  # 兼容脚本路径运行
    from bot_store import init_db, upsert_qa  # type: ignore
    from templates_kb import TEMPLATES  # type: ignore


# 触发词（中文/法文）——用于知识库检索的“问题字段”
# 注意：中文采用简单分词，尽量用常见的短词/短语以提升 FTS 命中率
TRIGGERS: Dict[str, Tuple[str, str]] = {
    "withdraw_conditions": ("提现 条件 要求 满足", "retrait condition exigences"),
    "provide_game_account": ("游戏 账号 查询 提供", "compte de jeu verifier fournir"),
    "register_before_login": ("注册 成功 后 才能 登录", "inscription avant connexion"),
    "register_operator_phone": ("运营商号 电话 注册", "numero operateur telephone inscription"),
    "payment_unstable_try_more": ("支付 渠道 不稳定 多次 尝试 充值", "paiement canal instable essayer plusieurs fois"),
    "have_fun": ("玩得 愉快 欢迎", "amusez-vous bon jeu"),
    "find_in_withdraw_ui": ("提现 界面 找到 在哪 哪里", "trouver interface de retrait ou"),
    "check_withdraw_conditions": ("检查 满足 提现 条件 限制", "verifier conditions de retrait"),
    "check_deposit_ui": ("查看 充值 界面 内容", "verifier interface de recharge"),
    "feedback_to_operator": ("反馈 运营 通知", "signaler a l'operateur informer"),
    "apology_local_payment_unstable": ("本地 支付 环境 不稳定 充值 提现 道歉 改善", "environnement paiement instable recharges retraits desoles ameliorer"),
    "apology_operator_network_issue": ("运营商 网络 问题 充值 提现 无法", "reseau operateur probleme recharges retraits"),
    "need_participate_platform_activities": ("参加 平台 活动 完成 任务", "participer activites plateforme taches"),
    "complete_tasks_get_rewards": ("完成 任务 获得 奖励", "terminer taches recompenses"),
    "payment_unstable_wait": ("支付 渠道 不稳定 耐心 等待", "canaux paiement instables patienter"),
    "withdraw_issue_wait": ("提现 问题 卡住 等待 处理", "probleme retrait bloque patienter traitement"),
    "transaction_delay_48h": ("交易 延迟 48 小时 等待", "transactions retardees 48 heures"),
    "welcome_gamesawa": ("欢迎 gamesawa", "bienvenue gamesawa"),
    "describe_issue_detail": ("详细 描述 问题", "decrire en detail probleme"),
}


def main() -> None:
    init_db()

    inserted = 0
    skipped = 0

    for key, lang_map in TEMPLATES.items():
        zh = (lang_map.get("zh") or "").strip()
        if not zh:
            # 只导入有中文回复的模板
            skipped += 1
            continue

        q_zh, q_fr = TRIGGERS.get(key, (key.replace("_", " "), key.replace("_", " ")))

        # 若模板中自带法语答案，可作为法语检索词的补充
        fr_ans = (lang_map.get("fr") or "").strip()
        if fr_ans and len(fr_ans) < 200:
            q_fr = f"{q_fr} {fr_ans}"

        upsert_qa(q_fr=q_fr, q_zh=q_zh, a_zh=zh, source="template_seed")
        inserted += 1

    print(f"templates imported: {inserted}, skipped(no zh): {skipped}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"import failed: {e}")
        sys.exit(1)
