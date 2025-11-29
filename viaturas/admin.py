# viaturas/admin.py
from django.contrib import admin
from .models import Viatura

@admin.register(Viatura)
class ViaturaAdmin(admin.ModelAdmin):
    # 1º campo de list_display NÃO pode estar em list_editable
    list_display = (
        "id",
        "prefixo",
        "placa_admin",            # coluna "placa" segura (funciona mesmo se o model não tiver o campo)
        "status",
        "km_atual",
        "km_prox_troca_oleo",
        "km_prox_revisao",
        "ativo",
    )
    list_display_links = ("prefixo",)
    ordering = ("prefixo",)
    search_fields = ("prefixo", "placa")
    list_filter = ("status", "ativo")

    # campos editáveis diretamente na listagem
    list_editable = ("status", "km_atual", "km_prox_troca_oleo", "km_prox_revisao", "ativo")

    # se o seu model não tiver 'placa', essa coluna não quebra o admin
    def placa_admin(self, obj):
        return getattr(obj, "placa", "—")
    placa_admin.short_description = "placa"
