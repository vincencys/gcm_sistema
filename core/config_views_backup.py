from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q

from users.forms import RegistrarUsuarioForm, GcmPerfilForm
from users.models import Perfil


def _is_config_admin(user) -> bool:
    try:
        return (user.get_username() or "").strip().lower() in {"moises", "admnistrativo"}
    except Exception:
        return False


@login_required
def config_dashboard(request):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à área de Configurações.")
        return redirect("core:dashboard")

    User = get_user_model()
    total_users = User.objects.count()
    total_perfis = Perfil.objects.count()

    return render(request, "configuracoes/dashboard.html", {
        "total_users": total_users,
        "total_perfis": total_perfis,
    })


# ===== Usuários =====
@login_required
def usuarios_list(request):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à gestão de usuários.")
        return redirect("core:dashboard")

    User = get_user_model()
    q = (request.GET.get("q") or "").strip()
    qs = User.objects.all().order_by("username")
    if q:
        qs = qs.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    paginator = Paginator(qs, 20)
    page = request.GET.get("page")
    users = paginator.get_page(page)

    return render(request, "configuracoes/usuarios_list.html", {
        "users": users,
        "q": q,
    })


@login_required
def usuario_new(request):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à criação de usuários.")
        return redirect("core:dashboard")

    if request.method == "POST":
        form = RegistrarUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário {user.username} criado com sucesso.")
            # Redireciona para a listagem com busca pelo username criado
            return redirect(f"{redirect('core:config_usuarios').url}?q={user.username}")
    else:
        form = RegistrarUsuarioForm()

    return render(request, "configuracoes/usuario_form.html", {
        "form": form,
        "is_create": True,
    })


@login_required
def usuario_edit(request, user_id: int):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à edição de usuários.")
        return redirect("core:dashboard")

    User = get_user_model()
    user = get_object_or_404(User, pk=user_id)

    # Editar campos básicos; reutiliza RegistrarUsuarioForm para layout e validações de nome/email.
    # Para não exigir senha, criamos um form mínimo ad-hoc.
    from django import forms

    class _UserEditForm(forms.ModelForm):
        class Meta:
            model = User
            fields = ("first_name", "last_name", "email", "is_active")
            widgets = {
                "first_name": forms.TextInput(attrs={"class": "w-full"}),
                "last_name": forms.TextInput(attrs={"class": "w-full"}),
                "email": forms.EmailInput(attrs={"class": "w-full"}),
            }

    if request.method == "POST":
        form = _UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário atualizado com sucesso.")
            return redirect("core:config_usuarios")
    else:
        form = _UserEditForm(instance=user)

    return render(request, "configuracoes/usuario_form.html", {
        "form": form,
        "is_create": False,
        "obj": user,
    })


# ===== Perfis GCM =====
@login_required
def perfis_list(request):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à gestão de perfis.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    qs = Perfil.objects.select_related("user").all().order_by("user__username")
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q) |
            Q(matricula__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )
    paginator = Paginator(qs, 20)
    page = request.GET.get("page")
    perfis = paginator.get_page(page)

    return render(request, "configuracoes/perfis_list.html", {
        "perfis": perfis,
        "q": q,
    })


@login_required
def perfil_new(request):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à criação de perfis.")
        return redirect("core:dashboard")

    User = get_user_model()
    
    if request.method == "POST":
        # Obter usuário selecionado
        user_id = request.POST.get("user_id")
        if not user_id:
            messages.error(request, "Selecione um usuário para criar o perfil.")
        else:
            try:
                user = User.objects.get(pk=user_id)
                # Verificar se já existe perfil para este usuário
                if hasattr(user, 'perfil'):
                    messages.warning(request, f"O usuário {user.username} já possui um perfil.")
                    return redirect("core:config_perfil_editar", perfil_id=user.perfil.id)
                
                # Criar perfil com dados do form
                form = GcmPerfilForm(request.POST, request.FILES)
                if form.is_valid():
                    perfil = form.save(commit=False)
                    perfil.user = user
                    perfil.save()
                    messages.success(request, f"Perfil criado com sucesso para {user.username}.")
                    return redirect("core:config_perfis")
            except User.DoesNotExist:
                messages.error(request, "Usuário não encontrado.")
    else:
        form = GcmPerfilForm()
    
    # Listar usuários sem perfil
    usuarios_sem_perfil = User.objects.filter(perfil__isnull=True).order_by("username")
    
    return render(request, "configuracoes/perfil_form.html", {
        "form": form,
        "is_create": True,
        "usuarios_sem_perfil": usuarios_sem_perfil,
    })


@login_required
def perfil_edit(request, perfil_id: int):
    if not _is_config_admin(request.user):
        messages.error(request, "Acesso negado à edição de perfis.")
        return redirect("core:dashboard")

    perfil = get_object_or_404(Perfil.objects.select_related("user"), pk=perfil_id)
    if request.method == "POST":
        form = GcmPerfilForm(request.POST, request.FILES, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("core:config_perfis")
    else:
        form = GcmPerfilForm(instance=perfil)

    return render(request, "configuracoes/perfil_form.html", {
        "form": form,
        "obj": perfil,
        "is_create": False,
    })
