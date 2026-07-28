"""FastAPI demo:Phase 1 分析 + Phase 2 跑局牌谱。

核心算法层零第三方依赖;仅本模块依赖 fastapi/pydantic,便于后续迁移小程序后端。

本地运行:
    pip install -e ".[api]"
    uvicorn api.main:app --reload
    # POST http://127.0.0.1:8000/api/phase1/analyze
    # POST http://127.0.0.1:8000/api/phase2/play
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from majiang_coach.hand import Hand
from majiang_coach.tiles import code_to_index
from majiang_coach.shanten import shanten
from majiang_coach.ukeire import ukeire
from majiang_coach.win import win
from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.analysis import analyze as analyze_view, analysis_result_to_dict

_LACK_LETTER_TO_INT = {"m": 0, "s": 1, "p": 2}
_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}

app = FastAPI(title="majiang-coach", version="0.2.0")


class AnalyzeRequest(BaseModel):
    codes: list[str] = Field(..., description="牌码列表,元素可为单码或同门拼接(如 ['1m2m3m','5p5p'])")
    lack_suit: Literal["m", "s", "p"] | None = Field(
        None, description="指定缺门;留空则自动枚举最优缺门"
    )


class UkeireTileOut(BaseModel):
    tile_index: int
    code: str
    new_shanten: int


class AnalyzeResponse(BaseModel):
    total: int
    suits_present: list[str]
    lack_suit: str | None
    is_win: bool
    is_tenpai: bool
    shanten: int
    status_cn: str = Field(..., description="川麻口语状态:已胡牌 / 下叫(听牌) / 差 N 张下叫 / 没下叫")
    ukeire: list[UkeireTileOut]


@app.get("/")
def root() -> dict:
    return {
        "name": "majiang-coach",
        "version": "0.2.0",
        "endpoints": ["/api/phase1/analyze", "/api/phase2/play", "/api/phase3/analyze"],
    }


@app.post("/api/phase1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    lack = _LACK_LETTER_TO_INT[req.lack_suit] if req.lack_suit else None

    tokens: list[str] = []
    for c in req.codes:
        tokens.extend(c.split())
    if not tokens:
        raise HTTPException(status_code=400, detail="codes 为空")
    try:
        hand = Hand.from_codes(tokens)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total = hand.total
    is_win = win(hand, lack) if total == 14 else False
    s = shanten(hand, lack)
    u = ukeire(hand, lack) if total == 13 else []

    # 川麻口语状态
    if s == -1:
        status_cn = "已胡牌"
    elif s == 0:
        status_cn = "下叫(听牌)"
    elif s > 0:
        status_cn = f"差 {s} 张下叫"
    else:
        status_cn = "没下叫"

    return AnalyzeResponse(
        total=total,
        suits_present=[_SUIT_NAME[suit] for suit in sorted(hand.suits_present())],
        lack_suit=req.lack_suit,
        is_win=is_win,
        is_tenpai=(s == 0),
        shanten=s,
        status_cn=status_cn,
        ukeire=[
            UkeireTileOut(tile_index=t.tile_index, code=t.code, new_shanten=t.new_shanten)
            for t in u
        ],
    )


# ---- Phase 2: 跑局牌谱 ----

class PlayRequest(BaseModel):
    seed: int = Field(42, description="随机种子(决定整局牌墙与 AI 选择)")


class PlayResponse(BaseModel):
    record: dict = Field(..., description="完整牌谱(meta + 事件流 + 结果)")
    summary: dict = Field(..., description="人类可读摘要")


@app.post("/api/phase2/play", response_model=PlayResponse)
def play(req: PlayRequest) -> PlayResponse:
    """跑一局血战到底(4 随机 AI),返回结构化 JSON 牌谱与摘要。"""
    actors = [RandomActor(req.seed * 4 + i) for i in range(4)]
    game = Game(actors, req.seed)
    record = game.run()

    result = record.result or {}
    winners = result.get("winners", [])
    losers = result.get("losers", [])
    lack = record.meta.get("lack", [])
    summary = {
        "seed": req.seed,
        "swap_direction": record.meta.get("swap_direction"),
        "lack": [_SUIT_NAME.get(l, "?") for l in lack],
        "num_events": len(record.events),
        "winners": [
            {"seat": w["seat"], "by": w["by"], "tile": w["tile"],
             "from": w.get("from"), "robbery": w.get("robbery", False)}
            for w in winners
        ],
        "losers": [
            {"seat": l["seat"], "huazhu": l.get("huazhu", False)}
            for l in losers
        ],
        "drawn": result.get("drawn", False),
    }
    return PlayResponse(record=record.to_dict(), summary=summary)


# ---- Phase 3: 分析引擎(硬计算结构化输出) ----

class MeldIn(BaseModel):
    kind: Literal["pon", "ankan", "daiminkan", "shouminkan"] = "pon"
    tile: str = Field(..., description="牌码,如 5m")
    src: int | None = Field(None, description="来源座(碰/大明杠);暗杠/补杠为 null")


class Analyze3Request(BaseModel):
    codes: list[str] = Field(..., description="暗手牌码(单张或同门拼接)")
    lack_suit: Literal["m", "s", "p"] | None = Field(None, description="自家缺门")
    lack_suits: list[str | None] | None = Field(
        None, description="4 座公开缺门(m/s/p/null);留空则只用自家缺门"
    )
    melds: list[MeldIn] = Field(default_factory=list, description="自家副露")
    public_melds: list[list[MeldIn]] | None = Field(
        None, description="4 座公开副露(含自家);留空则仅含自家 melds"
    )
    discards: list[list[str]] | None = Field(
        None, description="4 座弃牌(牌码列表);留空则全空"
    )
    wall_remaining: int = Field(30, description="牌墙剩余")
    last_discard: str | None = Field(None, description="最近弃牌牌码(用于 13 张 claim)")
    last_discard_src: int | None = Field(1, description="最近弃牌来源座")
    active_seats: list[int] | None = Field(None, description="在局座;留空则全在局")
    weights: dict | None = Field(None, description='权重 {"offense":0.6,"defense":0.4}')


def _meld_in_to_meld(m: MeldIn) -> Meld:
    return Meld(kind=m.kind, tile=code_to_index(m.tile), src_seat=m.src)


@app.post("/api/phase3/analyze")
def analyze3(req: Analyze3Request) -> dict:
    """Phase 3 分析:输入座位视角 -> 结构化 AnalysisResult JSON。

    14 张(刚摸态)输出弃牌候选 + 推荐;13 张(待摸态)输出 hand + 可选 claim。
    """
    lack = _LACK_LETTER_TO_INT[req.lack_suit] if req.lack_suit else None

    tokens: list[str] = []
    for c in req.codes:
        tokens.extend(c.split())
    if not tokens:
        raise HTTPException(status_code=400, detail="codes 为空")
    try:
        hand = Hand.from_codes(tokens)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    my_melds = tuple(_meld_in_to_meld(m) for m in req.melds)

    if req.public_melds is not None:
        public_melds = tuple(
            tuple(_meld_in_to_meld(m) for m in seat) for seat in req.public_melds
        )
    else:
        public_melds = (my_melds, (), (), ())

    if req.discards is not None:
        discards = tuple(
            tuple(code_to_index(c) for c in d) for d in req.discards
        )
        if len(discards) != 4:
            raise HTTPException(status_code=400, detail="discards 须 4 座")
    else:
        discards = ((), (), (), ())

    if req.lack_suits is not None:
        if len(req.lack_suits) != 4:
            raise HTTPException(status_code=400, detail="lack_suits 须 4 座")
        lack_suits = tuple(
            _LACK_LETTER_TO_INT[ls] if ls else None for ls in req.lack_suits
        )
    elif lack is not None:
        lack_suits = (lack, lack, lack, lack)
    else:
        lack_suits = ()

    last_discard = None
    if req.last_discard:
        last_discard = (req.last_discard_src, code_to_index(req.last_discard))

    active = tuple(req.active_seats) if req.active_seats is not None else (0, 1, 2, 3)

    view = PlayerView(
        seat=0,
        hand=hand,
        melds=my_melds,
        lack_suit=lack,
        lack_suits=lack_suits,
        public_melds=public_melds,
        discards=discards,
        wall_remaining=req.wall_remaining,
        last_discard=last_discard,
        active_seats=active,
    )

    try:
        result = analyze_view(view, weights=req.weights)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return analysis_result_to_dict(result)
