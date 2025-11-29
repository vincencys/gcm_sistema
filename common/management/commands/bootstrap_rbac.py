from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


ALMOX_APP = "almoxarifado"


GROUPS = {
    "AGENTE": {
        # Visualização básica de bens e suas movimentações
        "permissions": [
            f"{ALMOX_APP}.view_bempatrimonial",
            f"{ALMOX_APP}.view_movimentacaocautela",
            f"{ALMOX_APP}.view_cautelapermanente",
        ]
    },
    "ALMOXARIFE": {
        "permissions": [
            # Bens
            f"{ALMOX_APP}.view_bempatrimonial",
            # Movimentações de cautela
            f"{ALMOX_APP}.view_movimentacaocautela",
            f"{ALMOX_APP}.add_movimentacaocautela",
            f"{ALMOX_APP}.change_movimentacaocautela",
            f"{ALMOX_APP}.entregar_cautela",
            f"{ALMOX_APP}.devolver_cautela",
            # Estoque
            f"{ALMOX_APP}.view_movimentacaoestoque",
            f"{ALMOX_APP}.add_movimentacaoestoque",
            f"{ALMOX_APP}.change_movimentacaoestoque",
            f"{ALMOX_APP}.movimentar_estoque",
        ]
    },
    "SUPERVISOR": {
        "permissions": [
            # Visão ampla
            f"{ALMOX_APP}.view_bempatrimonial",
            f"{ALMOX_APP}.view_movimentacaocautela",
            f"{ALMOX_APP}.view_movimentacaoestoque",
            f"{ALMOX_APP}.view_cautelapermanente",
            # Aprovação e desbloqueios
            f"{ALMOX_APP}.aprovar_cautela",
            f"{ALMOX_APP}.desbloquear_excecao",
        ]
    },
    "AUDITORIA": {
        "permissions": [
            # Somente leitura
            f"{ALMOX_APP}.view_bempatrimonial",
            f"{ALMOX_APP}.view_movimentacaocautela",
            f"{ALMOX_APP}.view_movimentacaoestoque",
            f"{ALMOX_APP}.view_cautelapermanente",
            f"{ALMOX_APP}.ver_livro_municao",
            f"{ALMOX_APP}.ver_auditoria",
        ]
    },
    "ADMINISTRADOR": {
        # Vai receber 'todas' as permissões do app almoxarifado
        "permissions": "__ALL_APP_PERMS__",
    },
}


class Command(BaseCommand):
    help = "Cria grupos e permissões padrão (RBAC) para o Almoxarifado"

    def handle(self, *args, **options):
        # Mapa de todas as permissões do app almoxarifado
        almox_cts = ContentType.objects.filter(app_label=ALMOX_APP)
        all_almox_perms = list(Permission.objects.filter(content_type__in=almox_cts))
        all_codes = {f"{p.content_type.app_label}.{p.codename}": p for p in all_almox_perms}

        created_groups = []
        for group_name, conf in GROUPS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                created_groups.append(group_name)

            perms_spec = conf["permissions"]
            perms_to_assign: list[Permission] = []

            if perms_spec == "__ALL_APP_PERMS__":
                perms_to_assign = all_almox_perms
            else:
                for code in perms_spec:
                    perm = all_codes.get(code)
                    if not perm:
                        # Tenta buscar diretamente se o codename foi escrito sem prefixo app
                        if "." in code:
                            app_label, codename = code.split(".", 1)
                        else:
                            app_label, codename = ALMOX_APP, code
                        perm = Permission.objects.filter(
                            content_type__app_label=app_label, codename=codename
                        ).first()
                    if perm:
                        perms_to_assign.append(perm)
                    else:
                        self.stdout.write(self.style.WARNING(f"Permissão não encontrada: {code}"))

            group.permissions.set(perms_to_assign)
            group.save()
            self.stdout.write(self.style.SUCCESS(f"Grupo '{group_name}' atualizado com {len(perms_to_assign)} permissões."))

        if created_groups:
            self.stdout.write(self.style.SUCCESS(f"Grupos criados: {', '.join(created_groups)}"))
        else:
            self.stdout.write("Nenhum grupo novo criado. RBAC sincronizado.")
