from __future__ import annotations
from contextvars import ContextVar
from uuid import uuid4

run_id_var: ContextVar[str] = ContextVar("run_id", default=uuid4().hex)
user_var: ContextVar[str] = ContextVar("user", default="system")
session_var: ContextVar[str] = ContextVar("session", default="desktop")


def set_log_context(*, user: str | None = None, session: str | None = None) -> None:
    if user is not None:
        user_var.set(user)
    if session is not None:
        session_var.set(session)


def current_context() -> dict[str, str]:
    return {"run_id": run_id_var.get(), "user": user_var.get(), "session": session_var.get()}
