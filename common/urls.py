from django.urls import path
from . import views, ai_views

app_name = 'common'

urlpatterns = [
    path('healthz/', views.healthz, name='healthz'),
    path('documentos/pendentes/', views.documentos_pendentes, name='documentos_pendentes'),
    path('documentos/pendentes/ronda/', views.documentos_pendentes_ronda, name='documentos_pendentes_ronda'),
    path('documentos/pendentes/bogcm/', views.documentos_pendentes_bogcm, name='documentos_pendentes_bogcm'),
    path('documentos/pendentes/livro/', views.documentos_pendentes_livro, name='documentos_pendentes_livro'),
    path('documentos/assinados/', views.documentos_assinados, name='documentos_assinados'),
    path('documentos/assinados/ronda/', views.documentos_assinados_ronda, name='documentos_assinados_ronda'),
    path('documentos/assinados/bogcm/', views.documentos_assinados_bogcm, name='documentos_assinados_bogcm'),
    path('documentos/assinados/livro/', views.documentos_assinados_livro, name='documentos_assinados_livro'),
    path('documentos/<int:pk>/assinar/', views.assinar_documento, name='assinar_documento'),
    path('documentos/assinar-lote/', views.assinar_documentos_lote, name='assinar_documentos_lote'),
    path('documentos/<int:pk>/recusar/', views.recusar_documento, name='recusar_documento'),
    path('documentos/<int:pk>/excluir/', views.excluir_documento, name='excluir_documento'),
    path('documentos/<int:pk>/ver/', views.servir_documento, name='servir_documento'),
    path('diagnostico/pdfs/', views.diagnostico_pdfs, name='diagnostico_pdfs'),
    
    # IA endpoints
    path('ai/melhorar-relatorio/', ai_views.melhorar_relatorio_ai, name='melhorar_relatorio_ai'),
    path('ai/sugerir-relatorio/', ai_views.sugerir_relatorio_ai, name='sugerir_relatorio_ai'),

    # Push/Notificações
    path('push/register-device/', views.register_device, name='push_register_device'),
    path('push/test/', views.push_test, name='push_test'),
    path('push/diag/', views.push_diag, name='push_diag'),
]
