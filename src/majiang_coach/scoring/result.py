"""result.py:SettleResult 结算数据结构与 to_dict/from_dict(Phase 7)。

一局完整结算:
  - wins:     逐胡(自摸/点炮/一炮多响),含番种 FanResult 与本胡收付。
  - kans:     杠钱(直/补/暗;抢杠不落地,故不出现)。
  - tenpais:  流局查叫(未下叫赔下叫未胡者的听牌理论最大番倍数)。
  - huazhus:  查花猪(花猪赔其余三家各顶格;3 胡终局也查)。
  - per_seat: 四座累计收付(底分单位;不变式 sum==0)。

to_dict/from_dict 往返一致;风格镜像 review/result.py。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .fan import FanResult

__all__ = [
    "WinSettlement", "KanPayment", "TenpaiPayment", "HuazhuPayment",
    "SettleResult",
]


@dataclass(frozen=True)
class WinSettlement:
    """一次胡牌结算(一炮多响时每位赢家各一条)。"""

    seat: int
    by: str                       # "tsumo" | "ron"
    tile: str                     # 胡牌张(牌码)
    from_seat: int | None
    fan: FanResult
    payer_seats: tuple[int, ...]  # 付款座(自摸=在局三家;点炮=点炮者)
    amount_each: int              # 每付款座应付(倍数 × 底分)

    def to_dict(self) -> dict:
        return {
            "seat": self.seat,
            "by": self.by,
            "tile": self.tile,
            "from": self.from_seat,
            "fan": self.fan.to_dict(),
            "payer_seats": list(self.payer_seats),
            "amount_each": self.amount_each,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WinSettlement":
        return cls(
            seat=d["seat"],
            by=d["by"],
            tile=d["tile"],
            from_seat=d.get("from"),
            fan=FanResult.from_dict(d["fan"]),
            payer_seats=tuple(d.get("payer_seats", [])),
            amount_each=d.get("amount_each", 0),
        )


@dataclass(frozen=True)
class KanPayment:
    """一笔杠钱。"""

    seat: int                     # 杠牌者(收款)
    kind: str                     # ankan/daiminkan/shouminkan
    tile: str
    payer_seats: tuple[int, ...]
    amount_each: int              # 每付款座应付(底分单位,不乘翻倍)

    def to_dict(self) -> dict:
        return {
            "seat": self.seat,
            "kind": self.kind,
            "tile": self.tile,
            "payer_seats": list(self.payer_seats),
            "amount_each": self.amount_each,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KanPayment":
        return cls(
            seat=d["seat"],
            kind=d["kind"],
            tile=d["tile"],
            payer_seats=tuple(d.get("payer_seats", [])),
            amount_each=d.get("amount_each", 0),
        )


@dataclass(frozen=True)
class TenpaiPayment:
    """流局查叫一笔:未下叫座 payer 赔给下叫未胡座 wait_seat。"""

    payer: int
    wait_seat: int
    wait_tiles: tuple[str, ...]   # 听牌(待ち)
    max_fan: int
    multiplier: int               # 听牌理论最大番对应倍数
    amount: int                   # = multiplier × 底分

    def to_dict(self) -> dict:
        return {
            "payer": self.payer,
            "wait_seat": self.wait_seat,
            "wait_tiles": list(self.wait_tiles),
            "max_fan": self.max_fan,
            "multiplier": self.multiplier,
            "amount": self.amount,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TenpaiPayment":
        return cls(
            payer=d["payer"],
            wait_seat=d["wait_seat"],
            wait_tiles=tuple(d.get("wait_tiles", [])),
            max_fan=d.get("max_fan", 0),
            multiplier=d.get("multiplier", 0),
            amount=d.get("amount", 0),
        )


@dataclass(frozen=True)
class HuazhuPayment:
    """查花猪一笔:花猪赔对方(含已胡者)顶格。"""

    huazhu_seat: int
    payee: int
    amount: int

    def to_dict(self) -> dict:
        return {"huazhu_seat": self.huazhu_seat, "payee": self.payee, "amount": self.amount}

    @classmethod
    def from_dict(cls, d: dict) -> "HuazhuPayment":
        return cls(huazhu_seat=d["huazhu_seat"], payee=d["payee"], amount=d["amount"])


@dataclass
class SettleResult:
    """一局完整结算。"""

    wins: list[WinSettlement] = field(default_factory=list)
    kans: list[KanPayment] = field(default_factory=list)
    tenpais: list[TenpaiPayment] = field(default_factory=list)
    huazhus: list[HuazhuPayment] = field(default_factory=list)
    per_seat: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0, 2: 0, 3: 0})
    drawn: bool = False
    base_score: int = 1
    rules_used: dict = field(default_factory=dict)

    def total(self) -> int:
        """四座收付之和(不变式:恒为 0)。"""
        return sum(self.per_seat.values())

    def to_dict(self) -> dict:
        return {
            "wins": [w.to_dict() for w in self.wins],
            "kans": [k.to_dict() for k in self.kans],
            "tenpais": [t.to_dict() for t in self.tenpais],
            "huazhus": [h.to_dict() for h in self.huazhus],
            "per_seat": {str(s): self.per_seat[s] for s in range(4)},
            "drawn": self.drawn,
            "base_score": self.base_score,
            "rules_used": dict(self.rules_used),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SettleResult":
        per = d.get("per_seat", {})
        return cls(
            wins=[WinSettlement.from_dict(w) for w in d.get("wins", [])],
            kans=[KanPayment.from_dict(k) for k in d.get("kans", [])],
            tenpais=[TenpaiPayment.from_dict(t) for t in d.get("tenpais", [])],
            huazhus=[HuazhuPayment.from_dict(h) for h in d.get("huazhus", [])],
            per_seat={s: int(per.get(str(s), per.get(s, 0))) for s in range(4)},
            drawn=d.get("drawn", False),
            base_score=d.get("base_score", 1),
            rules_used=dict(d.get("rules_used", {})),
        )
