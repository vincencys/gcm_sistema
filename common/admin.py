from django.contrib import admin
from .models import NaturezaOcorrencia

@admin.register(NaturezaOcorrencia)
class NaturezaOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "titulo", "grupo", "grupo_nome", "ativo")
    list_filter = ("grupo", "ativo")
    search_fields = ("codigo", "titulo", "grupo", "grupo_nome")
