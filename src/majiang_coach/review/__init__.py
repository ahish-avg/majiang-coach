"""review/:Phase 6 复盘系统(牌谱逐步回放 + AI 点评)。

输入一个 GameRecord(JSON 事件流),输出结构化 ReviewResult:
  - ReviewCursor:事件流增量回放(与 engine/record.replay() 一致),逐步重建该座可见
    PlayerView(信息隔离,不含他家暗手)。
  - review_record:纯函数编排(每决策点 Phase 3 analyze + 可选 Phase 4 advise,
    hints_on 开关;按座汇总;seat_focus 限定)。
  - comment.py:川麻口语点评文案(第 N 巡/差 X 张下叫/下叫/叫牌/自摸/点炮/抢杠)。
  - result.py:ReviewStep/ReviewResult + to_dict/from_dict 往返一致。
"""

from __future__ import annotations

from .comment import (
    shanten_cn, build_turn_comment, build_claim_comment, build_win_comment,
)
from .cursor import ReviewCursor
from .result import ReviewStep, ReviewResult
from .review import review_record

__all__ = [
    "ReviewCursor",
    "ReviewStep",
    "ReviewResult",
    "review_record",
    "shanten_cn",
    "build_turn_comment",
    "build_claim_comment",
    "build_win_comment",
]
