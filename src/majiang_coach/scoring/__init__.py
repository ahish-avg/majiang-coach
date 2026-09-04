"""scoring/:Phase 7 番种算分 + 完整结算(成都血战标准)。

  - rules:  FanRules 可调番表/封顶/底分/杠钱(DEFAULT_RULES 为成都标准口径)。
  - fan:    fan_of 纯函数番种识别 -> FanResult(番种列表/总番/封顶/倍数)。
  - ctx:    scan_win_contexts 事件流上下文(杠上开花/杠上炮/海底/天胡/地胡/抢杠)。
  - settle: settle_record 逐胡结算 + 杠钱 + 流局查叫 + 查花猪 -> SettleResult;
            per_seat 累计,不变式 sum(per_seat)==0。
  - result: SettleResult 及各笔结算的 to_dict/from_dict 往返一致。
"""

from __future__ import annotations

from .ctx import WinCtx, scan_win_contexts
from .fan import FanItem, FanResult, fan_of
from .result import (
    HuazhuPayment,
    KanPayment,
    SettleResult,
    TenpaiPayment,
    WinSettlement,
)
from .rules import DEFAULT_RULES, FanRules
from .settle import settle_record, tenpai_max_fan

__all__ = [
    "FanRules",
    "DEFAULT_RULES",
    "FanItem",
    "FanResult",
    "fan_of",
    "WinCtx",
    "scan_win_contexts",
    "settle_record",
    "tenpai_max_fan",
    "SettleResult",
    "WinSettlement",
    "KanPayment",
    "TenpaiPayment",
    "HuazhuPayment",
]
