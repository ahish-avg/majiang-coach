"""tests for majiang_coach.tiles"""

import pytest

from majiang_coach import tiles
from majiang_coach.tiles import (
    ALL_INDICES,
    NUM_TILES,
    SUIT_LETTERS,
    SUIT_NAMES,
    TILE_CODES,
    code_to_index,
    codes_to_indices,
    index_to_code,
    index_to_emoji,
    indices_to_codes,
    number_of,
    parse_code_string,
    suit_of,
)


def test_constants():
    assert NUM_TILES == 27
    assert len(TILE_CODES) == 27
    assert len(ALL_INDICES) == 27
    assert SUIT_LETTERS == ("m", "s", "p")
    assert SUIT_NAMES == ("万", "条", "筒")
    # 顺序:1m..9m, 1s..9s, 1p..9p
    assert TILE_CODES[0] == "1m"
    assert TILE_CODES[8] == "9m"
    assert TILE_CODES[9] == "1s"
    assert TILE_CODES[17] == "9s"
    assert TILE_CODES[18] == "1p"
    assert TILE_CODES[26] == "9p"


@pytest.mark.parametrize("idx,code", [
    (0, "1m"), (8, "9m"),
    (9, "1s"), (17, "9s"),
    (18, "1p"), (26, "9p"),
    (4, "5m"), (13, "5s"), (22, "5p"),
])
def test_index_code_roundtrip(idx, code):
    assert index_to_code(idx) == code
    assert code_to_index(code) == idx


def test_full_roundtrip_all_27():
    for idx in range(27):
        assert code_to_index(index_to_code(idx)) == idx


def test_suit_and_number():
    for idx in range(9):
        assert suit_of(idx) == 0
    for idx in range(9, 18):
        assert suit_of(idx) == 1
    for idx in range(18, 27):
        assert suit_of(idx) == 2
    assert number_of(0) == 1
    assert number_of(8) == 9
    assert number_of(26) == 9


def test_emoji_codepoints():
    # 万 U+1F019.., 条 U+1F007.., 筒 U+1F010..
    assert index_to_emoji(0) == chr(0x1F019)   # 1m
    assert index_to_emoji(8) == chr(0x1F021)   # 9m
    assert index_to_emoji(9) == chr(0x1F007)   # 1s
    assert index_to_emoji(17) == chr(0x1F00F)  # 9s
    assert index_to_emoji(18) == chr(0x1F010)  # 1p
    assert index_to_emoji(26) == chr(0x1F018)  # 9p


@pytest.mark.parametrize("bad", ["0m", "1z", "1x", "m1", "10m", "9M", "", "  ", "abc"])
def test_invalid_codes_raise(bad):
    with pytest.raises(ValueError):
        code_to_index(bad)


def test_invalid_index_raises():
    with pytest.raises(ValueError):
        index_to_code(-1)
    with pytest.raises(ValueError):
        index_to_code(27)
    with pytest.raises(ValueError):
        index_to_emoji(27)


@pytest.mark.parametrize("s,expected", [
    ("1m", [0]),
    ("1m2m3m", [0, 1, 2]),
    ("5p5p", [22, 22]),
    ("9m1s1p", [8, 9, 18]),
    ("", []),
])
def test_parse_code_string(s, expected):
    assert parse_code_string(s) == expected


@pytest.mark.parametrize("bad", ["0m", "1z", "1x", "m1", "10m", "1mm", "1m2x", "12m"])
def test_parse_code_string_invalid(bad):
    with pytest.raises(ValueError):
        parse_code_string(bad)


def test_codes_to_indices_flattens():
    assert codes_to_indices(["1m2m3m", "5p5p"]) == [0, 1, 2, 22, 22]
    assert codes_to_indices(["1m", "2m", "3m"]) == [0, 1, 2]
    assert codes_to_indices([]) == []


def test_indices_to_codes():
    assert indices_to_codes([0, 1, 2, 22, 22]) == ["1m", "2m", "3m", "5p", "5p"]


def test_whitespace_tolerated():
    assert code_to_index(" 1m ") == 0
    assert parse_code_string("  1m2m3m  ") == [0, 1, 2]
