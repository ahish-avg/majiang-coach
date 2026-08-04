"""Advice / AdviseResult 数据类(Phase 4,见计划 §5)。

- Advice:LLM 结构化建议(recommended_tile + 4 段理由/教学/读牌)。
- AdviseResult:advise() 顶层结果(硬算 analysis 始终有 + 可选 advice + 开关/错误/模型)。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Advice", "AdviseResult"]


@dataclass(frozen=True)
class Advice:
    """LLM 解释出的结构化建议(已过防幻觉校验)。"""

    recommended_tile: str | None
    offense_reason: str
    defense_reason: str
    teaching_point: str
    opponent_read: str

    def to_dict(self) -> dict:
        return {
            "recommended_tile": self.recommended_tile,
            "offense_reason": self.offense_reason,
            "defense_reason": self.defense_reason,
            "teaching_point": self.teaching_point,
            "opponent_read": self.opponent_read,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Advice":
        return cls(
            recommended_tile=d["recommended_tile"],
            offense_reason=d["offense_reason"],
            defense_reason=d["defense_reason"],
            teaching_point=d["teaching_point"],
            opponent_read=d["opponent_read"],
        )


@dataclass(frozen=True)
class AdviseResult:
    """advise() 顶层结果。analysis(硬算)任何分支都返回。"""

    analysis: dict            # Phase 3 AnalysisResult.to_dict()(硬算,始终有)
    advice: Advice | None     # hints_on=false 或失败时 None
    hints_on: bool
    error: str | None         # 失败原因;成功 null
    model_used: str | None

    def to_dict(self) -> dict:
        return {
            "analysis": self.analysis,
            "advice": self.advice.to_dict() if self.advice is not None else None,
            "hints_on": self.hints_on,
            "error": self.error,
            "model_used": self.model_used,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdviseResult":
        return cls(
            analysis=d["analysis"],
            advice=Advice.from_dict(d["advice"]) if d.get("advice") else None,
            hints_on=d["hints_on"],
            error=d.get("error"),
            model_used=d.get("model_used"),
        )
