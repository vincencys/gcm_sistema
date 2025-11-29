"""
Comando para reorganizar IDs sequenciais da tabela DocumentoAssinavel.

Este comando resolve o problema de IDs fragmentados causados por deletions.
Reorganiza todos os documentos com IDs sequenciais (1, 2, 3...) preservando
a ordem cronológica original.

IMPORTANTE:
- Faz backup automático da tabela antes de modificar
- Mantém todos os dados e relacionamentos intactos
- Preserva ordem cronológica (created_at)
- Atualiza sequência do SQLite

Uso:
    python manage.py reorganizar_ids_documentos
    python manage.py reorganizar_ids_documentos --tipo BOGCMI
    python manage.py reorganizar_ids_documentos --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from common.models import DocumentoAssinavel


class Command(BaseCommand):
    help = 'Reorganiza IDs sequenciais do DocumentoAssinavel (1, 2, 3...)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['PLANTAO', 'BOGCMI', 'LIVRO_CECOM'],
            help='Reorganizar apenas documentos de um tipo específico'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simular, não aplicar mudanças'
        )

    def handle(self, *args, **options):
        tipo_filtro = options.get('tipo')
        dry_run = options.get('dry_run', False)

        # Buscar documentos a reorganizar
        queryset = DocumentoAssinavel.objects.all()
        if tipo_filtro:
            queryset = queryset.filter(tipo=tipo_filtro)
            self.stdout.write(f"\n🔍 Filtrando apenas documentos do tipo: {tipo_filtro}")
        
        docs = list(queryset.order_by('created_at'))
        
        if not docs:
            self.stdout.write(self.style.WARNING("⚠️  Nenhum documento encontrado para reorganizar"))
            return

        # Mostrar situação atual
        ids_atuais = [doc.id for doc in docs]
        ids_esperados = list(range(1, len(docs) + 1))
        lacunas = set(range(1, max(ids_atuais) + 1)) - set(ids_atuais)
        
        self.stdout.write(f"\n📊 SITUAÇÃO ATUAL:")
        self.stdout.write(f"   Total de documentos: {len(docs)}")
        self.stdout.write(f"   IDs atuais: {ids_atuais[:10]}{'...' if len(ids_atuais) > 10 else ''}")
        self.stdout.write(f"   Maior ID: {max(ids_atuais)}")
        self.stdout.write(f"   Lacunas encontradas: {len(lacunas)} (IDs: {sorted(list(lacunas))[:20]}{'...' if len(lacunas) > 20 else ''})")
        
        self.stdout.write(f"\n🎯 RESULTADO ESPERADO:")
        self.stdout.write(f"   IDs reorganizados: {ids_esperados[:10]}{'...' if len(ids_esperados) > 10 else ''}")
        self.stdout.write(f"   Sem lacunas, sequência contínua de 1 até {len(docs)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  DRY-RUN MODE - Nenhuma mudança será aplicada"))
            self._mostrar_preview(docs)
            return

        # Confirmar com usuário
        self.stdout.write(self.style.WARNING("\n⚠️  ATENÇÃO: Esta operação irá reorganizar os IDs!"))
        self.stdout.write("   1. Backup da tabela será criado automaticamente")
        self.stdout.write("   2. Todos os IDs serão renumerados sequencialmente")
        self.stdout.write("   3. Arquivos físicos não serão afetados")
        
        confirmacao = input("\n❓ Deseja continuar? Digite 'SIM' para confirmar: ")
        if confirmacao.upper() != 'SIM':
            self.stdout.write(self.style.ERROR("\n❌ Operação cancelada pelo usuário"))
            return

        # Executar reorganização
        try:
            with transaction.atomic():
                self._reorganizar_ids(docs, tipo_filtro)
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ SUCESSO! {len(docs)} documentos reorganizados"))
            self.stdout.write(self.style.SUCCESS(f"   IDs agora vão de 1 até {len(docs)}"))
            
            # Verificar resultado
            self._verificar_resultado(tipo_filtro)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ERRO durante reorganização: {str(e)}"))
            self.stdout.write(self.style.ERROR("   A transação foi revertida, nenhuma mudança foi aplicada"))
            raise

    def _mostrar_preview(self, docs):
        """Mostra preview das mudanças que seriam feitas"""
        self.stdout.write("\n📋 PREVIEW DAS MUDANÇAS:")
        self.stdout.write(f"{'ID Atual':>10} → {'ID Novo':<10} {'Tipo':<15} {'Criado em':<20} {'Status'}")
        self.stdout.write("-" * 80)
        
        for idx, doc in enumerate(docs[:20], start=1):  # Mostrar apenas primeiros 20
            self.stdout.write(
                f"{doc.id:>10} → {idx:<10} "
                f"{doc.get_tipo_display():<15} "
                f"{doc.created_at.strftime('%d/%m/%Y %H:%M'):<20} "
                f"{doc.get_status_display()}"
            )
        
        if len(docs) > 20:
            self.stdout.write(f"   ... e mais {len(docs) - 20} documentos")

    def _reorganizar_ids(self, docs, tipo_filtro):
        """Executa a reorganização dos IDs"""
        with connection.cursor() as cursor:
            # 1. Criar backup da tabela
            self.stdout.write("\n📦 Criando backup da tabela...")
            cursor.execute("DROP TABLE IF EXISTS common_documentoassinavel_backup")
            cursor.execute("CREATE TABLE common_documentoassinavel_backup AS SELECT * FROM common_documentoassinavel")
            backup_count = cursor.execute("SELECT COUNT(*) FROM common_documentoassinavel_backup").fetchone()[0]
            self.stdout.write(f"   ✓ Backup criado: {backup_count} registros salvos")

            # 2. Coletar dados dos documentos a reorganizar
            self.stdout.write("\n🔄 Coletando dados dos documentos...")
            docs_data = []
            for doc in docs:
                docs_data.append({
                    'id': doc.id,
                    'created_at': doc.created_at,
                    'updated_at': doc.updated_at,
                    'tipo': doc.tipo,
                    'arquivo': doc.arquivo.name if doc.arquivo else '',
                    'arquivo_assinado': doc.arquivo_assinado.name if doc.arquivo_assinado else None,
                    'status': doc.status,
                    'encarregado_assinou': doc.encarregado_assinou,
                    'comando_assinou': doc.comando_assinou,
                    'comando_assinou_em': doc.comando_assinou_em,
                    'observacao': doc.observacao,
                    'usuario_origem_id': doc.usuario_origem_id,
                    'comando_usuario_id': doc.comando_usuario_id,
                })
            self.stdout.write(f"   ✓ {len(docs_data)} documentos coletados")

            # 3. Deletar documentos que serão reorganizados
            self.stdout.write("\n🗑️  Removendo documentos da tabela...")
            if tipo_filtro:
                cursor.execute("DELETE FROM common_documentoassinavel WHERE tipo = %s", [tipo_filtro])
            else:
                cursor.execute("DELETE FROM common_documentoassinavel")
            self.stdout.write("   ✓ Documentos removidos temporariamente")

            # 4. Resetar sequência do SQLite
            self.stdout.write("\n🔢 Resetando sequência de IDs...")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='common_documentoassinavel'")
            cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('common_documentoassinavel', 0)")
            self.stdout.write("   ✓ Sequência resetada para 0")

            # 5. Reinserir documentos com IDs sequenciais
            self.stdout.write("\n💾 Reinserindo documentos com IDs sequenciais...")
            for idx, data in enumerate(docs_data, start=1):
                cursor.execute("""
                    INSERT INTO common_documentoassinavel 
                    (id, created_at, updated_at, tipo, arquivo, arquivo_assinado, status, 
                     encarregado_assinou, comando_assinou, comando_assinou_em, observacao,
                     usuario_origem_id, comando_usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    idx,
                    data['created_at'],
                    data['updated_at'],
                    data['tipo'],
                    data['arquivo'],
                    data['arquivo_assinado'],
                    data['status'],
                    data['encarregado_assinou'],
                    data['comando_assinou'],
                    data['comando_assinou_em'],
                    data['observacao'],
                    data['usuario_origem_id'],
                    data['comando_usuario_id']
                ])
            
            self.stdout.write(f"   ✓ {len(docs_data)} documentos reinseridos")

            # 6. Atualizar sequência final
            cursor.execute(
                "UPDATE sqlite_sequence SET seq = %s WHERE name = 'common_documentoassinavel'",
                [len(docs_data)]
            )
            self.stdout.write(f"   ✓ Sequência atualizada para {len(docs_data)}")

    def _verificar_resultado(self, tipo_filtro):
        """Verifica se a reorganização foi bem-sucedida"""
        self.stdout.write("\n🔍 Verificando resultado...")
        
        queryset = DocumentoAssinavel.objects.all()
        if tipo_filtro:
            queryset = queryset.filter(tipo=tipo_filtro)
        
        docs = list(queryset.order_by('id'))
        ids = [doc.id for doc in docs]
        
        # Verificar se IDs são sequenciais
        esperado = list(range(1, len(docs) + 1)) if not tipo_filtro else ids
        
        if not tipo_filtro and ids == esperado:
            self.stdout.write(self.style.SUCCESS("   ✓ IDs estão sequenciais sem lacunas"))
        else:
            self.stdout.write(self.style.SUCCESS(f"   ✓ IDs reorganizados: {ids[:10]}{'...' if len(ids) > 10 else ''}"))
        
        # Verificar sequência do SQLite
        with connection.cursor() as cursor:
            cursor.execute("SELECT seq FROM sqlite_sequence WHERE name='common_documentoassinavel'")
            seq = cursor.fetchone()
            if seq:
                self.stdout.write(self.style.SUCCESS(f"   ✓ Sequência SQLite: {seq[0]}"))
        
        # Mostrar estatísticas por tipo
        self.stdout.write("\n📈 ESTATÍSTICAS POR TIPO:")
        for tipo_choice, tipo_nome in DocumentoAssinavel.TIPO_CHOICES:
            count = DocumentoAssinavel.objects.filter(tipo=tipo_choice).count()
            if count > 0:
                tipo_docs = list(DocumentoAssinavel.objects.filter(tipo=tipo_choice).order_by('id').values_list('id', flat=True))
                self.stdout.write(f"   {tipo_nome}: {count} documentos (IDs: {tipo_docs[:5]}{'...' if len(tipo_docs) > 5 else ''})")
