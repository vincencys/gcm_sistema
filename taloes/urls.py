from __future__ import annotations
from django.urls import path
from . import views, views_extra

app_name = "taloes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:pk>/finalizar/", views.finalizar, name="finalizar"),
    path("<int:pk>/apagar/", views.apagar, name="apagar"),
    path("<int:pk>/editar/", views.editar_talao, name="editar"),
    path("arquivados/", views.taloes_arquivados, name="arquivados"),
    path("<int:pk>/ocorrencia/", views.editar_ocorrencia, name="editar_ocorrencia"),
    path("<int:pk>/abordados/", views.abordados_talao, name="abordados"),
    path("<int:pk>/abordados/<int:abordado_id>/remover/", views.remover_abordado, name="remover_abordado"),
    path("<int:pk>/abastecimento/novo/", views.abastecimento_novo, name="abastecimento_novo"),
    path("<int:pk>/aits/", views.aits_gerenciar, name="aits"),
    path("historico/", views.historico, name="historico"),

    # fluxo do plantão (views_extra)
    path("setup/", views_extra.setup_plantao, name="setup"),

    path("novo/", views_extra.novo_talao, name="novo"),
    path("iniciar-plantao/", views_extra.iniciar_plantao, name="iniciar_plantao"),
    path("editar-plantao/", views_extra.editar_plantao, name="editar_plantao"),
    path("encerrar-plantao/", views_extra.encerrar_plantao, name="encerrar_plantao"),
    path("sair-plantao/", views_extra.sair_plantao, name="sair_plantao"),
    path("relatorio/salvar/", views_extra.relatorio_ronda_salvar, name="relatorio_ronda_salvar"),
    path("relatorio/apagar/", views_extra.relatorio_ronda_apagar, name="relatorio_ronda_apagar"),
    path("finalizar-plantao-pdf/", views_extra.finalizar_plantao_pdf, name="finalizar_plantao_pdf"),
    path("checklist/", views_extra.checklist_viatura, name="checklist_viatura"),
    path("teste-pdf-assinatura/", views_extra.teste_pdf_assinatura, name="teste_pdf_assinatura"),
    path("gerar-pdf-ultimo-plantao/", views_extra.gerar_pdf_ultimo_plantao, name="gerar_pdf_ultimo_plantao"),
    path("documentos/", views_extra.meus_documentos, name="meus_documentos"),
    path("documentos/apagar/", views_extra.apagar_documento, name="apagar_documento"),
    path("documentos/download/", views_extra.download_documento, name="download_documento"),
    # Verificação pública do Relatório de Plantão (via token)
    path("verificar/<str:token>/", views_extra.verificar_relatorio_plantao, name="verificar_relatorio_plantao"),
    # API auxiliar
    path("api/ultimo-km/", views_extra.api_ultimo_km, name="api_ultimo_km"),
    # APIs para anexos de avaria
    path('avaria/anexo/upload/', views_extra.upload_anexo_avaria, name='upload_anexo_avaria'),
    path('avaria/anexo/<int:anexo_id>/remover/', views_extra.remover_anexo_avaria, name='remover_anexo_avaria'),
]
