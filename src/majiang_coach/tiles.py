"""牌表示:索引 / 字符串码 / emoji 互转 + 常量。

血战到底只用万/条/筒三门,各 1-9 共 27 种牌型 × 4 张 = 108 张。无字牌、无宝牌。

索引映射(内部用长度 27 的计数数组):
    0-8   万 (1m-9m)   suit 0
    9-17  条 (1s-9s)   suit 1
    18-26 筒 (1p-9p)   suit 2

字符串码采用标准麻将字母码:`m`=万(man) / `s`=条(sou,竹) / `p`=筒(pin,点)。
注意:是标准麻将字母码,不是拼音首字母。

本模块为零第三方依赖纯函数,可被后续任意层(含小程序后端)复用。
"""

from __future__ import annotations

import re

__all__ = [
    "SUIT_LETTERS",
    "SUIT_NAMES",
    "NUM_TILES",
    "ALL_INDICES",
    "TILE_CODES",
    "suit_of",
    "number_of",
    "index_to_code",
    "code_to_index",
    "index_to_emoji",
    "parse_code_string",
    "codes_to_indices",
    "indices_to_codes",
]

# 三门牌:0=万 1=条 2=筒
SUIT_LETTERS: tuple[str, ...] = ("m", "s", "p")
SUIT_NAMES: tuple[str, ...] = ("万", "条", "筒")

NUM_TILES = 27
ALL_INDICES: tuple[int, ...] = tuple(range(NUM_TILES))

# TILE_CODES[idx] -> 字符串码;按 索引顺序生成:1m..9m, 1s..9s, 1p..9p
TILE_CODES: list[str] = [
    f"{n + 1}{SUIT_LETTERS[s]}" for s in range(3) for n in range(9)
]

_CODE_TO_INDEX: dict[str, int] = {code: idx for idx, code in enumerate(TILE_CODES)}

# Unicode Mahjong Tiles 牌面起始码点:
#   万(characters) U+1F019..  条(bamboos) U+1F007..  筒(circles) U+1F010..
_SUIT_EMOJI_BASE: tuple[int, ...] = (0x1F019, 0x1F007, 0x1F010)

# 单张牌码正则:[1-9] + 门字母
_TOKEN_RE = re.compile(r"([1-9])([msp])")


def suit_of(idx: int) -> int:
    """索引 -> 门 (0=万 1=条 2=筒)。"""
    return idx // 9


def number_of(idx: int) -> int:
    """索引 -> 牌点数 (1-9)。"""
    return idx % 9 + 1


def index_to_code(idx: int) -> str:
    """索引(0-26) -> 字符串码。越界抛 ValueError。"""
    if not isinstance(idx, int) or not (0 <= idx < NUM_TILES):
        raise ValueError(f"Invalid tile index: {idx!r}")
    return TILE_CODES[idx]


def code_to_index(code: str) -> int:
    """字符串码(如 "1m") -> 索引。非法码抛 ValueError。"""
    if not isinstance(code, str):
        raise ValueError(f"Invalid tile code: {code!r}")
    code = code.strip()
    idx = _CODE_TO_INDEX.get(code)
    if idx is None:
        raise ValueError(f"Invalid tile code: {code!r}")
    return idx


def index_to_emoji(idx: int) -> str:
    """索引 -> Unicode 麻将牌 emoji(🀙🀇🀐 等)。越界抛 ValueError。"""
    if not isinstance(idx, int) or not (0 <= idx < NUM_TILES):
        raise ValueError(f"Invalid tile index: {idx!r}")
    return chr(_SUIT_EMOJI_BASE[idx // 9] + idx % 9)


def parse_code_string(s: str) -> list[int]:
    """解析(可能拼接的)牌码字符串为索引列表。

    支持:
        "1m"        -> [0]
        "1m2m3m"    -> [0, 1, 2]   (同门连续牌码拼接)
        "5p5p"      -> [22, 22]    (对子拼接)
        ""          -> []

    任意非法字符(如 "0m"、"1z"、"1x"、"m1"、"10m")抛 ValueError。
    """
    if not isinstance(s, str):
        raise ValueError(f"Invalid tile code string: {s!r}")
    s = s.strip()
    if not s:
        return []
    indices: list[int] = []
    pos = 0
    for m in _TOKEN_RE.finditer(s):
        if m.start() != pos:
            raise ValueError(f"Invalid tile code string {s!r} at position {pos}")
        indices.append(_CODE_TO_INDEX[m.group(0)])
        pos = m.end()
    if pos != len(s):
        raise ValueError(f"Invalid tile code string {s!r}: trailing characters at {pos}")
    return indices


def codes_to_indices(codes) -> list[int]:
    """将牌码列表(元素可为单码或拼接码)展平为索引列表。

    例: ["1m2m3m", "5p5p"] -> [0, 1, 2, 22, 22]
    """
    out: list[int] = []
    for c in codes:
        out.extend(parse_code_string(c))
    return out


def indices_to_codes(indices) -> list[str]:
    """索引列表 -> 牌码列表(每张一个码,保持顺序)。"""
    return [index_to_code(i) for i in indices]
