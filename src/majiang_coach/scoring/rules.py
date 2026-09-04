"""FanRules:成都血战番表/封顶/底分/杠钱/退税开关(Phase 7)。

所有规则数字集中于可调 dataclass,默认值 = 计划 §已确认决策:
  倍数 = 2^(总番-1);平胡 1 番 = 1 倍;总番封顶 5 番 = 16 倍。
  杠钱即时结算、不乘翻倍:直杠 1 倍(点杠者付)、补杠 1 倍(在局三家付,
  被抢杠不收)、暗杠 2 倍(在局三家付)。
  流局查花猪:花猪赔其余三家各顶格(16 倍);退税 v0 不做(留 flag)。

风格镜像 ai/heuristic weights_used:to_dict() 回传实际生效数值。
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

__all__ = ["FanRules", "DEFAULT_RULES"]


@dataclass(frozen=True)
class FanRules:
    """番表与结算参数(全部可调,默认值 = 成都血战标准口径)。"""

    # ---- 牌型番 ----
    fan_duidui: int = 2       # 对对胡(碰碰胡)
    fan_qidui: int = 4        # 七对
    fan_long_qidui: int = 8   # 龙七对(与七对互斥;龙对那 4 张不再计根)
    fan_qingyise: int = 4     # 清一色
    fan_jingoudiao: int = 4   # 金勾钓(4 副露,暗手仅剩将)
    fan_yaojiu: int = 4       # 幺九(全 1/9,含将)
    fan_tianhu: int = 16      # 天胡(值即顶格)
    fan_dihu: int = 16        # 地胡(值即顶格)

    # ---- 事件番(累加)----
    fan_zimo: int = 1         # 自摸
    fan_kan_kaihua: int = 2   # 杠上开花
    fan_kan_dama: int = 2     # 杠上炮
    fan_qianggang: int = 2    # 抢杠胡
    fan_haidi: int = 2        # 海底捞月 / 海底炮
    fan_gen: int = 1          # 每根(4 张同牌 / 杠各 1 根)

    # ---- 封顶 / 底分 ----
    cap_fan: int = 5          # 总番封顶番数(5 番 = 16 倍)
    base_score: int = 1       # 底分(倍数 × 底分 = 实际收付单位)

    # ---- 杠钱(即时、不乘翻倍,单位 = 底分)----
    kan_daiminkan: int = 1    # 直杠:点杠者付 1 倍
    kan_shouminkan: int = 1   # 补杠:在局三家各付 1 倍(被抢杠不收)
    kan_ankan: int = 2        # 暗杠:在局三家各付 2 倍

    # ---- 流局 ----
    huazhu_pay: int = 16      # 查花猪:花猪赔其余三家各 16 倍(顶格)

    # ---- 预留(v0 不做)----
    refund_kan_on_draw: bool = False  # 退税(流局杠钱退还)

    def multiplier(self, total_fan: int) -> int:
        """总番 -> 倍数:2^(总番-1),封顶 cap_fan。"""
        fan = min(total_fan, self.cap_fan)
        return 1 << (fan - 1)

    @property
    def cap_multiplier(self) -> int:
        """封顶倍数(默认 16)。"""
        return 1 << (self.cap_fan - 1)

    def to_dict(self) -> dict:
        """实际生效参数(仿 weights_used)。"""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict | None) -> "FanRules":
        """dict -> FanRules;未知键抛 ValueError(防呆)。None = 默认规则。"""
        if d is None:
            return DEFAULT_RULES
        if not isinstance(d, dict):
            raise ValueError(f"rules 须为 dict,得到 {type(d).__name__}")
        allowed = {f.name for f in fields(cls)}
        unknown = set(d) - allowed
        if unknown:
            raise ValueError(f"未知 rules 键: {sorted(unknown)}")
        return replace(DEFAULT_RULES, **d)


DEFAULT_RULES = FanRules()
