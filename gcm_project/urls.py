# gcm_project/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from common.views import healthz

# Branding opcional do admin
admin.site.site_header = "Administração do Sistema GCM"
admin.site.site_title = "Sistema GCM – Admin"
admin.site.index_title = "Painel de Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Healthcheck simples para o app mobile
    path("healthz/", healthz, name="healthz_root"),

    # apps
    path("", include(("core.urls", "core"), namespace="core")),
    path("users/", include(("users.urls", "users"), namespace="users")),
    path("viaturas/", include(("viaturas.urls", "viaturas"), namespace="viaturas")),
    path("taloes/", include(("taloes.urls", "taloes"), namespace="taloes")),
    path("bogcmi/", include(("bogcmi.urls", "bogcmi"), namespace="bogcmi")),
    path("panic/", include(("panic.urls", "panic"), namespace="panic")),
    path("cecom/", include(("cecom.urls", "cecom"), namespace="cecom")),
    path("notificacoes/", include(("notificacoes.urls", "notificacoes"), namespace="notificacoes")),
    path("integracoes/", include(("integracoes.urls", "integracoes"), namespace="integracoes")),
    path("relatorios/", include(("relatorios.urls", "relatorios"), namespace="relatorios")),
    path("common/", include(("common.urls", "common"), namespace="common")),


    # /favicon.ico -> /static/favicon.ico (evita 404 em prod)
    re_path(r"^favicon\.ico$", RedirectView.as_view(
        url=f"{settings.STATIC_URL}favicon.ico", permanent=True
    )),
]

# Arquivos de mídia (somente no dev)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug Toolbar (se instalado)
    try:
        import debug_toolbar  # type: ignore
    except Exception:
        debug_toolbar = None
    if debug_toolbar:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
