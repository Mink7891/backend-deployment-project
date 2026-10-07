"""Public factory for CLI workers and tests; registrations live in dependencies."""

from app.dependencies.dispatcher_register import build_dispatcher

__all__ = ["build_dispatcher"]
