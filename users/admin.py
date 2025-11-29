# users/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Perfil, Lotacao


@admin.register(Lotacao)
class LotacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "sigla")
    ordering = ("nome",)
    actions = ("marcar_ativo", "marcar_inativo")

    def marcar_ativo(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} lotações marcadas como ativas.")
    marcar_ativo.short_description = "Marcar como ativas"

    def marcar_inativo(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} lotações marcadas como inativas.")
    marcar_inativo.short_description = "Marcar como inativas"

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = (
        "user_username",
        "user_fullname",
        "matricula",
        "recovery_email",
        "lotacao",
        "equipe",
        "classe",
        "cargo",
        "ativo",
        "assinatura_preview",
    )
    list_filter = ("equipe", "classe", "ativo", "lotacao")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "matricula",
        "recovery_email",
        "cargo",
    )
    ordering = ("user__username",)
    list_select_related = ("user", "lotacao")
    autocomplete_fields = ("user", "lotacao")
    save_on_top = True
    readonly_fields = ("assinatura_preview",)
    fieldsets = (
        ("Vinculação", {"fields": ("user", "ativo")}),
        ("Dados Funcionais", {"fields": ("matricula", "equipe", "classe", "cargo", "lotacao", "recovery_email")}),
        ("Assinatura", {"fields": ("assinatura_img", "assinatura_preview")}),
    )
    actions = ("marcar_ativo", "marcar_inativo")

    # colunas helpers
    def user_username(self, obj):
        return obj.user.username
    user_username.short_description = "Usuário"
    user_username.admin_order_field = "user__username"

    def user_fullname(self, obj):
        fn = (obj.user.get_full_name() or "").strip()
        return fn or "—"
    user_fullname.short_description = "Nome"

    # preview clicável
    def assinatura_preview(self, obj):
        if obj.assinatura_img:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height:60px;"></a>',
                obj.assinatura_img.url,
            )
        return "—"
    assinatura_preview.short_description = "Assinatura"

    # ações em lote
    def marcar_ativo(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} perfis marcados como ativos.")
    marcar_ativo.short_description = "Marcar como ativos"

    def marcar_inativo(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} perfis marcados como inativos.")
    marcar_inativo.short_description = "Marcar como inativos"
