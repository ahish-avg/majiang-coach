"""tests for llm/advisor.py(Phase 4,见计划 §3/§6/§8.6)。

覆盖 6 条兜底链:
  1. hints_on=false -> advice=None, error=None。
  2. config 不可用 -> advice=None, error=未配置。
  3. provider.chat 抛 LLMError -> advice=None, error=str(e)。
  4. 解析失败 -> advice=None, error=非 JSON。
  5. 防幻觉拦截(recommended_tile 不符)。
  6. 成功 -> Advice。
另:13 张待摸态(recommended_tile 强制 null);analysis 始终==analyze(view).to_dict();
解耦断言(llm/ 不 import win/shanten/ukeire)。
"""

from __future__ import annotations

import json
import re
import pathlib

import pytest

from majiang_coach.analysis import analyze
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand
from majiang_coach.llm import advisor
from majiang_coach.llm.config import LLMConfig
from majiang_coach.llm.provider import LLMError
from majiang_coach.llm.result import AdviseResult
from majiang_coach.llm.advisor import advise
from majiang_coach.tiles import code_to_index

_CFG = LLMConfig("https://x", "sk-key", "demo-model")


def _view14():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    return PlayerView(
        seat=0, hand=h, melds=(), lack_suit=2, lack_suits=(2, 2, 2, 2),
        public_melds=((), (), (), ()), discards=((), (), (), ()),
        wall_remaining=30, active_seats=(0, 1, 2, 3),
    )


def _view13():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"])
    return PlayerView(
        seat=0, hand=h, melds=(), lack_suit=2, lack_suits=(2, 2, 2, 2),
        public_melds=((), (), (), ()), discards=((), (), (), ()),
        wall_remaining=30, active_seats=(0, 1, 2, 3),
        last_discard=(1, code_to_index("5m")),
    )


def _rec_code(view) -> str:
    return analyze(view).recommend.code


def _advice_content(recommended_tile, **kw):
    d = {
        "recommended_tile": recommended_tile,
        "offense_reason": kw.get("offense_reason", "进攻理由"),
        "defense_reason": kw.get("defense_reason", "防守理由"),
        "teaching_point": kw.get("teaching_point", "教学点"),
        "opponent_read": kw.get("opponent_read", "对手读牌"),
    }
    return json.dumps(d, ensure_ascii=False)


def _set_chat(monkeypatch, fn):
    monkeypatch.setattr(advisor, "chat", fn)


# ---- 1. hints_on=false ----

def test_hints_off_no_advice_no_error():
    res = advise(_view14(), hints_on=False)
    assert res.hints_on is False
    assert res.advice is None
    assert res.error is None
    assert res.model_used is None
    assert res.analysis["hand_total"] == 14


def test_hints_off_analysis_equals_analyze():
    v = _view14()
    res = advise(v, hints_on=False)
    assert res.analysis == analyze(v).to_dict()


# ---- 2. config 不可用 ----

def test_no_config_returns_error(monkeypatch):
    # 确保 chat 不被调用
    _set_chat(monkeypatch, lambda *a, **k: pytest.fail("chat 不应被调用"))
    res = advise(_view14(), hints_on=True, llm_config=None)
    assert res.advice is None
    assert "未配置" in res.error
    assert res.model_used is None
    assert res.analysis["hand_total"] == 14


# ---- 3. provider.chat 抛 LLMError ----

def test_chat_llmerror_returns_error_no_key(monkeypatch):
    def fake(messages, config, json_mode=True):
        raise LLMError("LLM HTTP 401")
    _set_chat(monkeypatch, fake)
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert "401" in res.error
    assert res.model_used == "demo-model"


def test_chat_timeout_error(monkeypatch):
    _set_chat(monkeypatch, lambda *a, **k: (_ for _ in ()).throw(LLMError("LLM 请求超时(12.0s)")))
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert "超时" in res.error


# ---- 4. 解析失败 ----

def test_non_json_content(monkeypatch):
    _set_chat(monkeypatch, lambda *a, **k: "这不是 JSON,也没有大括号")
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert res.error == "LLM 输出非 JSON"


def test_text_with_embedded_json_parses(monkeypatch):
    v = _view14()
    rec = _rec_code(v)
    content = f"好的,这是我的建议:\n```json\n{_advice_content(rec)}\n```\n以上。"
    _set_chat(monkeypatch, lambda *a, **k: content)
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is not None
    assert res.advice.recommended_tile == rec


def test_json_missing_fields(monkeypatch):
    _set_chat(monkeypatch, lambda *a, **k: json.dumps({"recommended_tile": "1m", "offense_reason": "x"}))
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert res.error == "LLM 输出非 JSON"


def test_json_wrong_types(monkeypatch):
    _set_chat(monkeypatch, lambda *a, **k: json.dumps({
        "recommended_tile": 5, "offense_reason": "x", "defense_reason": "y",
        "teaching_point": "z", "opponent_read": "w",
    }))
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None


# ---- 5. 防幻觉拦截 ----

def test_antihallucination_mismatch(monkeypatch):
    v = _view14()
    rec = _rec_code(v)
    wrong = "9p" if rec != "9p" else "1p"
    _set_chat(monkeypatch, lambda *a, **k: _advice_content(wrong))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert "防幻觉" in res.error


def test_antihallucination_null_tile_discard(monkeypatch):
    # 14 张弃牌态:LLM 返回 null recommended_tile -> 拦截
    _set_chat(monkeypatch, lambda *a, **k: _advice_content(None))
    res = advise(_view14(), hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert "防幻觉" in res.error


def test_antihallucination_match_normalizes(monkeypatch):
    v = _view14()
    rec = _rec_code(v)
    # 带空格 + 大写 -> 规范化后应通过
    tile = f" {rec.upper()} "
    _set_chat(monkeypatch, lambda *a, **k: _advice_content(tile))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is not None
    assert res.error is None
    # advice 中保留 LLM 原样(未规整化),仅校验阶段做比对
    assert res.advice.recommended_tile.strip().lower() == rec.strip().lower()


# ---- 6. 成功 ----

def test_success_returns_advice(monkeypatch):
    v = _view14()
    rec = _rec_code(v)
    _set_chat(monkeypatch, lambda *a, **k: _advice_content(
        rec, offense_reason="弃后下叫", defense_reason="现物稍安全",
        teaching_point="学综合权衡", opponent_read="下家缺筒"))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is not None
    assert res.advice.recommended_tile == rec
    assert res.advice.offense_reason == "弃后下叫"
    assert res.error is None
    assert res.hints_on is True
    assert res.model_used == "demo-model"
    assert res.analysis == analyze(v).to_dict()


def test_success_advise_result_roundtrip():
    a = AdviseResult(
        analysis={"seat": 0}, advice=None, hints_on=False, error=None, model_used=None
    )
    d = a.to_dict()
    assert AdviseResult.from_dict(d) == a


# ---- 13 张待摸态 ----

def test_wait_state_forces_null_tile_no_validation(monkeypatch):
    v = _view13()
    assert analyze(v).recommend is None
    # LLM 即便返回一个 tile,也强制 null 且不触发防幻觉
    _set_chat(monkeypatch, lambda *a, **k: _advice_content("5m"))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is not None
    assert res.advice.recommended_tile is None  # 强制 null
    assert res.error is None
    assert res.analysis["recommend"] is None
    assert res.analysis["claim"] is not None


def test_wait_state_null_tile_accepted(monkeypatch):
    v = _view13()
    _set_chat(monkeypatch, lambda *a, **k: _advice_content(None))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is not None
    assert res.advice.recommended_tile is None
    assert res.error is None


def test_analysis_always_returned_on_failure(monkeypatch):
    v = _view13()
    _set_chat(monkeypatch, lambda *a, **k: (_ for _ in ()).throw(LLMError("LLM HTTP 500")))
    res = advise(v, hints_on=True, llm_config=_CFG)
    assert res.advice is None
    assert res.analysis == analyze(v).to_dict()


# ---- 解耦:llm/ 不 import win/shanten/ukeire ----

def test_llm_decoupled_from_rules():
    import majiang_coach.llm as llm_pkg
    pkg_dir = pathlib.Path(llm_pkg.__file__).parent
    import_re = re.compile(r"^\s*(from\s+\S+\s+import\b|import\s+\S+)", re.M)
    forbidden = re.compile(r"\b(win|shanten|ukeire)\b")
    offenders = []
    for f in sorted(pkg_dir.glob("*.py")):
        text = f.read_text(encoding="utf-8")
        for m in import_re.finditer(text):
            line = text[m.start():text.find("\n", m.start())]
            if forbidden.search(line):
                offenders.append((f.name, line.strip()))
    assert not offenders, f"llm/ 包违规导入规则引擎: {offenders}"


def test_llm_imports_allowed_only():
    # llm/ 允许 import analysis(含 analyze)与 engine.view;不允许直接 import 规则模块
    import majiang_coach.llm.context as ctx
    import majiang_coach.llm.advisor as adv
    assert hasattr(ctx, "build_context")
    assert hasattr(adv, "advise")
