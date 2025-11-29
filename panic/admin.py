from django.contrib import admin
from .models import Dispositivo, Evento, Assistida, DisparoPanico

@admin.register(Assistida)
class AssistidaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "status", "created_at")
    search_fields = ("nome", "cpf", "processo_mp")
    list_filter = ("status", "created_at")

@admin.register(DisparoPanico)
class DisparoPanicoAdmin(admin.ModelAdmin):
    list_display = ("id", "assistida", "status", "created_at", "em_atendimento_em", "encerrado_em")
    search_fields = ("assistida__nome", "assistida__cpf")
    list_filter = ("status", "created_at")

@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "vitima_nome", "ativo", "created_at")
    search_fields = ("codigo", "vitima_nome")
    list_filter = ("ativo",)

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("id", "dispositivo", "status", "created_at")
    list_filter = ("status",)
