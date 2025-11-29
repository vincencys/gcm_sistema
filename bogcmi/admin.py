from django.contrib import admin
from .models import CadastroEnvolvido


@admin.register(CadastroEnvolvido)
class CadastroEnvolvidoAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'cpf', 'cpf_normalizado', 'cidade', 'uf', 'telefone',
    )
    search_fields = (
        'nome', 'nome_social', 'cpf', 'cpf_normalizado', 'rg', 'telefone', 'endereco', 'bairro', 'cidade'
    )
    list_per_page = 25
    ordering = ('nome',)
    readonly_fields = ('cpf_normalizado',)
