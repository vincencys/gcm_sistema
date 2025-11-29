# viaturas/urls.py
from django.urls import path
from . import views

app_name = "viaturas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar, name="criar"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/observacoes/", views.observacoes, name="observacoes"),
    path("<int:pk>/avarias/", views.avarias, name="avarias"),
    path("<int:pk>/avarias/resolver/", views.resolver_avarias, name="resolver_avarias"),
    path("<int:pk>/arquivar/", views.arquivar, name="arquivar"),
    path("<int:pk>/restaurar/", views.restaurar, name="restaurar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("track/", views.track, name="track"),
]
