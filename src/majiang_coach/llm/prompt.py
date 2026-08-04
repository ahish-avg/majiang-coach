"""build_messages(context) -> OpenAI 消息列表(Phase 4,见计划 §5)。

SYSTEM_PROMPT 含防幻觉铁律(强制引用注入数字、recommended_tile 约束、川麻口语、
教学导向、对手读牌仅可见信息、严格 JSON 输出 schema)。user 消息注入 context JSON。
"""

from __future__ import annotations

import json

__all__ = ["SYSTEM_PROMPT", "build_messages"]

SYSTEM_PROMPT = """你是川麻血战到底教练。铁律:
1. 只能用下方「分析数据」中的数字,严禁自创向听数/进张/危险度/未见张。
2. recommended_tile 必须等于 分析数据.recommend.code(弃牌态);待摸态为 null。
3. 用川麻口语(下叫/进张/现物/壁/碰杠/缺门/点炮/自摸)。
4. 教学导向:解释为何这样打,让用户学思路,不替打。
5. 对手读牌只基于可见信息(弃牌/副露/缺门),不得编造他家暗手。
6. 严格输出 JSON:{recommended_tile:str|null, offense_reason:str, defense_reason:str, teaching_point:str, opponent_read:str}。"""


def build_messages(context: dict) -> list[dict]:
    """system(铁律+输出 schema) + user(context JSON)。"""
    user_content = (
        "以下是当前局面的分析数据(JSON),请严格基于其中数字给出建议:\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
