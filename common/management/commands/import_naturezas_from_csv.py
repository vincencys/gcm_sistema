from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import NaturezaOcorrencia
from taloes.services import sync_codigos_from_naturezas


REQUIRED_COLUMNS = {"grupo", "grupo_nome", "codigo", "titulo"}


class Command(BaseCommand):
    help = (
        "Importa/atualiza Naturezas de Ocorrência a partir de um CSV e sincroniza "
        "os Códigos de Ocorrência (app taloes).\n\n"
        "CSV esperado com cabeçalho: grupo,grupo_nome,codigo,titulo,ativo(opcional).\n"
        "- grupo: nome curto do grupo (ex.: ALFA, BRAVO, ...).\n"
        "- grupo_nome: descrição do grupo (ex.: OCORRÊNCIA CONTRA PESSOAS).\n"
        "- codigo: sigla do código (ex.: A-01).\n"
        "- titulo: descrição do código.\n"
        "- ativo: 1/true/yes para ativo; vazio/0/false para inativo (opcional; padrão=1).\n"
    )

    def add_arguments(self, parser):  # pragma: no cover - interface de CLI
        parser.add_argument("csv_path", help="Caminho do arquivo CSV com os códigos de ocorrência")
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Marcar como inativas as naturezas que não estiverem presentes no CSV. "
                "(Não remove; apenas seta ativo=False.)"
            ),
        )

    def _iter_rows(self, path: Path) -> Iterable[dict]:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise CommandError("CSV sem cabeçalho.")
            cols = {c.strip().lower() for c in reader.fieldnames if c}
            missing = REQUIRED_COLUMNS - cols
            if missing:
                raise CommandError(f"CSV faltando colunas obrigatórias: {', '.join(sorted(missing))}")
            for row in reader:
                # normalizar chaves para minúsculas e tirar espaços
                norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
                yield norm

    @transaction.atomic
    def handle(self, *args, **opts):  # pragma: no cover - integra com banco
        csv_path = Path(opts["csv_path"]).resolve()
        if not csv_path.exists():
            raise CommandError(f"Arquivo não encontrado: {csv_path}")

        deactivate_missing = bool(opts.get("deactivate-missing"))

        self.stdout.write(self.style.NOTICE(f"Lendo {csv_path}…"))
        seen_codigos: set[str] = set()
        created = updated = 0

        for row in self._iter_rows(csv_path):
            grupo = row.get("grupo", "").strip()
            grupo_nome = row.get("grupo_nome", "").strip()
            codigo = row.get("codigo", "").strip()
            titulo = row.get("titulo", "").strip()
            ativo_raw = (row.get("ativo", "") or "1").strip().lower()
            ativo = ativo_raw in ("1", "true", "t", "yes", "y", "sim", "s")

            if not (grupo and grupo_nome and codigo and titulo):
                # Ignora linhas incompletas silenciosamente (útil quando há separadores ou rodapés)
                continue

            seen_codigos.add(codigo)

            obj, created_flag = NaturezaOcorrencia.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "grupo": grupo,
                    "grupo_nome": grupo_nome,
                    "titulo": titulo,
                    "ativo": ativo,
                },
            )
            if created_flag:
                created += 1
            else:
                updates = []
                if obj.grupo != grupo:
                    obj.grupo = grupo; updates.append("grupo")
                if obj.grupo_nome != grupo_nome:
                    obj.grupo_nome = grupo_nome; updates.append("grupo_nome")
                if obj.titulo != titulo:
                    obj.titulo = titulo; updates.append("titulo")
                if obj.ativo != ativo:
                    obj.ativo = ativo; updates.append("ativo")
                if updates:
                    obj.save(update_fields=list(set(updates)))
                    updated += 1

        if deactivate_missing:
            inativados = NaturezaOcorrencia.objects.exclude(codigo__in=seen_codigos).update(ativo=False)
            self.stdout.write(self.style.WARNING(f"Naturezas marcadas como inativas (ausentes no CSV): {inativados}"))

        # Sincronizar com os modelos de talões
        g_count, c_count = sync_codigos_from_naturezas()

        self.stdout.write(self.style.SUCCESS(
            f"Importação concluída. Criados: {created}, Atualizados: {updated}. "
            f"Sincronizados -> Grupos: {g_count}, Códigos: {c_count}."
        ))
