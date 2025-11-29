from django.urls import path
from . import views

app_name = 'almoxarifado'

urlpatterns = [
    path('estoque/', views.estoque_index, name='estoque'),
    path('painel/', views.painel_disponibilidade, name='painel'),
    path('cautelas/', views.cautelas_index, name='cautelas'),
    path('cautelas/lista/', views.cautelas_lista, name='cautelas_lista'),
    path('cautelas/<int:cautela_id>/', views.cautelas_detalhe, name='cautelas_detalhe'),
    path('cautelas/<int:cautela_id>/auditoria/', views.cautelas_auditoria, name='cautelas_auditoria'),
    path('cautelas/export/csv/', views.cautelas_export_csv, name='cautelas_export_csv'),
    path('cautelas/export/json/', views.cautelas_export_json, name='cautelas_export_json'),
    path('cautelas/<int:cautela_id>/aprovar/', views.cautelas_aprovar, name='cautelas_aprovar'),
    path('cautelas/<int:cautela_id>/entregar/', views.cautelas_entregar, name='cautelas_entregar'),
    path('cautelas/<int:cautela_id>/devolver/', views.cautelas_devolver, name='cautelas_devolver'),
    path('cautelas/<int:cautela_id>/solicitar-devolucao/', views.cautelas_solicitar_devolucao, name='cautelas_solicitar_devolucao'),
    path('cautelas/suporte/solicitar/', views.cautelas_suporte_solicitar, name='cautelas_suporte_solicitar'),
    # Cautelas - quatro listas
    path('cautelas/armamento-suporte/novo/', views.cautelas_armamento_suporte_novo, name='cautelas_armamento_suporte_novo'),
    path('cautelas/municao-suporte/novo/', views.cautelas_municao_suporte_novo, name='cautelas_municao_suporte_novo'),
    path('cautelas/armamento-fixo/novo/', views.cautelas_armamento_fixo_novo, name='cautelas_armamento_fixo_novo'),
    path('cautelas/municao-fixo/novo/', views.cautelas_municao_fixo_novo, name='cautelas_municao_fixo_novo'),
    path('cautelas/bem/<int:bem_id>/excluir/', views.cautelas_bem_excluir, name='cautelas_bem_excluir'),
    # Estoque CRUD
    path('estoque/produtos/novo/', views.estoque_produto_novo, name='estoque_produto_novo'),
    path('estoque/produtos/<int:produto_id>/editar/', views.estoque_produto_editar, name='estoque_produto_editar'),
    path('estoque/produtos/<int:produto_id>/movimentar/', views.estoque_movimentar, name='estoque_movimentar'),
    # Cautelas CRUD
    path('cautelas/bens/novo/', views.cautelas_bem_novo, name='cautelas_bem_novo'),
    path('cautelas/bens/<int:bem_id>/editar/', views.cautelas_bem_editar, name='cautelas_bem_editar'),
    path('cautelas/bens/<int:bem_id>/movimentar/', views.cautelas_movimentar, name='cautelas_movimentar'),
    path('cautelas/permanente/<int:bem_id>/atribuir/', views.cautelas_permanente_atribuir, name='cautelas_permanente_atribuir'),
    path('cautelas/permanente/<int:cp_id>/devolver/', views.cautelas_permanente_devolver, name='cautelas_permanente_devolver'),
    path('cautelas/bens/<int:bem_id>/disparos/registrar/', views.cautelas_disparo_registrar, name='cautelas_disparo_registrar'),
]
