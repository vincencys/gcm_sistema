from django.urls import path
from . import views
from . import sync_views
from . import views_debug

app_name = 'bogcmi'

urlpatterns = [
    path('', views.bo_list, name='lista'),
    path('table/', views.bo_table, name='table'),
    path('novo/', views.novo_layout, name='novo'),
    path('<int:pk>/salvar/', views.salvar_bo, name='salvar'),
    path('<int:pk>/excluir/', views.bo_excluir, name='excluir'),
    path('envolvido/novo/', views.envolvido_form, name='envolvido_form'),
    path('envolvido/<int:pk>/editar/', views.envolvido_form, name='envolvido_editar'),
    path('envolvido/<int:pk>/excluir/', views.envolvido_excluir, name='envolvido_excluir'),
    path('envolvido/lista/', views.envolvido_list, name='envolvido_list'),
    path('envolvido/form-offline/', views.envolvido_form_offline, name='envolvido_form_offline'),
    path('envolvido/import-offline/', views.envolvido_import_offline, name='envolvido_import_offline'),
    path('<int:pk>/editar/', views.bo_editar, name='editar'),
    path('<int:pk>/finalizar/', views.bo_finalizar, name='finalizar'),
    path('<int:pk>/despachar-cmt/', views.bo_despachar_cmt, name='despachar_cmt'),
    path('<int:pk>/duplicar/', views.duplicar_bo, name='duplicar'),
    path('apreensao/novo/', views.apreensao_form, name='apreensao_form'),
    path('apreensao/lista/', views.apreensao_lista, name='apreensao_lista'),
    path('apreensao/<int:pk>/excluir/', views.apreensao_excluir, name='apreensao_excluir'),
    path('apreensao/<int:pk>/anexo/', views.apreensao_anexo_form, name='apreensao_anexo_form'),
    path('apreensao/anexo/<int:pk>/excluir/', views.apreensao_anexo_excluir, name='apreensao_anexo_excluir'),
    # URLs para veículos
    path('veiculo/novo/', views.veiculo_form, name='veiculo_form'),
    path('veiculo/<int:pk>/editar/', views.veiculo_form, name='veiculo_editar'),
    path('veiculo/lista/', views.veiculo_lista, name='veiculo_lista'),
    path('veiculo/<int:pk>/excluir/', views.veiculo_excluir, name='veiculo_excluir'),
    path('veiculo/<int:pk>/anexo/', views.veiculo_anexo_form, name='veiculo_anexo_form'),
    path('veiculo/anexo/<int:pk>/excluir/', views.veiculo_anexo_excluir, name='veiculo_anexo_excluir'),
    path('veiculo/form-offline/', views.veiculo_form_offline, name='veiculo_form_offline'),
    path('veiculo/import-offline/', views.veiculo_import_offline, name='veiculo_import_offline'),
    # URLs para equipes de apoio
    path('equipe/novo/', views.equipe_form, name='equipe_form'),
    path('equipe/<int:pk>/editar/', views.equipe_form, name='equipe_editar'),
    path('equipe/lista/', views.equipe_lista, name='equipe_lista'),
    path('equipe/<int:pk>/excluir/', views.equipe_excluir, name='equipe_excluir'),
    # URLs para anexos
    path('anexo/novo/', views.anexo_form, name='anexo_form'),
    path('anexo/lista/', views.anexo_lista, name='anexo_lista'),
    path('anexo/<int:pk>/excluir/', views.anexo_excluir, name='anexo_excluir'),
    # URLs para autosave e finalização de BO
    path('autosave/', views.autosave_finalizacao, name='autosave_finalizacao'),
    path('finalizar-bo/', views.finalizar_bo, name='finalizar_bo'),

    path('criar-bo-automatico/', views.criar_bo_automatico, name='criar_bo_automatico'),
    path('<int:pk>/documento/', views.visualizar_documento_bo, name='visualizar_documento_bo'),
    path('<int:pk>/baixar-documento/', views.baixar_documento_bo, name='baixar_documento_bo'),
    path('<int:pk>/baixar-pdf/', views.baixar_documento_bo_pdf, name='baixar_documento_bo_pdf'),
    path('documento-assinado/<int:doc_id>/', views.servir_documento_assinado, name='servir_documento_assinado'),
    path('pdf-token/<str:token>/<int:doc_id>/', views.servir_documento_com_token, name='servir_documento_com_token'),
    path('gerar-token-pdf/<int:doc_id>/', views.gerar_token_acesso_pdf, name='gerar_token_acesso_pdf'),
    path('validar/<int:pk>/<str:token>/', views.validar_documento_bo, name='validar_documento_bo'),
    path('sync-offline/', sync_views.sync_offline_bos, name='sync_offline_bos'),
    # Debug
    path('<int:pk>/debug-marca/', views_debug.debug_marca_dagua, name='debug_marca_dagua'),
    # API
    path('api/envolvido-por-cpf/', views.api_cadastro_envolvido_lookup, name='api_envolvido_por_cpf'),
]
