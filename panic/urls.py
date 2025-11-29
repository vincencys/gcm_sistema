from django.urls import path
from . import views, api, public_api, admin_views

app_name = 'panic'

urlpatterns = [
	path('', views.index, name='index'),
	path('_dev/trigger/', views._dev_trigger, name='dev_trigger_panico'),
	# Gestão de assistidas (admin)
	path('assistidas/', admin_views.assistidas_list, name='assistidas_list'),
	path('assistidas/pendentes/', admin_views.assistidas_pendentes_list, name='assistidas_pendentes_list'),
	path('assistidas/aprovadas/', admin_views.assistidas_aprovadas_list, name='assistidas_aprovadas_list'),
	path('assistidas/criar/', admin_views.assistida_criar, name='assistida_criar'),
	path('assistidas/<int:pk>/aprovar/', admin_views.assistida_aprovar, name='assistida_aprovar'),
	path('assistidas/<int:pk>/reprovar/', admin_views.assistida_reprovar, name='assistida_reprovar'),
	path('assistidas/<int:pk>/suspender/', admin_views.assistida_suspender, name='assistida_suspender'),
	# API interna (CECOM / operacional)
	path('api/disparos/', api.DisparoListAPI.as_view(), name='api_disparos_list'),
	path('api/disparos/<int:pk>/assumir/', api.DisparoAssumirAPI.as_view(), name='api_disparo_assumir'),
	path('api/disparos/<int:pk>/encerrar/', api.DisparoEncerrarAPI.as_view(), name='api_disparo_encerrar'),
	path('api/disparos/<int:pk>/', api.DisparoDetalheAPI.as_view(), name='api_disparo_detalhe'),
	# Workflow Assistida (interno)
	path('api/assistida/<int:pk>/aprovar/', api.AssistidaAprovarAPI.as_view(), name='api_assistida_aprovar'),
	path('api/assistida/<int:pk>/reprovar/', api.AssistidaReprovarAPI.as_view(), name='api_assistida_reprovar'),
	path('api/assistida/<int:pk>/suspender/', api.AssistidaSuspenderAPI.as_view(), name='api_assistida_suspender'),
	path('api/assistida/<int:pk>/reativar/', api.AssistidaReativarAPI.as_view(), name='api_assistida_reativar'),
	path('api/assistida/<int:pk>/rotacionar-token/', api.AssistidaRotacionarTokenAPI.as_view(), name='api_assistida_rotacionar_token'),
	# Endpoints públicos para app (Assistida)
	path('public/assistida/solicitar/', public_api.PublicAssistidaSolicitar.as_view(), name='public_assistida_solicitar'),
	path('public/disparo/', public_api.PublicDisparoCriar.as_view(), name='public_disparo_criar'),
	path('public/disparo/<int:pk>/localizacao/', public_api.PublicDisparoLocalizacao.as_view(), name='public_disparo_localizacao'),
]
