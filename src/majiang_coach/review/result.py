"""review/result.py:ReviewStep / ReviewResult 数据结构与序列化(Phase 6,见计划 §6.2)。

ReviewStep 一个点评步骤(决策点):turn_action(刚摸待弃)/claim(他人弃牌申索)/
win(胡牌)/over(流局)。view 为 view_to_dict 序列化的 PlayerView;analysis 为 Phase 3
硬算;advice 为 Phase 4 AdviseResult.to_dict()(hints_on 时,失败含 error)。

to_dict/from_dict 往返一致,风格镜像 analysis/result.py。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ReviewStep", "ReviewResult"]

_PHASES = ("turn_action", "claim", "win", "over")


@dataclass
class ReviewStep:
    """一个复盘点评步骤。"""

    step: int
    event_index: int
    phase: str
    seat: int
    tile: str | None = None  # 摸到/弃牌/胡牌张(牌码)
    hand_total: int = 0
    actual_action: dict | None = None  # 实战动作 {kind, tile?, from?}
    view: dict | None = None           # view_to_dict 序列化 PlayerView
    analysis: dict | None = None       # Phase 3 AnalysisResult.to_dict()
    advice: dict | None = None         # Phase 4 AdviseResult.to_dict()(hints_on)
    comment: str = ""                  # 川麻口语点评
    fans: dict | None = None           # Phase 7 FanResult.to_dict()(win 步)
    score: dict | None = None          # Phase 7 本胡倍数/付款座(win 步)

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError(f"非法 phase:{self.phase!r},须为 {_PHASES}")

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "event_index": self.event_index,
            "phase": self.phase,
            "seat": self.seat,
            "tile": self.tile,
            "hand_total": self.hand_total,
            "actual_action": self.actual_action,
            "view": self.view,
            "analysis": self.analysis,
            "advice": self.advice,
            "comment": self.comment,
            "fans": self.fans,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewStep":
        return cls(
            step=d["step"],
            event_index=d["event_index"],
            phase=d["phase"],
            seat=d["seat"],
            tile=d.get("tile"),
            hand_total=d.get("hand_total", 0),
            actual_action=d.get("actual_action"),
            view=d.get("view"),
            analysis=d.get("analysis"),
            advice=d.get("advice"),
            comment=d.get("comment", ""),
            fans=d.get("fans"),
            score=d.get("score"),
        )


@dataclass
class ReviewResult:
    """一局完整复盘结果。"""

    meta: dict
    summary: dict
    steps: list[ReviewStep]

    def to_dict(self) -> dict:
        return {
            "meta": dict(self.meta),
            "summary": dict(self.summary),
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewResult":
        return cls(
            meta=dict(d.get("meta", {})),
            summary=dict(d.get("summary", {})),
            steps=[ReviewStep.from_dict(s) for s in d.get("steps", [])],
        )
