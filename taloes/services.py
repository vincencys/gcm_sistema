from __future__ import annotations

from typing import Tuple

from django.db import transaction

from common.models import NaturezaOcorrencia
from .models import GrupoOcorrencia, CodigoOcorrencia


@transaction.atomic
def sync_codigos_from_naturezas() -> Tuple[int, int]:
    """
    Sincroniza NaturezaOcorrencia (app common) para
    GrupoOcorrencia/CodigoOcorrencia (app taloes).

    - Cria/atualiza grupos (nome=grupo, descricao=grupo_nome)
    - Cria/atualiza códigos (sigla=codigo, descricao=titulo)
    - Considera apenas naturezas com `ativo=True`

    Retorna (grupos_atualizados_ou_criados, codigos_atualizados_ou_criados).
    """
    g_count = 0
    c_count = 0

    for n in NaturezaOcorrencia.objects.filter(ativo=True):
        g_nome = (n.grupo or "").strip() or (n.grupo_nome or "").strip() or "GRUPO"
        g_desc = (n.grupo_nome or "").strip()

        grupo, created_g = GrupoOcorrencia.objects.get_or_create(
            nome=g_nome,
            defaults={"descricao": g_desc},
        )
        if created_g:
            g_count += 1
        else:
            if (grupo.descricao or "") != g_desc:
                grupo.descricao = g_desc
                grupo.save(update_fields=["descricao"])
                g_count += 1

        codigo, created_c = CodigoOcorrencia.objects.get_or_create(
            sigla=n.codigo,
            defaults={"descricao": n.titulo, "grupo": grupo},
        )
        if created_c:
            c_count += 1
        else:
            updates = []
            if (codigo.descricao or "") != (n.titulo or ""):
                codigo.descricao = n.titulo
                updates.append("descricao")
            if codigo.grupo_id != grupo.id:
                codigo.grupo = grupo
                updates.append("grupo")
            if updates:
                codigo.save(update_fields=updates)
                c_count += 1

    return g_count, c_count
