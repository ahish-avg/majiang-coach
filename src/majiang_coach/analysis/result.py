"""AnalysisResult 序列化聚合(Phase 3,见计划 §4/§7/§9)。

to_dict/from_dict 方法定义在各数据类自身(自包含,避免循环导入);本模块聚合
顶层 `analysis_result_to_dict` / `analysis_result_from_dict` 供 API/demo/测试复用,
并验证往返一致。
"""

from __future__ import annotations

from .recommend import AnalysisResult

__all__ = ["analysis_result_to_dict", "analysis_result_from_dict"]


def analysis_result_to_dict(result: AnalysisResult) -> dict:
    """AnalysisResult -> JSON 就绪 dict(具名数字字段,供 Phase 4 LLM 强制引用)。"""
    return result.to_dict()


def analysis_result_from_dict(d: dict) -> AnalysisResult:
    """JSON dict -> AnalysisResult(往返一致)。"""
    return AnalysisResult.from_dict(d)
