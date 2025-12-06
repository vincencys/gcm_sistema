"""Wrapper mínimo: reexporta todas as views do módulo views_core."""

from .views_core import *  # noqa: F401,F403
from .views_pdf_token import (  # noqa: F401
    gerar_token_acesso_pdf,
    servir_documento_com_token,
)

__all__ = [name for name in globals().keys() if not name.startswith('_')]
