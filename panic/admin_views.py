from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import date
from .models import Assistida
from .forms import AssistidaForm

@login_required
@permission_required('panic.view_assistida', raise_exception=True)
def assistidas_list(request):
    """Lista todas as assistidas com filtros: status, busca livre e intervalo de datas."""
    status_f = (request.GET.get('status') or '').strip()
    q = (request.GET.get('q') or '').strip()
    de_str = (request.GET.get('de') or '').strip()
    ate_str = (request.GET.get('ate') or '').strip()

    qs = Assistida.objects.order_by('-created_at')
    if status_f:
        qs = qs.filter(status=status_f)
    if q:
        qs = qs.filter(
            Q(nome__icontains=q) |
            Q(cpf__icontains=q) |
            Q(processo_mp__icontains=q) |
            Q(telefone__icontains=q)
        )
    if de_str:
        try:
            d = date.fromisoformat(de_str)
            qs = qs.filter(created_at__date__gte=d)
        except ValueError:
            pass
    if ate_str:
        try:
            d = date.fromisoformat(ate_str)
            qs = qs.filter(created_at__date__lte=d)
        except ValueError:
            pass
    
    ctx = {
        'assistidas': list(qs),
        'status_f': status_f,
        'q': q,
        'de': de_str,
        'ate': ate_str,
        'status_choices': [
            ('PENDENTE_VALIDACAO', 'Pendente'),
            ('APROVADO', 'Aprovado'),
            ('REPROVADO', 'Reprovado'),
            ('SUSPENSO', 'Suspenso'),
        ],
    }
    return render(request, 'panic/assistidas_list.html', ctx)

@login_required
@permission_required('panic.add_assistida', raise_exception=True)
def assistida_criar(request):
    """Criação manual de assistida (já aprovada)."""
    if request.method == 'POST':
        form = AssistidaForm(request.POST, request.FILES)
        if form.is_valid():
            assistida = form.save(commit=False)
            assistida.status = 'APROVADO'  # Aprovação automática para cadastro interno
            assistida.save()
            assistida.gerar_token()
            messages.success(request, f'Assistida {assistida.nome} cadastrada e aprovada com sucesso!')
            return redirect('panic:assistidas_list')
    else:
        form = AssistidaForm()
    
    return render(request, 'panic/assistida_form.html', {'form': form})

@login_required
@permission_required('panic.change_assistida', raise_exception=True)
def assistida_aprovar(request, pk):
    """Aprovar assistida pendente."""
    assistida = get_object_or_404(Assistida, pk=pk)
    if request.method == 'POST':
        assistida.status = 'APROVADO'
        assistida.observacao_validacao = request.POST.get('observacao', '')
        if not assistida.token_panico:
            assistida.gerar_token()
        else:
            assistida.save(update_fields=['status', 'observacao_validacao'])
        messages.success(request, f'✅ Assistida {assistida.nome} aprovada! Token gerado: {assistida.token_panico}')
        return redirect('panic:assistidas_aprovadas_list')
    return render(request, 'panic/assistida_aprovar.html', {'assistida': assistida})

@login_required
@permission_required('panic.change_assistida', raise_exception=True)
def assistida_reprovar(request, pk):
    """Reprovar assistida pendente."""
    assistida = get_object_or_404(Assistida, pk=pk)
    if request.method == 'POST':
        assistida.status = 'REPROVADO'
        assistida.observacao_validacao = request.POST.get('observacao', '')
        assistida.save()
        messages.warning(request, f'Assistida {assistida.nome} reprovada.')
        return redirect('panic:assistidas_pendentes_list')
    return render(request, 'panic/assistida_reprovar.html', {'assistida': assistida})

@login_required
@permission_required('panic.change_assistida', raise_exception=True)
def assistida_suspender(request, pk):
    """Suspender assistida aprovada."""
    assistida = get_object_or_404(Assistida, pk=pk)
    if request.method == 'POST':
        assistida.status = 'SUSPENSO'
        assistida.observacao_validacao = request.POST.get('observacao', '')
        assistida.save()
        messages.info(request, f'Assistida {assistida.nome} suspensa.')
        return redirect('panic:assistidas_aprovadas_list')
    return render(request, 'panic/assistida_suspender.html', {'assistida': assistida})

@login_required
@permission_required('panic.view_assistida', raise_exception=True)
def assistidas_pendentes_list(request):
    """Lista assistidas PENDENTES com filtros avançados e paginação."""
    nome = (request.GET.get('nome') or '').strip()
    cpf = (request.GET.get('cpf') or '').strip()
    telefone = (request.GET.get('telefone') or '').strip()
    processo = (request.GET.get('processo') or '').strip()
    page_num = request.GET.get('page', 1)

    qs = Assistida.objects.filter(status='PENDENTE_VALIDACAO').order_by('-created_at')
    
    if nome:
        qs = qs.filter(nome__icontains=nome)
    if cpf:
        qs = qs.filter(cpf__icontains=cpf)
    if telefone:
        qs = qs.filter(telefone__icontains=telefone)
    if processo:
        qs = qs.filter(processo_mp__icontains=processo)
    
    paginator = Paginator(qs, 10)  # 10 por página
    page_obj = paginator.get_page(page_num)
    
    ctx = {
        'page_obj': page_obj,
        'nome': nome,
        'cpf': cpf,
        'telefone': telefone,
        'processo': processo,
    }
    return render(request, 'panic/assistidas_pendentes_list.html', ctx)


@login_required
@permission_required('panic.view_assistida', raise_exception=True)
def assistidas_aprovadas_list(request):
    """Lista assistidas APROVADAS com filtros avançados e paginação."""
    nome = (request.GET.get('nome') or '').strip()
    cpf = (request.GET.get('cpf') or '').strip()
    telefone = (request.GET.get('telefone') or '').strip()
    processo = (request.GET.get('processo') or '').strip()
    page_num = request.GET.get('page', 1)

    qs = Assistida.objects.filter(status='APROVADO').order_by('-created_at')
    
    if nome:
        qs = qs.filter(nome__icontains=nome)
    if cpf:
        qs = qs.filter(cpf__icontains=cpf)
    if telefone:
        qs = qs.filter(telefone__icontains=telefone)
    if processo:
        qs = qs.filter(processo_mp__icontains=processo)
    
    paginator = Paginator(qs, 10)  # 10 por página
    page_obj = paginator.get_page(page_num)
    
    ctx = {
        'page_obj': page_obj,
        'nome': nome,
        'cpf': cpf,
        'telefone': telefone,
        'processo': processo,
    }
    return render(request, 'panic/assistidas_aprovadas_list.html', ctx)

