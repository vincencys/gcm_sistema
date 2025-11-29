from django.contrib import admin
from django.db.models import F, Window
from .models import GrupoOcorrencia, CodigoOcorrencia, Talao


@admin.register(GrupoOcorrencia)
class GrupoOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "descricao")
    search_fields = ("nome", "descricao")
    ordering = ("nome",)


@admin.register(CodigoOcorrencia)
class CodigoOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("sigla", "descricao", "grupo")
    list_filter = ("grupo",)
    search_fields = ("sigla", "descricao", "grupo__nome")
    ordering = ("sigla",)


@admin.register(Talao)
class TalaoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "viatura",
        "status",
        "iniciado_em",
        "encerrado_em",
        "km_inicial",
        "km_final",
        "local_bairro",
        "local_rua",
        "codigo_ocorrencia",
    )
    list_filter = ("status", "viatura", "iniciado_em", "codigo_ocorrencia")
    search_fields = (
        "local_bairro",
        "local_rua",
        "equipe_texto",
        "plantao",
        "codigo_ocorrencia__sigla",
        "codigo_ocorrencia__descricao",
        "viatura__prefixo",
    )
    date_hierarchy = "iniciado_em"
    autocomplete_fields = (
        "viatura",
        "codigo_ocorrencia",
        "encarregado",
        "motorista",
        "auxiliar1",
        "auxiliar2",
        "criado_por",
    )
    ordering = ("iniciado_em",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Constrói a ordenação atual do admin para a janela ROW_NUMBER
        order_fields = []
        for fld in self.get_ordering(request) or ["iniciado_em"]:
            if isinstance(fld, str) and fld.startswith("-"):
                order_fields.append(F(fld[1:]).desc())
            else:
                order_fields.append(F(fld).asc())
        try:
            from django.db.models.functions import RowNumber as _RowNumber
            qs = qs.annotate(_rownum=Window(expression=_RowNumber(), order_by=order_fields))
        except Exception:
            # Se o banco/ORM não suportar window functions, mantém QS simples
            pass
        return qs

    @admin.display(description="Nº", ordering="_rownum")
    def numero(self, obj):
        # Usa a anotação _rownum quando disponível; senão, cai para o próprio id
        return getattr(obj, "_rownum", None) or "-"
