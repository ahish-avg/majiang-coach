"""川麻血战核心算法 (Phase 1)。

核心算法层零第三方依赖:
- tiles:   牌表示 (索引 / 字符串码 / emoji 互转)
- hand:    手牌不可变结构
- decompose: 单门面子/搭子分解 (内部模块)
- win:     胡牌判定
- shanten: 向听数
- ukeire:  有效牌
- demo:    CLI demo
"""

__version__ = "0.1.0"
__all__ = ["tiles", "hand", "decompose", "win", "shanten", "ukeire"]
