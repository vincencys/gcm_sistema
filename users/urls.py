from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "users"

urlpatterns = [
    path("login/",  views.RememberLoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    path("registrar/", views.registrar, name="registrar"),
    path("2fa/configurar/", views.twofa_configurar, name="twofa_configurar"),
    path("2fa/validar/", views.twofa_validar, name="twofa_validar"),
    # Reset de senha via e-mail de recuperação
    path("password/reset/", views.password_reset_request, name="password_reset"),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="users/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="users/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="users/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
