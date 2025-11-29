from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from common.models import DocumentoAssinavel
from common.views import _append_assinatura, _nome_primeiro_ultimo
from pathlib import Path
from django.core.files.base import ContentFile
import sys

class Command(BaseCommand):
    help = "Regenera PDFs assinados que ficaram somente com a página de assinatura (adicionando novamente as páginas originais)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Apenas mostra o que faria, sem alterar arquivos.')
        parser.add_argument('--limit', type=int, help='Limita quantidade de documentos processados.')
        parser.add_argument('--min-size', type=int, default=7000, help='Tamanho mínimo esperado de um PDF mesclado (usado para detectar truncados).')
        parser.add_argument('--force', action='store_true', help='Regerar mesmo se já parecer OK (>= min-size).')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        limit = opts.get('limit')
        min_size = opts['min_size']
        force = opts['force']
        qs = DocumentoAssinavel.objects.filter(status='ASSINADO', arquivo_assinado__isnull=False)
        total = qs.count()
        self.stdout.write(f"Documentos assinados encontrados: {total}")
        processed = 0
        fixed = 0
        for doc in qs.order_by('-created_at'):
            if limit and processed >= limit:
                break
            processed += 1
            path_assinado = Path(doc.arquivo_assinado.path)
            size_assinado = path_assinado.stat().st_size if path_assinado.exists() else 0
            truncado = size_assinado < min_size
            if not force and not truncado:
                continue
            orig_path = Path(doc.arquivo.path)
            if not orig_path.exists():
                self.stderr.write(f"[SKIP] Doc {doc.id}: original inexistente: {orig_path}")
                continue
            self.stdout.write(f"[REGEN] Doc {doc.id} size_atual={size_assinado} truncado={truncado}")
            if dry:
                continue
            try:
                nome_full = doc.comando_usuario.get_full_name() if doc.comando_usuario else 'Comando'
                nome_assin = _nome_primeiro_ultimo(nome_full)
                perfil_cmd = getattr(doc.comando_usuario, 'perfil', None) if doc.comando_usuario else None
                # Padroniza título conforme tipo do documento: BOGCMI/BOGCM => "Despacho CMT/SUBCMT",
                # Livro CECOM => Administração; demais mantém o rótulo genérico.
                if doc.tipo in ('BOGCMI', 'BOGCM'):
                    titulo_padrao = 'Despacho CMT/SUBCMT'
                elif doc.tipo == 'LIVRO_CECOM':
                    titulo_padrao = 'Despacho / Assinatura da Administração'
                else:
                    titulo_padrao = 'Despacho / Assinatura do Comando/Sub Comando'

                novo_pdf = _append_assinatura(
                    str(orig_path),
                    None,
                    nome_assin,
                    titulo_assinatura=titulo_padrao,
                    matricula=getattr(perfil_cmd, 'matricula', None) if perfil_cmd else None,
                    cargo=getattr(perfil_cmd, 'cargo', None) if perfil_cmd else None,
                    classe=getattr(perfil_cmd, 'classe_legivel', None) if perfil_cmd else None,
                )
                # Checar se de fato aumentou páginas -> heurística pelo tamanho
                if len(novo_pdf) <= size_assinado and not force:
                    self.stderr.write(f"  -> Não aumentou tamanho (len={len(novo_pdf)}), mantendo original")
                    continue
                nome_base = path_assinado.name.replace('_assinado','_regen')
                doc.arquivo_assinado.save(nome_base, ContentFile(novo_pdf), save=False)
                with transaction.atomic():
                    doc.save(update_fields=['arquivo_assinado'])
                fixed += 1
                self.stdout.write(f"  -> OK novo_size={len(novo_pdf)}")
            except Exception as e:
                self.stderr.write(f"  -> ERRO: {e}")
        self.stdout.write(f"Concluído. Processados={processed} Regenerados={fixed}")
        if dry:
            self.stdout.write("(modo dry-run, nada alterado)")
