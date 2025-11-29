from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from .models import DisparoPanico
from django.db.models import Q
from datetime import date
from .broadcast import broadcast_panico
from django.contrib.auth.decorators import login_required
from django.utils import timezone

def index(request):
    return render(request, 'panic/index.html')

# Endpoint simples para teste manual do broadcast (somente dev)
@csrf_exempt
def _dev_trigger(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'POST only'}, status=405)
    try:
        d = DisparoPanico.objects.order_by('-id').select_related('assistida').first()
        if not d:
            return JsonResponse({'detail': 'Sem disparos para simular'}, status=400)
        broadcast_panico(d)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ---------------- Página básica no CECOM para gestão dos disparos ----------------

@login_required
def cecom_panico_list(request):
    """Lista simples de disparos de pânico com ações Assumir/Encerrar.

    MVP: sem mapa. Filtro opcional por status via ?status=ABERTA|EM_ATENDIMENTO|ENCERRADA|...
    """
    status_f = (request.GET.get('status') or '').strip()
    q = (request.GET.get('q') or '').strip()
    de_str = (request.GET.get('de') or '').strip()
    ate_str = (request.GET.get('ate') or '').strip()

    qs = DisparoPanico.objects.select_related('assistida').order_by('-created_at')
    if status_f:
        qs = qs.filter(status=status_f)
    if q:
        # Busca por nome/cpf da assistida e também por ID do disparo, quando numérico
        try:
            pk_int = int(q)
        except Exception:
            pk_int = None
        query = Q(assistida__nome__icontains=q) | Q(assistida__cpf__icontains=q)
        if pk_int is not None:
            query = query | Q(pk=pk_int)
        qs = qs.filter(query)
    # Intervalo de datas (baseado na data de criação)
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
    # Ações inline básicas via POST (formas simples)
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        # Exclusão múltipla
        if acao == 'excluir_multiplos' and request.user.username == 'moises':
            ids = request.POST.getlist('disparos_selecionados')
            if ids:
                DisparoPanico.objects.filter(pk__in=ids).delete()
                messages.success(request, f'{len(ids)} disparo(s) excluído(s) com sucesso.')
            return redirect('cecom:panico_list')
        
        # Ações individuais
        try:
            pk = int(request.POST.get('id'))
        except Exception:
            pk = None
        
        if acao and pk:
            d = get_object_or_404(DisparoPanico, pk=pk)
            
            # Excluir individual
            if acao == 'excluir' and request.user.username == 'moises':
                d.delete()
                messages.success(request, f'Disparo #{pk} excluído com sucesso.')
                return redirect('cecom:panico_list')
            
            if acao == 'assumir' and d.status in {"ABERTA", "EM_ATENDIMENTO"}:
                if d.status == 'ABERTA':
                    d.marcar_atendimento(request.user)
                return redirect('cecom:panico_list')
            if acao == 'encerrar' and d.status in {"ABERTA", "EM_ATENDIMENTO"}:
                relato = (request.POST.get('relato') or '').strip()
                status_final = (request.POST.get('status_final') or 'ENCERRADA').upper()
                if status_final not in {"ENCERRADA","CANCELADA","FALSO_POSITIVO"}:
                    status_final = 'ENCERRADA'
                d.encerrar(relato, status_final=status_final)
                return redirect('cecom:panico_list')
    page = list(qs[:200])
    ctx = {
        'page': page,
        'status_f': status_f,
        'q': q,
        'de': de_str,
        'ate': ate_str,
        'agora': timezone.localtime(),
        'pode_excluir': request.user.username == 'moises',
        'status_choices': [
            ('ABERTA','Aberta'),
            ('EM_ATENDIMENTO','Em atendimento'),
            ('ENCERRADA','Encerrada'),
            ('CANCELADA','Cancelada'),
            ('FALSO_POSITIVO','Falso positivo'),
        ],
        'status_ativos': ['ABERTA','EM_ATENDIMENTO'],
    }
    return render(request, 'cecom/panico_list.html', ctx)


@login_required
def cecom_panico_detalhe(request, pk: int):
    """Detalhe do disparo de pânico com mapa e ações."""
    d = get_object_or_404(DisparoPanico.objects.select_related('assistida'), pk=pk)

    # Ações rápidas via POST
    if request.method == 'POST':
        acao = request.POST.get('acao') or ''
        if acao == 'assumir' and d.status in {"ABERTA","EM_ATENDIMENTO"}:
            if d.status == 'ABERTA':
                d.marcar_atendimento(request.user)
            return redirect('cecom:panico_detalhe', pk=d.pk)
        if acao == 'encerrar' and d.status in {"ABERTA","EM_ATENDIMENTO"}:
            relato = (request.POST.get('relato') or '').strip()
            status_final = (request.POST.get('status_final') or 'ENCERRADA').upper()
            if status_final not in {"ENCERRADA","CANCELADA","FALSO_POSITIVO"}:
                status_final = 'ENCERRADA'
            d.encerrar(relato, status_final=status_final)
            return redirect('cecom:panico_list')

    ctx = {
        'd': d,
        'has_coords': bool(d.latitude and d.longitude),
    }
    return render(request, 'cecom/panico_detalhe.html', ctx)
