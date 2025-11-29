from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from cecom.models import PlantaoCECOM

User = get_user_model()

class Command(BaseCommand):
    help = "Força o encerramento de qualquer plantão ativo de um usuário (ou de todos) sem validações." 

    def add_arguments(self, parser):
        parser.add_argument('--username', '-u', help='Username do usuário alvo (se omitido encerra todos os plantões ativos).')
        parser.add_argument('--dry-run', action='store_true', help='Apenas mostrar o que seria feito.')

    def handle(self, *args, **options):
        username = options.get('username')
        dry = options.get('dry_run')

        qs = PlantaoCECOM.objects.filter(ativo=True)
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"Usuário '{username}' não encontrado")
            qs = qs.filter(iniciado_por=user)

        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING('Nenhum plantão ativo encontrado para encerrar.'))
            return

        for plantao in qs:
            self.stdout.write(f"Encerrando plantão {plantao.id} iniciado por {plantao.iniciado_por.username}...")
            if not dry:
                plantao.ativo = False
                plantao.encerrado_em = timezone.now()
                plantao.save(update_fields=['ativo','encerrado_em'])

        if dry:
            self.stdout.write(self.style.SUCCESS(f"Dry-run concluído. {total} plantões seriam encerrados."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{total} plantão(ões) encerrado(s)."))
