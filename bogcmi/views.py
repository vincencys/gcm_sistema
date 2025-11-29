"""Wrapper mínimo: reexporta todas as views do módulo views_core."""

from .views_core import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if not name.startswith('_')]
