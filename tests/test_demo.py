"""smoke tests for majiang_coach.demo"""

from majiang_coach.demo import analyze, main
from majiang_coach.hand import Hand


def test_analyze_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    out = analyze(h, emoji=False)
    assert "是否胡牌: 是" in out
    assert "已胡牌" in out


def test_analyze_tenpai_machi():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    out = analyze(h, emoji=False)
    assert "下叫(听牌)" in out
    assert "叫牌" in out
    assert "5s" in out


def test_analyze_one_shanten_with_lack():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"])
    out = analyze(h, lack_suit=2, emoji=False)
    assert "差 1 张下叫" in out
    assert "进张" in out
    assert "5p" not in out.split("进张")[1]  # 缺门牌不在进张中


def test_main_returns_zero_and_prints(capsys):
    rc = main(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s", "--no-emoji"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "下叫(听牌)" in captured.out
    assert "5s" in captured.out


def test_main_invalid_codes_returns_two(capsys):
    rc = main(["0m", "1z"])
    assert rc == 2


# ---- Phase 2 demo_game ----

from majiang_coach.demo_game import main as demo_game_main, summarize  # noqa: E402
from majiang_coach.engine.game import Game, RandomActor  # noqa: E402


def test_demo_game_main(capsys):
    rc = demo_game_main(["42"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "种子 42" in captured.out
    assert "事件数" in captured.out


def test_demo_game_json(capsys):
    rc = demo_game_main(["7", "--json"])
    assert rc == 0
    import json
    captured = capsys.readouterr()
    s = json.loads(captured.out)
    assert s["seed"] == 7
    assert "winners" in s and "losers" in s


def test_demo_game_summarize():
    record = Game([RandomActor(i) for i in range(4)], 1).run()
    s = summarize(record)
    assert s["seed"] == 1
    assert len(s["winners"]) + len(s["losers"]) == 4


# ---- Phase 3 demo_analyze ----

from majiang_coach.demo_analyze import main as demo_analyze_main  # noqa: E402


def test_demo_analyze_14tile(capsys):
    rc = demo_analyze_main(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s", "--lack", "p"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "弃牌候选" in captured.out
    assert "推荐弃牌" in captured.out


def test_demo_analyze_13tile_claim(capsys):
    rc = demo_analyze_main(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m",
                            "--lack", "p", "--last-discard", "5m"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "申索" in captured.out
    assert "可胡(ron)" in captured.out


def test_demo_analyze_json(capsys):
    rc = demo_analyze_main(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s",
                            "--lack", "p", "--json"])
    assert rc == 0
    import json
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["hand_total"] == 14
    assert "candidates" in body
    assert body["weights_used"]["offense"] == 0.6


def test_demo_analyze_melds(capsys):
    rc = demo_analyze_main(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s",
                            "--lack", "p", "--pon", "5m"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "副露 1 副" in captured.out


def test_demo_analyze_invalid_codes(capsys):
    rc = demo_analyze_main(["zz"])
    assert rc == 2
