from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import (
    CategoriaProduto,
    Produto,
    MovimentacaoEstoque,
    BemPatrimonial,
    Cautela,
    CautelaItem,
    AssignacaoFixa,
    Manutencao,
    Municao,
    MunicaoEstoque,
)
from . import services
from .forms import EntregaCautelaForm, DevolucaoCautelaForm


@admin.register(CategoriaProduto)
class CategoriaProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao")
    search_fields = ("nome", "descricao")
    ordering = ("nome",)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "unidade", "estoque_atual", "estoque_minimo", "ativo")
    list_filter = ("ativo", "categoria")
    search_fields = ("nome",)
    autocomplete_fields = ("categoria",)
    ordering = ("nome",)


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("produto", "tipo", "quantidade", "usuario", "criado_em")
    list_filter = ("tipo", "criado_em")
    search_fields = ("produto__nome", "usuario__username")
    autocomplete_fields = ("produto", "usuario")
    date_hierarchy = "criado_em"
    ordering = ("-criado_em",)


@admin.register(BemPatrimonial)
class BemPatrimonialAdmin(admin.ModelAdmin):
    list_display = ("nome", "get_tipo", "classe", "grupo", "tombamento", "numero_serie", "calibre", "ativo")
    list_filter = ("tipo", "classe", "grupo", "ativo")
    search_fields = ("nome", "tombamento", "numero_serie", "calibre")
    ordering = ("tipo", "nome")

    def get_tipo(self, obj):
        return obj.get_tipo_display()
    get_tipo.short_description = "Tipo"


class CautelaItemInline(GenericTabularInline):
    model = CautelaItem
    extra = 1
    fields = ("item_tipo", "content_type", "object_id", "quantidade", "estado_saida", "estado_retorno")


@admin.register(Cautela)
class CautelaAdmin(admin.ModelAdmin):
    change_form_template = "admin/almoxarifado/cautela/change_form.html"
    list_display = (
        "id",
        "tipo",
        "usuario",
        "almoxarife",
        "supervisor",
        "status",
        "data_hora_retirada",
        "data_hora_prevista_devolucao",
        "data_hora_devolucao",
    )
    list_filter = ("tipo", "status")
    search_fields = ("id", "usuario__username", "almoxarife__username", "supervisor__username")
    autocomplete_fields = ("usuario", "almoxarife", "supervisor")
    inlines = [CautelaItemInline]
    ordering = ("-id",)

    actions = ("action_aprovar", "action_entregar", "action_devolver")

    def action_aprovar(self, request, queryset):
        ok = err = 0
        for c in queryset:
            try:
                services.aprovar_cautela(cautela=c, supervisor=request.user)
                ok += 1
            except Exception as e:
                err += 1
        self.message_user(request, f"Aprovadas: {ok}. Falhas: {err}.")
    action_aprovar.short_description = "Aprovar cautelas selecionadas"

    def action_entregar(self, request, queryset):
        ok = err = 0
        for c in queryset:
            try:
                services.entregar_cautela(cautela=c, almoxarife=request.user)
                ok += 1
            except Exception:
                err += 1
        self.message_user(request, f"Entregues: {ok}. Falhas: {err}.")
    action_entregar.short_description = "Entregar (abrir) cautelas selecionadas"

    def action_devolver(self, request, queryset):
        ok = err = 0
        for c in queryset:
            try:
                services.devolver_cautela(cautela=c, almoxarife=request.user)
                ok += 1
            except Exception:
                err += 1
        self.message_user(request, f"Devolvidas: {ok}. Falhas: {err}.")
    action_devolver.short_description = "Receber (encerrar) cautelas selecionadas"

    # URLs customizadas para ações por objeto
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/aprovar/', self.admin_site.admin_view(self.view_aprovar), name='almoxarifado_cautela_aprovar'),
            path('<int:pk>/entregar/', self.admin_site.admin_view(self.view_entregar), name='almoxarifado_cautela_entregar'),
            path('<int:pk>/devolver/', self.admin_site.admin_view(self.view_devolver), name='almoxarifado_cautela_devolver'),
        ]
        return custom + urls

    def view_aprovar(self, request, pk: int):
        obj = get_object_or_404(Cautela, pk=pk)
        try:
            services.aprovar_cautela(cautela=obj, supervisor=request.user)
            self.message_user(request, "Cautela aprovada.", level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Erro: {e}", level=messages.ERROR)
        return redirect('admin:almoxarifado_cautela_change', obj.pk)

    def view_entregar(self, request, pk: int):
        obj = get_object_or_404(Cautela, pk=pk)
        if request.method == 'POST':
            form = EntregaCautelaForm(request.POST)
            if form.is_valid():
                try:
                    services.entregar_cautela(
                        cautela=obj,
                        almoxarife=request.user,
                        checklist_saida=form.cleaned_data.get('checklist_saida'),
                    )
                    self.message_user(request, "Cautela entregue.", level=messages.SUCCESS)
                    return redirect('admin:almoxarifado_cautela_change', obj.pk)
                except Exception as e:
                    self.message_user(request, f"Erro: {e}", level=messages.ERROR)
        else:
            form = EntregaCautelaForm()
        return render(request, 'admin/almoxarifado/cautela/entregar.html', {'form': form, 'original': obj})

    def view_devolver(self, request, pk: int):
        obj = get_object_or_404(Cautela, pk=pk)
        if request.method == 'POST':
            form = DevolucaoCautelaForm(request.POST)
            if form.is_valid():
                try:
                    services.devolver_cautela(
                        cautela=obj,
                        almoxarife=request.user,
                        checklist_retorno=form.cleaned_data.get('checklist_retorno'),
                        municao_devolvida=form.cleaned_data.get('municao_devolvida'),
                    )
                    self.message_user(request, "Cautela devolvida.", level=messages.SUCCESS)
                    return redirect('admin:almoxarifado_cautela_change', obj.pk)
                except Exception as e:
                    self.message_user(request, f"Erro: {e}", level=messages.ERROR)
        else:
            form = DevolucaoCautelaForm()
        return render(request, 'admin/almoxarifado/cautela/devolver.html', {'form': form, 'original': obj})


@admin.register(AssignacaoFixa)
class AssignacaoFixaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "armamento", "status", "data_inicio", "data_fim")
    list_filter = ("status",)
    search_fields = ("usuario__username", "armamento__nome", "armamento__numero_serie")
    autocomplete_fields = ("usuario", "armamento")
    ordering = ("-data_inicio",)


@admin.register(Manutencao)
class ManutencaoAdmin(admin.ModelAdmin):
    list_display = ("armamento", "tipo", "data_inicio", "data_fim", "impacta_disponibilidade")
    list_filter = ("tipo", "impacta_disponibilidade")
    search_fields = ("armamento__nome", "armamento__numero_serie")
    autocomplete_fields = ("armamento",)
    ordering = ("-data_inicio",)


@admin.register(Municao)
class MunicaoAdmin(admin.ModelAdmin):
    list_display = ("calibre", "tipo", "lote", "validade", "status")
    list_filter = ("tipo", "status")
    search_fields = ("calibre", "lote")
    ordering = ("calibre", "lote")


@admin.register(MunicaoEstoque)
class MunicaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ("municao", "local", "quantidade_disponivel", "quantidade_reservada")
    list_filter = ("local",)
    search_fields = ("municao__calibre", "municao__lote", "local")
    autocomplete_fields = ("municao",)
    ordering = ("local",)
