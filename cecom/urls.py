from django.urls import path
from . import views
from panic import views as panic_views

app_name = "cecom"
urlpatterns = [
    path("", views.painel, name="painel"),
    # Pânico - página básica de gestão dos disparos (fase inicial)
    path("panico/", panic_views.cecom_panico_list, name="panico_list"),
    path("panico/<int:pk>/", panic_views.cecom_panico_detalhe, name="panico_detalhe"),
    path("plantao/iniciar/", views.iniciar_plantao_cecom, name="iniciar_plantao_cecom"),
    path("plantao/<int:pk>/encerrar/", views.encerrar_plantao_cecom, name="encerrar_plantao_cecom"),
    path("plantao/<int:pk>/livro/", views.livro_cecom, name="livro_cecom"),
    path("plantao/<int:pk>/livro/add-viatura/", views.livro_cecom_add_viatura, name="livro_cecom_add_viatura"),
    path("plantao/<int:pk>/livro/del-viatura/<int:vid>/", views.livro_cecom_del_viatura, name="livro_cecom_del_viatura"),
    path("plantao/<int:pk>/livro/add-posto/", views.livro_cecom_add_posto, name="livro_cecom_add_posto"),
    path("plantao/<int:pk>/livro/del-posto/<int:pid>/", views.livro_cecom_del_posto, name="livro_cecom_del_posto"),
    # Pessoas (dispensados/atraso/banco/hora extra)
    path("plantao/<int:pk>/livro/add-pessoa/", views.livro_cecom_add_pessoa, name="livro_cecom_add_pessoa"),
    path("plantao/<int:pk>/livro/del-pessoa/<int:pid>/", views.livro_cecom_del_pessoa, name="livro_cecom_del_pessoa"),
    # CGA do dia (definir/limpar)
    path("plantao/<int:pk>/livro/set-cga/", views.livro_cecom_set_cga, name="livro_cecom_set_cga"),
    path("plantao/<int:pk>/livro/clear-cga/", views.livro_cecom_clear_cga, name="livro_cecom_clear_cga"),
    path('relatorios-livro/', views.relatorios_livro, name='relatorios_livro'),
    path('relatorios-livro/verificar/<str:token>/', views.verificar_relatorio_livro, name='verificar_relatorio_livro'),
    path('relatorios-livro/<int:rid>/download/', views.relatorio_livro_download, name='relatorio_livro_download'),
    path('relatorios-livro/<int:rid>/excluir/', views.relatorio_livro_excluir, name='relatorio_livro_excluir'),
    path("viaturas/", views.painel_viaturas, name="painel_viaturas"),
    path("ativos.json", views.ativos_json, name="ativos_json"),
    # Localização em tempo real
    path("mapa/viaturas/", views.mapa_viaturas, name="mapa_viaturas"),
    path("api/localizacao/", views.localizacao_post, name="localizacao_post"),
    path("api/localizacao/ativas/", views.localizacoes_ativas, name="localizacoes_ativas"),
    
    # Despachos
    path("despachar/", views.despachar_ocorrencia, name="despachar"),
    path("despachos/", views.despachos_lista, name="despachos"),
    path("despachos/arquivados/", views.despachos_arquivados, name="despachos_arquivados"),
    path("despachos/arquivados/excluir/", views.despachos_excluir, name="despachos_excluir_todos"),
    path("despachos/arquivados/excluir/<int:pk>/", views.despachos_excluir, name="despachos_excluir_single"),
    path("despacho/<int:pk>/status/", views.despacho_atualizar_status, name="despacho_status"),
    path("despacho/<int:pk>/finalizar/", views.despacho_finalizar, name="despacho_finalizar"),
    path("despacho/<int:pk>/arquivar/", views.despacho_arquivar, name="despacho_arquivar"),
]
