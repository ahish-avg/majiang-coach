"""settle.py:完整结算纯函数(Phase 7,成都血战标准)。

settle_record(record, rules=None) -> SettleResult:
  逐胡结算(自摸在局三家各付 / 点炮点炮者一人付 / 一炮多响分别赔)+ 杠钱
  (直杠点杠者付、补杠与暗杠在局三家付;抢杠不落地故不收)+ 流局查叫
  (未下叫非花猪者赔每个「下叫未胡」者其听牌理论最大番倍数)+ 查花猪
  (花猪赔其余三家各顶格;双花猪互赔自然抵消;3 胡终局不查叫但查花猪)。

已胡者退出后续一切支付/收取(血战);每笔收支配平,per_seat 累计恒满足
sum(per_seat.values()) == 0。

消费 engine/record.replay() 终局态 + 事件流上下文(scoring.ctx);不 import review/。
"""

from __future__ import annotations

from .. import tiles
from ..engine.melds import Meld
from ..engine.record import GameRecord, meld_from_dict, replay
from ..hand import Hand
from ..shanten import shanten
from ..ukeire import ukeire
from .ctx import scan_win_contexts
from .fan import FanResult, fan_of
from .result import (
    HuazhuPayment,
    KanPayment,
    SettleResult,
    TenpaiPayment,
    WinSettlement,
)
from .rules import DEFAULT_RULES, FanRules

__all__ = ["settle_record", "tenpai_max_fan"]

_KAN_RATE = {"ankan": "kan_ankan", "daiminkan": "kan_daiminkan", "shouminkan": "kan_shouminkan"}
_KAN_CN = {"ankan": "暗杠", "daiminkan": "直杠", "shouminkan": "补杠"}


def settle_record(record: GameRecord | dict, rules: FanRules | None = None) -> SettleResult:
    """一局牌谱 -> 完整结算 SettleResult(纯函数、确定性)。"""
    rules = rules or DEFAULT_RULES
    rec = record if isinstance(record, GameRecord) else GameRecord.from_dict(record)
    fs = replay(rec)
    events = rec.events
    ctxs = scan_win_contexts(events)

    res = SettleResult(drawn=fs.drawn, base_score=rules.base_score, rules_used=rules.to_dict())
    deltas = [0, 0, 0, 0]

    def transfer(payer: int, payee: int, amount: int) -> None:
        deltas[payer] -= amount
        deltas[payee] += amount

    active = [True, True, True, True]  # 在局(未胡);已胡者退出后续一切支付/收取

    def _is_robbery_target(i: int) -> bool:
        """补杠事件 i 是否被抢:后续紧邻 ron(robbery=True)以该杠座为 from。"""
        for j in range(i + 1, len(events)):
            ev2 = events[j]
            t2 = ev2["t"]
            if t2 in ("discard", "draw", "kan_draw", "pon", "kan", "ryuukyoku"):
                return False
            if t2 == "ron" and ev2.get("robbery") and ev2.get("from") == events[i]["seat"]:
                return True
        return False

    # ---- 1. 事件流顺序:杠钱即时 + 逐胡结算 ----
    ctx_by_index = {c.event_index: c for c in ctxs}
    for i, ev in enumerate(events):
        t = ev["t"]

        if t == "kan":
            seat = ev["seat"]
            kind = ev["kind"]
            rate = getattr(rules, _KAN_RATE[kind]) * rules.base_score
            robbed = kind == "shouminkan" and _is_robbery_target(i)
            if kind == "daiminkan":
                payers = [ev["from"]]
            else:
                payers = [s for s in range(4) if s != seat and active[s]]
            pay = KanPayment(
                seat=seat, kind=kind, tile=ev["tile"],
                payer_seats=tuple(payers), amount_each=rate,
            )
            if robbed:
                # 被抢杠:杠取消,杠钱不收(事件不落地)
                continue
            for p in payers:
                transfer(p, seat, rate)
            res.kans.append(pay)

        elif t in ("tsumo", "ron"):
            seat = ev["seat"]
            ctx = ctx_by_index[i]
            melds = [meld_from_dict(m) for m in ev.get("melds", [])]
            hand = [tiles.code_to_index(c) for c in ev.get("hand", [])]
            lack = ev.get("lack")
            fan = fan_of(hand, melds, lack, by=t, ctx=ctx, rules=rules)
            amount = fan.multiplier * rules.base_score
            if t == "tsumo":
                payers = tuple(s for s in range(4) if s != seat and active[s])
            else:
                payers = (ev["from"],)
            for p in payers:
                transfer(p, seat, amount)
            res.wins.append(WinSettlement(
                seat=seat, by=t, tile=ev["tile"], from_seat=ev.get("from"),
                fan=fan, payer_seats=payers, amount_each=amount,
            ))
            active[seat] = False

    # ---- 2. 流局查叫(3 胡终局不查叫)----
    if fs.drawn and len(fs.winners) < 3:
        _settle_tenpai(fs, rules, transfer, res)

    # ---- 3. 查花猪(流局 / 3 胡终局都查;含已胡者)----
    _settle_huazhu(fs, rules, transfer, res)

    res.per_seat = {s: deltas[s] for s in range(4)}
    assert res.total() == 0, f"结算收付不平: {res.per_seat}"
    return res


def _settle_tenpai(fs, rules: FanRules, transfer, res: SettleResult) -> None:
    """流局查叫:未下叫且非花猪者,赔每个下叫未胡者其听牌理论最大番倍数。"""
    waiters: list[tuple[int, Hand, list[Meld], int]] = []  # (seat, 待摸态 hand, melds, lack)
    noten: list[int] = []
    for s in range(4):
        if s in fs.winners:
            continue
        melds = fs.melds[s]
        lack = fs.lack[s]
        # 终局暗手张数 = 13-3k(该座最后动作是弃牌)或 14-3k(最后一摸未及打出)。
        # 统一规整为待摸态(13-3k):14 张时取弃一张后最优向听的那手牌。
        hand = Hand.from_indices(fs.hands[s])
        if len(hand.suits_present()) >= 3:
            continue  # 花猪:走查花猪,不参与查叫
        n_melds = len(melds)
        waiting = _to_waiting_hand(hand, melds, lack)
        if waiting is not None and shanten(waiting, lack, n_melds) == 0:
            waiters.append((s, waiting, melds, lack))
        else:
            noten.append(s)

    for payer in noten:
        for wait_seat, wait_hand, wait_melds, wait_lack in waiters:
            wait_codes, max_fan, mult = tenpai_max_fan(
                wait_hand, wait_melds, wait_lack, rules
            )
            amount = mult * rules.base_score
            transfer(payer, wait_seat, amount)
            res.tenpais.append(TenpaiPayment(
                payer=payer, wait_seat=wait_seat, wait_tiles=tuple(wait_codes),
                max_fan=max_fan, multiplier=mult, amount=amount,
            ))

def _to_waiting_hand(hand: Hand, melds: list[Meld], lack: int | None) -> Hand | None:
    """终局暗手 -> 待摸态(13-3k 张)。

    13-3k 张(最后动作是弃牌):原样返回;14-3k 张(最后一摸未打出):逐张弃牌,
    返回使向听最小的那手;张数异常返回 None(不参与下叫判定)。
    """
    n_melds = len(melds)
    n_wait = 13 - 3 * n_melds
    n_drawn = 14 - 3 * n_melds
    if hand.total == n_wait:
        return hand
    if hand.total != n_drawn:
        return None
    best: Hand | None = None
    best_s = 99
    for idx in hand.to_indices():
        h = hand.remove(idx)
        s = shanten(h, lack, n_melds)
        if s < best_s:
            best_s, best = s, h
            if s == -1:
                break
    return best


def tenpai_max_fan(hand: Hand, melds: list[Meld], lack: int | None,
                   rules: FanRules) -> tuple[list[str], int, int]:
    """听牌理论最大番:枚举待ち(ukeire),逐张模拟胡牌算番取最大。

    事件番(自摸/杠上开花/海底等)不计入理论牌型番;死叫(待ち牌已绝)仍算下叫,
    ukeire 只看牌型故候选仍在。
    返回 (待ち牌码列表, 最大番, 对应倍数)。
    """
    waits = ukeire(hand, lack, len(melds))
    best_fan = 0
    best_mult = 0
    for u in waits:
        fan = fan_of(hand.add(u.tile_index).to_indices(), melds, lack,
                     by="ron", ctx=None, rules=rules)
        if fan.total_fan > best_fan:
            best_fan = fan.total_fan
            best_mult = fan.multiplier
    return [u.code for u in waits], best_fan, best_mult


def _settle_huazhu(fs, rules: FanRules, transfer, res: SettleResult) -> None:
    """查花猪:花猪(终局未胡且仍持三门牌)赔其余三家各顶格。"""
    huazhu_seats: list[int] = []
    for s in range(4):
        if s in fs.winners:
            continue
        # 花猪 = 未胡且终局暗手仍三门(缺门未清);口径同 engine.settlement.build_result
        suits = {tiles.suit_of(t) for t in fs.hands[s]}
        if len(suits) >= 3:
            huazhu_seats.append(s)

    amount = rules.huazhu_pay * rules.base_score
    for hz in huazhu_seats:
        for payee in range(4):
            if payee == hz:
                continue
            transfer(hz, payee, amount)
            res.huazhus.append(HuazhuPayment(huazhu_seat=hz, payee=payee, amount=amount))
