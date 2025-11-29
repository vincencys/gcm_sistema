from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = (
        "Cria o grupo 'Pânico — Assistidas' (se não existir) e adiciona a "
        "permissão panic.view_assistida. Opcionalmente, adiciona usuários ao grupo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group-name",
            default="Pânico — Assistidas",
            help="Nome do grupo a ser criado/atualizado.",
        )
        parser.add_argument(
            "--add-users",
            nargs="*",
            default=[],
            help="Usernames para adicionar ao grupo (opcional)",
        )

    def handle(self, *args, **options):
        group_name = options["group_name"]
        usernames = options["add_users"]

        # Localiza a permissão padrão de view do modelo Assistida
        try:
            from panic.models import Assistida  # import local para evitar problemas de app loading
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Falha ao importar Assistida: {e}"))
            return

        ct = ContentType.objects.get_for_model(Assistida)
        perm_codename = "view_assistida"
        try:
            perm = Permission.objects.get(content_type=ct, codename=perm_codename)
        except Permission.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    "Permissão 'panic.view_assistida' não encontrada. Rode as migrações e tente novamente."
                )
            )
            return

        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Grupo criado: {group_name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Grupo já existia: {group_name}"))

        group.permissions.add(perm)
        self.stdout.write(self.style.SUCCESS("Permissão 'panic.view_assistida' atribuída ao grupo."))

        added = []
        for uname in usernames:
            try:
                u = User.objects.get(username=uname)
            except User.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"Usuário não encontrado: {uname}"))
                continue
            u.groups.add(group)
            added.append(uname)

        if added:
            self.stdout.write(self.style.SUCCESS(f"Usuários adicionados ao grupo: {', '.join(added)}"))
        else:
            self.stdout.write("Nenhum usuário adicionado. Use --add-users para adicionar.")
