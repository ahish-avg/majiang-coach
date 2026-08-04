"""practice/store.py:内存会话存储 + idle TTL 清理(Phase 5,见计划 §5)。

session_id -> PracticeSession;无 DB(Phase 7/8 再持久化)。sweep_idle 清理超时会话。
线程安全(单进程 REST demo 足够;多进程/分布式留后续)。
"""

from __future__ import annotations

import threading
import time
import uuid

from ..llm import LLMConfig, resolve_llm_config
from .session import PracticeSession

__all__ = ["SessionStore"]

_DEFAULT_TTL = 1800.0  # 30 分钟 idle 超时


class SessionStore:
    """内存会话存储(session_id -> (PracticeSession, last_access))。"""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[PracticeSession, float]] = {}
        self._lock = threading.Lock()

    def create(
        self,
        ai_strengths: list[str] | None = None,
        hints_on: bool = False,
        llm_config: LLMConfig | None = None,
        weights: dict | None = None,
        seed: int | None = None,
    ) -> str:
        """创建会话,返回 session_id。"""
        sid = uuid.uuid4().hex[:12]
        actual_seed = seed if seed is not None else (int(time.time() * 1000) ^ hash(sid)) & 0x7FFFFFFF
        session = PracticeSession(
            ai_strengths=ai_strengths, hints_on=hints_on, llm_config=llm_config,
            weights=weights, seed=actual_seed, session_id=sid,
        )
        with self._lock:
            self._sessions[sid] = (session, time.time())
        return sid

    def get(self, sid: str) -> PracticeSession | None:
        with self._lock:
            entry = self._sessions.get(sid)
            if entry is None:
                return None
            session, _ = entry
            self._sessions[sid] = (session, time.time())
            return session

    def delete(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)

    def sweep_idle(self, ttl: float = _DEFAULT_TTL) -> int:
        """清理 idle 超时会话,返回清理数。"""
        now = time.time()
        removed = 0
        with self._lock:
            expired = [sid for sid, (_, ts) in self._sessions.items() if now - ts > ttl]
            for sid in expired:
                self._sessions.pop(sid, None)
                removed += 1
        return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
