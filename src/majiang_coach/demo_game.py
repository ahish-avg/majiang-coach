"""demo_game:跑一局 4 随机 AI 血战到底,打印牌谱摘要。

用法:
    python -m majiang_coach.demo_game [seed]
    python -m majiang_coach.demo_game 42 --full   # 打印完整事件流

核心引擎零依赖;本 CLI 仅用标准库。
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine.game import Game, RandomActor
from .engine.record import replay

_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}
_SWAP_NAME = {"cw": "顺时针", "ccw": "逆时针", "across": "对家"}


def summarize(record) -> dict:
    """从 GameRecord 提取人类可读摘要。"""
    meta = record.meta
    result = record.result or {}
    winners = result.get("winners", [])
    losers = result.get("losers", [])
    lack_names = [_SUIT_NAME.get(l, "?") for l in meta.get("lack", [])]
    return {
        "seed": meta.get("seed"),
        "swap_direction": _SWAP_NAME.get(meta.get("swap_direction"), "?"),
        "lack": lack_names,
        "num_events": len(record.events),
        "winners": [
            {"seat": w["seat"], "by": w["by"], "tile": w["tile"],
             "from": w.get("from"), "robbery": w.get("robbery", False),
             "melds": len(w.get("melds", []))}
            for w in winners
        ],
        "losers": [
            {"seat": l["seat"], "huazhu": l.get("huazhu", False),
             "melds": len(l.get("melds", []))}
            for l in losers
        ],
        "drawn": result.get("drawn", False),
    }


def print_summary(record) -> None:
    s = summarize(record)
    print(f"种子 {s['seed']} | 换三张:{s['swap_direction']} | 缺门:{' '.join(s['lack'])}")
    print(f"事件数:{s['num_events']}")
    if s["winners"]:
        for w in s["winners"]:
            extra = []
            if w["from"] is not None:
                extra.append(f"点炮座{w['from']}")
            if w["robbery"]:
                extra.append("抢杠")
            by = "自摸" if w["by"] == "tsumo" else "点炮"
            print(f"  胡家 座{w['seat']}:{by} {w['tile']} 副露{w['melds']} {' '.join(extra)}")
    else:
        print("  无胡家")
    for l in s["losers"]:
        tag = " 花猪" if l["huazhu"] else ""
        print(f"  输家 座{l['seat']}:副露{l['melds']}{tag}")
    print(f"流局:{'是' if s['drawn'] else '否'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="跑一局血战到底(4 随机 AI)")
    parser.add_argument("seed", type=int, nargs="?", default=42, help="随机种子")
    parser.add_argument("--full", action="store_true", help="打印完整 JSON 牌谱")
    parser.add_argument("--json", action="store_true", help="打印摘要 JSON")
    args = parser.parse_args(argv)

    actors = [RandomActor(args.seed * 4 + i) for i in range(4)]
    game = Game(actors, args.seed)
    record = game.run()

    if args.full:
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(summarize(record), ensure_ascii=False, indent=2))
    else:
        print_summary(record)

    # 回放校验(自检)
    fs = replay(record)
    assert fs.winners == [w["seat"] for w in (record.result or {}).get("winners", [])]
    return 0


if __name__ == "__main__":
    sys.exit(main())
