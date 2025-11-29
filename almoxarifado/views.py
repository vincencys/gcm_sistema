from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from .models import Produto, BemPatrimonial, MovimentacaoEstoque, MovimentacaoCautela, CautelaPermanente, DisparoArma, Cautela, CautelaItem, Manutencao, Municao
from .forms import (
    ProdutoForm, MovimentacaoEstoqueForm,
    BemPatrimonialForm, MovimentacaoCautelaForm, CautelaPermanenteForm, DisparoArmaForm,
    ArmamentoSuporteForm, MunicaoSuporteForm, ArmamentoFixoForm, MunicaoFixoForm,
    SolicitarCautelaSuporteForm, MuniicaoLinhaForm, EntregaCautelaForm, DevolucaoCautelaForm,
    
)
from .services import ItemSpec, solicitar_cautela, aprovar_cautela, entregar_cautela, devolver_cautela
from django.contrib.auth.decorators import permission_required
from django.contrib.contenttypes.models import ContentType
from common.models import AuditTrail
from common.audit import log_event
from common.audit_simple import record
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
import csv


@login_required
def estoque_index(request):
    produtos = Produto.objects.select_related('categoria').order_by('nome')
    return render(request, 'almoxarifado/estoque_index.html', {
        'produtos': produtos,
    })


@login_required
def cautelas_index(request):
    suporte_armas = BemPatrimonial.objects.filter(classe='ARMAMENTO', grupo='SUPORTE').order_by('nome')
    suporte_municoes = BemPatrimonial.objects.filter(classe='MUNICAO', grupo='SUPORTE').order_by('nome')

    # Filtros de busca por agente para listas FIXO (armas e munições)
    ag_fixo = (request.GET.get('ag_fixo') or '').strip()
    ag_fixo_mun = (request.GET.get('ag_fixo_mun') or '').strip()

    fixo_armas = BemPatrimonial.objects.filter(classe='ARMAMENTO', grupo='FIXO').select_related('dono__perfil').order_by('nome')
    if ag_fixo:
        fixo_armas = fixo_armas.filter(
            Q(dono__perfil__matricula__icontains=ag_fixo) |
            Q(dono__username__icontains=ag_fixo) |
            Q(dono__first_name__icontains=ag_fixo) |
            Q(dono__last_name__icontains=ag_fixo)
        )

    fixo_municoes = BemPatrimonial.objects.filter(classe='MUNICAO', grupo='FIXO').select_related('dono__perfil').order_by('nome')
    if ag_fixo_mun:
        fixo_municoes = fixo_municoes.filter(
            Q(dono__perfil__matricula__icontains=ag_fixo_mun) |
            Q(dono__username__icontains=ag_fixo_mun) |
            Q(dono__first_name__icontains=ag_fixo_mun) |
            Q(dono__last_name__icontains=ag_fixo_mun)
        )
    # Mapas:
    # - arm_cautelados: armamento_id -> usuário (quando em cautela ABERTA)
    # - arm_reservados: armamento_id -> usuário (quando cautela APROVADA)
    from django.contrib.contenttypes.models import ContentType
    ct_bem = ContentType.objects.get_for_model(BemPatrimonial)
    itens_abertos = (
        CautelaItem.objects
        .filter(item_tipo='ARMAMENTO', content_type=ct_bem, cautela__status='ABERTA')
        .select_related('cautela__usuario')
        .order_by('-cautela__data_hora_retirada', '-cautela_id')
    )
    arm_cautelados = {}
    for it in itens_abertos:
        # Em caso de múltiplas cautelas, pega a mais recente
        if it.object_id not in arm_cautelados:
            arm_cautelados[it.object_id] = it.cautela.usuario
    itens_reservados = (
        CautelaItem.objects
        .filter(item_tipo='ARMAMENTO', content_type=ct_bem, cautela__status='APROVADA')
        .select_related('cautela__usuario')
        .order_by('-cautela__aprovada_em', '-cautela_id')
    )
    arm_reservados = {}
    for it in itens_reservados:
        if it.object_id not in arm_reservados:
            arm_reservados[it.object_id] = it.cautela.usuario
    return render(request, 'almoxarifado/cautelas_index.html', {
        'suporte_armas': suporte_armas,
        'suporte_municoes': suporte_municoes,
        'fixo_armas': fixo_armas,
        'fixo_municoes': fixo_municoes,
        'arm_cautelados': arm_cautelados,
        'arm_reservados': arm_reservados,
        'ag_fixo': ag_fixo,
        'ag_fixo_mun': ag_fixo_mun,
    })
@login_required
def painel_disponibilidade(request):
    from django.utils import timezone
    now = timezone.now()

    # Armamentos ativos
    armas_qs = BemPatrimonial.objects.filter(classe='ARMAMENTO', ativo=True)

    # Em cautela (ABERTA)
    armas_em_cautela_ids = set(
        CautelaItem.objects.filter(
            item_tipo='ARMAMENTO',
            cautela__status='ABERTA'
        ).values_list('object_id', flat=True)
    )

    # Em manutenção ativa
    armas_em_manut_ids = set(
        Manutencao.objects.filter(
            data_fim__isnull=True,
            impacta_disponibilidade=True
        ).values_list('armamento_id', flat=True)
    )

    # Livres = ativos - (em cautela ∪ em manutenção)
    armas_livres = armas_qs.exclude(id__in=armas_em_cautela_ids.union(armas_em_manut_ids))
    armas_em_cautela = armas_qs.filter(id__in=armas_em_cautela_ids)
    armas_em_manut = armas_qs.filter(id__in=armas_em_manut_ids)

    # Alertas
    cautelas_vencidas = Cautela.objects.filter(
        status='ABERTA',
        data_hora_prevista_devolucao__isnull=False,
        data_hora_prevista_devolucao__lt=now
    ).select_related('usuario')

    from datetime import timedelta
    limite = now.date() + timedelta(days=30)
    municoes_por_vencer = Municao.objects.filter(
        status='ATIVO',
        validade__isnull=False,
        validade__lte=limite
    ).order_by('validade', 'calibre', 'lote')

    return render(request, 'almoxarifado/painel_disponibilidade.html', {
        'armas_livres': armas_livres,
        'armas_em_cautela': armas_em_cautela,
        'armas_em_manut': armas_em_manut,
        'cautelas_vencidas': cautelas_vencidas,
        'municoes_por_vencer': municoes_por_vencer,
    })


@login_required
def cautelas_lista(request):
    # Abas simples (mantidas)
    minhas = Cautela.objects.filter(usuario=request.user).order_by('-created_at')[:100]
    pendentes = Cautela.objects.filter(status='PENDENTE').order_by('-created_at')[:100]
    from django.db.models import Q
    aprovadas = Cautela.objects.filter(status='APROVADA').order_by('-aprovada_em', '-id')[:100]
    # 'Abertas (devolução)': incluir ABERTA e também APROVADA com devolução solicitada
    abertas = Cautela.objects.filter(
        Q(status='ABERTA') | Q(status='APROVADA', observacoes__contains='DEVOLUCAO_SOLICITADA=1')
    ).order_by('-data_hora_retirada', '-aprovada_em', '-id')[:100]

    # Filtros e paginação para consulta
    qs = _filter_cautelas_queryset(request)
    paginator = Paginator(qs.select_related('usuario'), 25)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)

    # Querystring preservada (sem 'page') para export/paginação
    from urllib.parse import urlencode
    preserved = {k: v for k, v in request.GET.items() if k not in {'page', 'sort', 'dir'}}
    qstr = urlencode(preserved)

    return render(request, 'almoxarifado/cautelas_lista.html', {
        'minhas': minhas,
        'pendentes': pendentes,
        'aprovadas': aprovadas,
        'abertas': abertas,
        'page_obj': page_obj,
        'total_count': qs.count(),
        'qstr_preserved': qstr,
        'params': preserved,
        'status_choices': Cautela.STATUS_CHOICES,
        'tipo_choices': Cautela.TIPO_CHOICES,
    })


@login_required
def cautelas_detalhe(request, cautela_id: int):
    c = get_object_or_404(Cautela.objects.prefetch_related('itens'), pk=cautela_id)
    # verificar integridade da cadeia de auditoria (hash_prev -> hash_current)
    ct = ContentType.objects.get_for_model(Cautela)
    eventos = (
        AuditTrail.objects
        .filter(content_type=ct, object_id=c.id)
        .order_by('created_at', 'id')
    )
    prev = ""
    chain_ok = True
    for e in eventos:
        if (e.hash_prev or "") != (prev or ""):
            chain_ok = False
            break
        prev = e.hash_current
    return render(request, 'almoxarifado/cautelas_detalhe.html', {'c': c, 'audit_chain_ok': chain_ok})


@login_required
def cautelas_aprovar(request, cautela_id: int):
    c = get_object_or_404(Cautela, pk=cautela_id)
    # Apenas o supervisor designado pode aprovar
    if request.user.id != c.supervisor_id:
        messages.error(request, 'Somente o supervisor designado pode aprovar esta cautela.')
        return redirect('core:almoxarifado:cautelas_detalhe', c.id)
    if request.method == 'POST':
        try:
            aprovar_cautela(cautela=c, supervisor=request.user)
            record(request, event="CAUTELA_APROVADA", obj=c, message=f"Cautela #{c.id} aprovada pelo supervisor", app="almoxarifado")
            messages.success(request, 'Cautela aprovada. Disponível para devolução quando o usuário encerrar o uso.')
            return redirect('core:almoxarifado:cautelas_detalhe', c.id)
        except Exception as e:
            messages.error(request, f'Erro: {e}')
    return render(request, 'almoxarifado/cautelas_aprovar_confirm.html', {'c': c})


@login_required
@permission_required('almoxarifado.entregar_cautela', raise_exception=True)
def cautelas_entregar(request, cautela_id: int):
    c = get_object_or_404(Cautela, pk=cautela_id)
    if request.method == 'POST':
        form = EntregaCautelaForm(request.POST)
        if form.is_valid():
            try:
                entregar_cautela(cautela=c, almoxarife=request.user, checklist_saida=form.cleaned_data.get('checklist_saida'))
                record(request, event="CAUTELA_ENTREGUE", obj=c, message=f"Cautela #{c.id} entregue ao usuário {c.usuario.get_full_name() or c.usuario.username}", app="almoxarifado")
                messages.success(request, 'Cautela entregue/aberta com sucesso.')
                return redirect('core:almoxarifado:cautelas_detalhe', c.id)
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = EntregaCautelaForm()
    return render(request, 'almoxarifado/cautelas_entregar.html', {'c': c, 'form': form})


@login_required
def cautelas_devolver(request, cautela_id: int):
    """Devolução 1-clique: somente POST e somente supervisor.

    Sem formulário; confirmação acontece no front (JS confirm).
    """
    c = get_object_or_404(Cautela, pk=cautela_id)
    # Apenas o supervisor designado pode aprovar a devolução
    if request.user.id != c.supervisor_id:
        messages.error(request, 'Somente o supervisor designado pode aprovar a devolução.')
        return redirect('core:almoxarifado:cautelas_detalhe', c.id)
    if request.method != 'POST':
        messages.error(request, 'Operação inválida. Utilize o botão Devolver.')
        return redirect('core:almoxarifado:cautelas_detalhe', c.id)
    try:
        devolver_cautela(
            cautela=c,
            almoxarife=request.user,
            checklist_retorno=None,
            municao_devolvida=None,
            supervisor=request.user,
        )
        record(request, event="CAUTELA_DEVOLVIDA", obj=c, message=f"Cautela #{c.id} devolvida e encerrada", app="almoxarifado")
        messages.success(request, 'Cautela encerrada com sucesso.')
    except Exception as e:
        messages.error(request, f'Erro: {e}')
    return redirect('core:almoxarifado:cautelas_detalhe', c.id)


# Solicitação de devolução pelo usuário (escolhe o supervisor e sinaliza)
@login_required
def cautelas_solicitar_devolucao(request, cautela_id: int):
    from django import forms
    User = request.user.__class__

    class UserMatriculaChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            perfil = getattr(obj, 'perfil', None)
            matricula = getattr(perfil, 'matricula', '') or getattr(obj, 'username', '')
            nome = (obj.get_full_name() or obj.first_name or obj.last_name or obj.username).upper()
            return f"{matricula} - {nome}"

    class DevolucaoSolicitacaoForm(forms.Form):
        supervisor = UserMatriculaChoiceField(queryset=User.objects.none(), required=True, label='Supervisor')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['supervisor'].widget.attrs.update({'class': 'w-full js-searchable'})
            self.fields['supervisor'].queryset = User.objects.select_related('perfil').filter(perfil__isnull=False).order_by('perfil__matricula', 'username')

    c = get_object_or_404(Cautela, pk=cautela_id)
    # Somente o solicitante pode iniciar a solicitação de devolução enquanto APROVADA
    if c.status != 'APROVADA' or c.usuario_id != request.user.id:
        messages.error(request, 'Somente o solicitante pode solicitar a devolução quando a cautela está aprovada.')
        return redirect('core:almoxarifado:cautelas_detalhe', c.id)
    if request.method == 'POST':
        form = DevolucaoSolicitacaoForm(request.POST)
        if form.is_valid():
            c.supervisor = form.cleaned_data['supervisor']
            # marca flag simples em observacoes
            flag = 'DEVOLUCAO_SOLICITADA=1'
            if (c.observacoes or '').find(flag) == -1:
                c.observacoes = ((c.observacoes or '') + ("\n" if c.observacoes else '') + flag)
            c.save(update_fields=['supervisor', 'observacoes'])
            messages.success(request, 'Devolução solicitada. O supervisor escolhido deve aprovar para retornar ao estoque.')
            return redirect('core:almoxarifado:cautelas_detalhe', c.id)
    else:
        form = DevolucaoSolicitacaoForm()
    return render(request, 'almoxarifado/cautelas_solicitar_devolucao.html', {'c': c, 'form': form})


@login_required
def cautelas_auditoria(request, cautela_id: int):
    c = get_object_or_404(Cautela, pk=cautela_id)
    ct = ContentType.objects.get_for_model(Cautela)
    eventos = (
        AuditTrail.objects
        .filter(content_type=ct, object_id=c.id)
        .select_related('actor')
        .order_by('created_at', 'id')
    )
    # opcional: marcar cadeia como válida (comparando hash_prev/hash_current)
    prev = ""
    cadeia = []
    for e in eventos:
        ok = (e.hash_prev or "") == (prev or "")
        cadeia.append({
            'e': e,
            'encadeamento_ok': ok,
        })
        prev = e.hash_current
    return render(request, 'almoxarifado/cautelas_auditoria.html', {'c': c, 'cadeia': cadeia})


def _filter_cautelas_queryset(request):
    qs = Cautela.objects.all()
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip().upper()
    tipo = (request.GET.get('tipo') or '').strip().upper()
    mine = request.GET.get('mine') == '1'
    de = request.GET.get('de') or ''
    ate = request.GET.get('ate') or ''
    if q:
        # busca por ID ou nome de usuário parcialmente
        if q.isdigit():
            qs = qs.filter(id=int(q))
        else:
            qs = qs.select_related('usuario').filter(usuario__username__icontains=q)
    if status in {s for s, _ in Cautela.STATUS_CHOICES}:
        qs = qs.filter(status=status)
    if tipo in {t for t, _ in Cautela.TIPO_CHOICES}:
        qs = qs.filter(tipo=tipo)
    if mine and request.user.is_authenticated:
        qs = qs.filter(usuario=request.user)
    # datas (campo created_at)
    try:
        if de:
            inicio = timezone.make_aware(timezone.datetime.fromisoformat(f"{de}T00:00:00"))
            qs = qs.filter(created_at__gte=inicio)
        if ate:
            fim = timezone.make_aware(timezone.datetime.fromisoformat(f"{ate}T23:59:59"))
            qs = qs.filter(created_at__lte=fim)
    except Exception:
        pass
    # ordenação configurável
    sort = (request.GET.get('sort') or '').strip()
    direction = (request.GET.get('dir') or 'desc').lower()
    allowed = {
        'id': 'id',
        'usuario': 'usuario__username',
        'tipo': 'tipo',
        'status': 'status',
        'criada': 'created_at',
        'prev': 'data_hora_prevista_devolucao',
        'aprovada': 'aprovada_em',
        'retirada': 'data_hora_retirada',
        'devolucao': 'data_hora_devolucao',
    }
    field = allowed.get(sort, 'created_at')
    prefix = '-' if direction != 'asc' else ''
    return qs.order_by(f"{prefix}{field}", '-id')


@login_required
def cautelas_export_csv(request):
    qs = _filter_cautelas_queryset(request).select_related('usuario')[:5000]
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="cautelas.csv"'
    w = csv.writer(resp)
    w.writerow(['id', 'usuario', 'tipo', 'status', 'criada', 'prev_devolucao', 'aprovada', 'retirada', 'devolucao'])
    for c in qs:
        w.writerow([
            c.id,
            getattr(c.usuario, 'username', ''),
            c.get_tipo_display() if hasattr(c, 'get_tipo_display') else c.tipo,
            c.status,
            c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else '',
            c.data_hora_prevista_devolucao.strftime('%Y-%m-%d %H:%M') if c.data_hora_prevista_devolucao else '',
            c.aprovada_em.strftime('%Y-%m-%d %H:%M') if c.aprovada_em else '',
            c.data_hora_retirada.strftime('%Y-%m-%d %H:%M') if c.data_hora_retirada else '',
            c.data_hora_devolucao.strftime('%Y-%m-%d %H:%M') if c.data_hora_devolucao else '',
        ])
    return resp


@login_required
def cautelas_export_json(request):
    qs = _filter_cautelas_queryset(request).select_related('usuario')[:5000]
    data = []
    for c in qs:
        data.append({
            'id': c.id,
            'usuario': getattr(c.usuario, 'username', ''),
            'tipo': c.tipo,
            'tipo_display': c.get_tipo_display() if hasattr(c, 'get_tipo_display') else c.tipo,
            'status': c.status,
            'criada': c.created_at.isoformat() if c.created_at else None,
            'prev_devolucao': c.data_hora_prevista_devolucao.isoformat() if c.data_hora_prevista_devolucao else None,
            'aprovada': c.aprovada_em.isoformat() if c.aprovada_em else None,
            'retirada': c.data_hora_retirada.isoformat() if c.data_hora_retirada else None,
            'devolucao': c.data_hora_devolucao.isoformat() if c.data_hora_devolucao else None,
        })
    return JsonResponse({'count': len(data), 'results': data})


@login_required
def cautelas_suporte_solicitar(request):
    from django.forms import formset_factory
    MunicaoFormSet = formset_factory(MuniicaoLinhaForm, extra=3, can_delete=True)
    if request.method == 'POST':
        form = SolicitarCautelaSuporteForm(request.POST)
        formset = MunicaoFormSet(request.POST, prefix="mun")
        if form.is_valid() and formset.is_valid():
            itens = []
            arms = form.cleaned_data.get('armamentos') or []
            for a in arms:
                itens.append(ItemSpec(item_tipo="ARMAMENTO", object_id=a.id, quantidade=1))
            # munições
            mun_count = 0
            for f in formset.cleaned_data:
                if not f or f.get("DELETE"):
                    continue
                m = f.get('municao')
                q = f.get('quantidade')
                if m and q:
                    itens.append(ItemSpec(item_tipo="MUNICAO", object_id=m.id, quantidade=int(q)))
                    mun_count += 1
            if mun_count == 0:
                messages.error(request, "Selecione ao menos uma munição com quantidade")
            else:
                try:
                    c = solicitar_cautela(
                        usuario=request.user,
                        supervisor=form.cleaned_data.get('supervisor'),
                        itens=itens,
                        prevista_devolucao=form.cleaned_data.get('prevista_devolucao'),
                    )
                    record(request, event="CAUTELA_SOLICITADA", obj=c, message=f"Cautela #{c.id} solicitada (PENDENTE)", app="almoxarifado")
                    messages.success(request, f"Solicitação criada: Cautela #{c.id} (PENDENTE)")
                    return redirect('core:almoxarifado:cautelas')
                except Exception as e:
                    messages.error(request, f"Erro: {e}")
    else:
        form = SolicitarCautelaSuporteForm()
        formset = MunicaoFormSet(prefix="mun")
    return render(request, 'almoxarifado/cautelas_solicitar_suporte.html', {'form': form, 'formset': formset})


# ====== Estoque forms ======
@login_required
def estoque_produto_novo(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto criado com sucesso.')
            return redirect('core:almoxarifado:estoque')
    else:
        form = ProdutoForm()
    return render(request, 'almoxarifado/estoque_form_produto.html', {'form': form, 'is_edit': False})


@login_required
def estoque_produto_editar(request, produto_id: int):
    p = get_object_or_404(Produto, pk=produto_id)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=p)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto atualizado com sucesso.')
            return redirect('core:almoxarifado:estoque')
    else:
        form = ProdutoForm(instance=p)
    return render(request, 'almoxarifado/estoque_form_produto.html', {'form': form, 'is_edit': True, 'produto': p})


@login_required
@transaction.atomic
def estoque_movimentar(request, produto_id: int):
    p = get_object_or_404(Produto, pk=produto_id)
    if request.method == 'POST':
        form = MovimentacaoEstoqueForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.produto = p
            mov.usuario = request.user
            mov.save()
            mov.aplicar_no_saldo()
            messages.success(request, 'Movimentação registrada e saldo atualizado.')
            return redirect('core:almoxarifado:estoque')
    else:
        form = MovimentacaoEstoqueForm()
    return render(request, 'almoxarifado/estoque_form_movimentacao.html', {'form': form, 'produto': p})


# ====== Cautelas forms ======
@login_required
def cautelas_bem_novo(request):
    if request.method == 'POST':
        form = BemPatrimonialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bem cadastrado com sucesso.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = BemPatrimonialForm()
    return render(request, 'almoxarifado/cautelas_form_bem.html', {'form': form, 'is_edit': False})


@login_required
def cautelas_bem_editar(request, bem_id: int):
    b = get_object_or_404(BemPatrimonial, pk=bem_id)
    if request.method == 'POST':
        form = BemPatrimonialForm(request.POST, instance=b)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bem atualizado com sucesso.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = BemPatrimonialForm(instance=b)
    return render(request, 'almoxarifado/cautelas_form_bem.html', {'form': form, 'is_edit': True, 'bem': b})


# ====== Cautelas: Quatro listas (criar/excluir) ======
@login_required
def cautelas_armamento_suporte_novo(request):
    if request.method == 'POST':
        form = ArmamentoSuporteForm(request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.tipo = 'ARMA'
            b.grupo = 'SUPORTE'
            b.classe = 'ARMAMENTO'
            b.save()
            messages.success(request, 'Armamento de suporte adicionado.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = ArmamentoSuporteForm()
    return render(request, 'almoxarifado/cautelas_form_armamento.html', {
        'form': form,
        'titulo': 'Adicionar Armamento de Suporte',
    })


@login_required
def cautelas_municao_suporte_novo(request):
    if request.method == 'POST':
        form = MunicaoSuporteForm(request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.tipo = 'OUTRO'
            b.grupo = 'SUPORTE'
            b.classe = 'MUNICAO'
            b.save()
            messages.success(request, 'Munição de suporte adicionada.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = MunicaoSuporteForm()
    return render(request, 'almoxarifado/cautelas_form_armamento.html', {
        'form': form,
        'titulo': 'Adicionar Munição do Armamento de Suporte',
        'esconder_subtipo': True,
        'esconder_numero': True,
    })


@login_required
def cautelas_armamento_fixo_novo(request):
    if request.method == 'POST':
        form = ArmamentoFixoForm(request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.tipo = 'ARMA'
            b.grupo = 'FIXO'
            b.classe = 'ARMAMENTO'
            b.save()
            messages.success(request, 'Armamento fixo adicionado.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = ArmamentoFixoForm()
    return render(request, 'almoxarifado/cautelas_form_armamento.html', {
        'form': form,
        'titulo': 'Adicionar Armamento Fixo dos Agentes',
    })


@login_required
def cautelas_municao_fixo_novo(request):
    if request.method == 'POST':
        form = MunicaoFixoForm(request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.tipo = 'OUTRO'
            b.grupo = 'FIXO'
            b.classe = 'MUNICAO'
            b.save()
            messages.success(request, 'Munição do armamento fixo adicionada.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = MunicaoFixoForm()
    return render(request, 'almoxarifado/cautelas_form_armamento.html', {
        'form': form,
        'titulo': 'Adicionar Munição do Armamento Fixo',
        'esconder_subtipo': True,
        'esconder_numero': True,
    })


@login_required
def cautelas_bem_excluir(request, bem_id: int):
    b = get_object_or_404(BemPatrimonial, pk=bem_id)
    if request.method == 'POST':
        b.delete()
        messages.success(request, 'Item excluído com sucesso.')
        return redirect('core:almoxarifado:cautelas')
    return render(request, 'almoxarifado/bem_confirm_delete.html', {'bem': b})


@login_required
def cautelas_movimentar(request, bem_id: int):
    b = get_object_or_404(BemPatrimonial, pk=bem_id)
    if request.method == 'POST':
        form = MovimentacaoCautelaForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.bem = b
            mov.registrado_por = request.user
            mov.save()
            messages.success(request, 'Movimentação registrada.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = MovimentacaoCautelaForm(initial={})
    return render(request, 'almoxarifado/cautelas_form_movimentacao.html', {'form': form, 'bem': b})


@login_required
def cautelas_permanente_atribuir(request, bem_id: int):
    b = get_object_or_404(BemPatrimonial, pk=bem_id)
    if request.method == 'POST':
        form = CautelaPermanenteForm(request.POST)
        if form.is_valid():
            cp = form.save(commit=False)
            cp.bem = b
            cp.save()
            messages.success(request, 'Posse permanente atribuída.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = CautelaPermanenteForm()
    return render(request, 'almoxarifado/cautelas_form_permanente.html', {'form': form, 'bem': b})


@login_required
def cautelas_permanente_devolver(request, cp_id: int):
    cp = get_object_or_404(CautelaPermanente, pk=cp_id)
    if request.method == 'POST':
        cp.devolvido_em = cp.devolvido_em or cp._meta.get_field('devolvido_em').default or None
        from django.utils import timezone as _tz
        cp.devolvido_em = _tz.now()
        cp.save(update_fields=['devolvido_em'])
    messages.success(request, 'Posse permanente devolvida.')
    return redirect('core:almoxarifado:cautelas')
    return render(request, 'almoxarifado/cautelas_form_permanente.html', {'bem': cp.bem, 'cp': cp, 'is_return': True})


@login_required
def cautelas_disparo_registrar(request, bem_id: int):
    b = get_object_or_404(BemPatrimonial, pk=bem_id)
    if request.method == 'POST':
        form = DisparoArmaForm(request.POST)
        if form.is_valid():
            d = form.save(commit=False)
            d.bem = b
            d.save()
            messages.success(request, 'Disparo(s) registrados.')
            return redirect('core:almoxarifado:cautelas')
    else:
        form = DisparoArmaForm()
    return render(request, 'almoxarifado/cautelas_form_disparo.html', {'form': form, 'bem': b})
