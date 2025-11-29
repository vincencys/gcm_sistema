from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from users.models import Perfil


class Command(BaseCommand):
    help = "Garante que todos os usuários tenham Perfil GCM ativo (para aparecerem nas seleções)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Inclui usuários inativos na sincronização (por padrão só usuários ativos).",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        if options.get("include_inactive"):
            users_qs = User.objects.all()
        else:
            users_qs = User.objects.filter(is_active=True)

        created = 0
        activated = 0
        updated = 0

        for u in users_qs.iterator():
            perfil, was_created = Perfil.objects.get_or_create(user=u)
            if was_created:
                created += 1

            # Marca ativo e preenche defaults úteis
            changed = False
            if perfil.ativo is not True:
                perfil.ativo = True
                activated += 1
                changed = True

            if not perfil.cargo:
                perfil.cargo = "Guarda Civil Municipal"
                changed = True

            if not perfil.matricula:
                # Usa username como matrícula quando vazio
                perfil.matricula = str(u.username or "")
                changed = True

            if changed:
                perfil.save()
                if not was_created:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Perfis criados: {created} | ativados: {activated} | atualizados: {updated}"
        ))
