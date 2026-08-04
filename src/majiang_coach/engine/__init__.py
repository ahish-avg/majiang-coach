"""血战到底 Game Engine(Phase 2):状态机 + 规则 + 牌谱。

核心算法层(Phase 1)零第三方依赖;本引擎模块同样零依赖,可被后端/小程序复用。
"""

from __future__ import annotations

from .wall import TileWall, WallExhausted
from .melds import Meld
from .action import (
    Action,
    discard,
    pon,
    ankan,
    daiminkan,
    shouminkan,
    tsumo,
    ron,
    ronkan,
    pass_action,
    swap,
    lack_action,
    legal_discards,
    legal_claims,
    legal_self_actions,
)
from .view import PlayerView
from .state import GameState
from .rules import resolve_claims, nearest_claimer, robbery_targets
from .apply import (
    apply_discard, apply_pon, apply_ankan, apply_daiminkan,
    apply_tsumo, apply_ron, apply_shouminkan,
)
from .record import GameRecord, FinalState, replay, make_meld_dict, meld_from_dict
from .settlement import build_result, WinnerInfo, LoserInfo, GameResult
from .game import Actor, RandomActor, Game

__all__ = [
    "TileWall", "WallExhausted", "Meld", "Action",
    "discard", "pon", "ankan", "daiminkan", "shouminkan", "tsumo", "ron",
    "ronkan", "pass_action", "swap", "lack_action",
    "legal_discards", "legal_claims", "legal_self_actions",
    "PlayerView", "GameState",
    "resolve_claims", "nearest_claimer", "robbery_targets",
    "apply_discard", "apply_pon", "apply_ankan", "apply_daiminkan",
    "apply_tsumo", "apply_ron", "apply_shouminkan",
    "GameRecord", "FinalState", "replay", "make_meld_dict", "meld_from_dict",
    "build_result", "WinnerInfo", "LoserInfo", "GameResult",
    "Actor", "RandomActor", "Game",
]
