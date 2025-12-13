from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import csv
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.mail import EmailMessage
from django.contrib import messages
import os, re, tempfile, subprocess
from django.conf import settings
from bogcmi.models import BO
from taloes.models import Talao
from cecom.models import PlantaoCECOM, PlantaoCecomPrincipal
from taloes.views_extra import SESSION_PLANTAO
from .models import EscalaMensal, Audiencias, OrdemServico, OficioDiverso, Dispensa, NotificacaoFiscalizacao, AutoInfracaoComercio, AutoInfracaoSom, OficioInterno, OficioAcao, BancoHorasSaldo, BancoHorasLancamento
from common.models import AuditLog
from .forms import DispensaSolicitacaoForm, DispensaAprovacaoForm, NotificacaoFiscalizacaoForm, AutoInfracaoComercioForm, AutoInfracaoSomForm, OficioInternoForm, OficioAcaoForm
from .views_estatisticas import estatisticas_abordados, estatisticas_abordados_graficos, estatisticas_policiamentos, estatisticas_policiamentos_graficos
import calendar
from datetime import date, timedelta
from django.db.models import Count, Avg, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.utils.safestring import mark_safe

@login_required
def dashboard(request):
    hoje = timezone.localdate()
    bos_abertos = BO.objects.filter(emissao__date=hoje, status__in=['EDICAO','FINALIZADO']).order_by('-emissao')[:50]
    try:
        # Alinhar com o painel CECOM: listar todos os talões ABERTOS (não só do dia)
        taloes_abertos = (
            Talao.objects.select_related('viatura', 'codigo_ocorrencia', 'codigo_ocorrencia__grupo')
            .filter(status='ABERTO')
            .order_by('-iniciado_em')
        )
    except Exception:
        taloes_abertos = []
    # Integrantes por viatura ativa (Plantão CECOM) para fallback
    ativos = PlantaoCECOM.objects.select_related('viatura').prefetch_related('participantes__usuario').filter(ativo=True, viatura__isnull=False)
    func_map = { 'ENC': 'Enc', 'MOT': 'Mot', 'AUX1': 'Aux1', 'AUX2': 'Aux2' }
    integrantes_map = {}
    for p in ativos:
        try:
            nomes = []
            for part in p.participantes.select_related('usuario').filter(saida_em__isnull=True):
                u = part.usuario
                if not u:
                    continue
                nome = (getattr(u,'get_full_name',lambda: '')() or getattr(u,'username','')).strip()
                label = func_map.get(part.funcao or '', '')
                nomes.append(f"{label+': ' if label else ''}{nome}")
            integrantes_map[p.viatura_id] = " · ".join(nomes)
        except Exception:
            integrantes_map[p.viatura_id] = ""
    # Equipe (A/B/C/D) do plantão CECOM ativo (global)
    plantao_equipe = ''
    try:
        ativo_global = PlantaoCecomPrincipal.objects.filter(ativo=True).order_by('-inicio').first()
        if ativo_global and hasattr(ativo_global, 'livro') and getattr(ativo_global.livro, 'equipe_plantao', ''):
            plantao_equipe = ativo_global.livro.equipe_plantao or ''
    except Exception:
        plantao_equipe = ''
    # Fallback: sessão do módulo de Talões
    if not plantao_equipe:
        try:
            plantao_equipe = (request.session.get(SESSION_PLANTAO) or '').strip()
        except Exception:
            plantao_equipe = ''
    # Últimas 2 escalas adicionadas/atualizadas
    ultimas_escalas = EscalaMensal.objects.order_by('-updated_at', '-created_at')[:2]
    audiencia_doc = Audiencias.objects.order_by('-updated_at', '-created_at').first()
    ultimas_os = OrdemServico.objects.order_by('-updated_at', '-created_at')[:2]
    ultimas_od = OficioDiverso.objects.order_by('-updated_at', '-created_at')[:4]

    # Cartão: Banco de Horas (linha do usuário logado)
    try:
        saldo_obj, _ = BancoHorasSaldo.objects.get_or_create(user=request.user)
        saldo_val = int(getattr(saldo_obj, 'saldo_minutos', 0) or 0)
    except Exception:
        saldo_val = 0
    def _fmt_hhmm(m: int) -> str:
        m = abs(int(m or 0)); h = m // 60; mm = m % 60; return f"{h:02d}:{mm:02d}"
    try:
        nome_user = (request.user.get_full_name() or request.user.get_username()).strip()
    except Exception:
        nome_user = request.user.get_username()
    try:
        from users.models import Perfil
        perf = getattr(request.user, 'perfil', None) or Perfil.objects.filter(user=request.user).first()
        matricula = getattr(perf, 'matricula', '') or ''
    except Exception:
        matricula = ''
    if saldo_val >= 0:
        pos_str = _fmt_hhmm(saldo_val)
        dev_str = '00:00'
    else:
        pos_str = '00:00'
        dev_str = _fmt_hhmm(-saldo_val)
    banco_user = {
        'nome': nome_user,
        'matricula': matricula,
        'saldo_minutos': saldo_val,
        'positivas': pos_str,
        'devidas': dev_str,
    }
    return render(request, 'core/dashboard.html', {
        'bos_abertos': bos_abertos,
        'taloes_abertos': taloes_abertos,
        'ultimas_escalas': ultimas_escalas,
        'audiencia_doc': audiencia_doc,
        'ultimas_os': ultimas_os,
        'ultimas_od': ultimas_od,
        'integrantes_map': integrantes_map,
        'plantao_equipe': plantao_equipe,
        'banco_user': banco_user,
    })

@login_required
def banco_de_horas(request):
    # Permissão básica de gestão
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    can_manage = request.user.is_superuser or (request.user.username.lower() in allowed_users)
    # Acesso restrito à página principal
    if not can_manage:
        return HttpResponseForbidden('Página restrita ao administrativo e comando.')

    # Filtro de busca
    q = (request.GET.get('q') or '').strip()
    from users.models import Perfil
    perfis = Perfil.objects.select_related('user').filter(ativo=True)
    if q:
        from django.db.models import Q
        perfis = perfis.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(matricula__icontains=q)
        )
    perfis = perfis.order_by('user__first_name', 'user__username')

    # Paginação igual à lista de BO: 20 por página
    paginator = Paginator(perfis, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Mapear saldos atuais (somente dos perfis desta página)
    user_ids = list(page_obj.object_list.values_list('user_id', flat=True))
    saldos_map = {s.user_id: s.saldo_minutos for s in BancoHorasSaldo.objects.filter(user_id__in=user_ids)}

    def fmt_hhmm(minutos: int) -> str:
        m = abs(int(minutos or 0))
        h = m // 60
        mm = m % 60
        return f"{h:02d}:{mm:02d}"

    linhas = []
    for p in page_obj.object_list:
        u = p.user
        nome = (u.get_full_name() or u.get_username()).strip()
        saldo = int(saldos_map.get(u.id, 0) or 0)
        if saldo >= 0:
            pos_str = fmt_hhmm(saldo)
            dev_str = "00:00"
        else:
            pos_str = "00:00"
            dev_str = fmt_hhmm(-saldo)
        linhas.append({
            'user_id': u.id,
            'nome': nome,
            'matricula': p.matricula or '',
            'saldo_minutos': saldo,
            'positivas': pos_str,
            'devidas': dev_str,
        })

    # querystring base para manter filtros durante paginação
    qd = request.GET.copy()
    if 'page' in qd:
        qd.pop('page')
    base_query = qd.urlencode()
    extra_query = ('&' + base_query) if base_query else ''

    return render(request, 'core/adm_banco_horas.html', {
        'linhas': linhas,
        'q': q,
        'can_manage': can_manage,
        'page_obj': page_obj,
        'extra_query': extra_query,
    })


@login_required
def banco_de_horas_ajustar(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido'}, status=405)
    # Permissão
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if not (request.user.is_superuser or request.user.username.lower() in allowed_users):
        return JsonResponse({'ok': False, 'error': 'Sem permissão'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}') if request.body else request.POST
    except Exception:
        payload = request.POST

    try:
        user_id = int(payload.get('user_id'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'user_id inválido'}, status=400)
    acao = (payload.get('action') or '').lower()  # 'add' | 'remove'
    hhmm = (payload.get('hhmm') or '').strip()
    motivo = (payload.get('motivo') or '').strip()
    if acao not in {'add','remove'}:
        return JsonResponse({'ok': False, 'error': 'Ação inválida'}, status=400)
    # Validar HH:MM
    if not hhmm or ':' not in hhmm:
        return JsonResponse({'ok': False, 'error': 'Informe horas no formato HH:MM'}, status=400)
    try:
        hh, mm = hhmm.split(':', 1)
        horas = int(hh)
        minutos = int(mm)
        if horas < 0 or minutos < 0 or minutos >= 60:
            raise ValueError()
        total_min = horas * 60 + minutos
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Horas inválidas (use HH:MM)'}, status=400)

    # Carregar usuário
    from django.contrib.auth import get_user_model
    U = get_user_model()
    try:
        alvo = U.objects.get(pk=user_id)
    except U.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Usuário não encontrado'}, status=404)

    # Sinal do lançamento
    signed = total_min if acao == 'add' else -total_min
    try:
        BancoHorasLancamento.ajustar_saldo(
            alvo,
            signed,
            origem='MANUAL',
            motivo=motivo,
            created_by=request.user,
            ref_type='',
            ref_id='',
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    # Retornar novo saldo formatado
    saldo_obj, _ = BancoHorasSaldo.objects.get_or_create(user=alvo)
    saldo = int(saldo_obj.saldo_minutos or 0)
    def fmt(mins: int) -> str:
        m = abs(int(mins or 0)); h = m // 60; mm = m % 60; return f"{h:02d}:{mm:02d}"
    resp = {
        'ok': True,
        'user_id': alvo.id,
        'saldo_minutos': saldo,
        'positivas': fmt(saldo) if saldo >= 0 else '00:00',
        'devidas': fmt(-saldo) if saldo < 0 else '00:00',
    }
    return JsonResponse(resp)


@login_required
def banco_de_horas_lancamentos(request, user_id: int):
    """Lista paginada (20/pg) de lançamentos de Banco de Horas de um usuário,
    com filtro por período (de/até) e por origem.

    Estilo e paginação como nas listas do sistema (usa _partials/pagination.html).
    """
    # Permissão de auditoria igual à tela principal (somente grupo gestor)
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if not (request.user.is_superuser or request.user.username.lower() in allowed_users):
        return HttpResponseForbidden('Sem permissão para visualizar lançamentos.')

    # Carregar usuário alvo
    from django.contrib.auth import get_user_model
    U = get_user_model()
    alvo = get_object_or_404(U.objects.select_related('perfil'), pk=user_id)

    # Filtros
    origem = (request.GET.get('origem') or '').strip()
    de = (request.GET.get('de') or '').strip()
    ate = (request.GET.get('ate') or '').strip()
    q = (request.GET.get('q') or '').strip()

    qs = BancoHorasLancamento.objects.select_related('created_by').filter(user=alvo).order_by('-created_at', '-id')
    if origem:
        qs = qs.filter(origem=origem)
    # Busca textual: motivo, ref_id e username do criador
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(motivo__icontains=q) |
            Q(ref_id__icontains=q) |
            Q(created_by__username__icontains=q)
        )
    # Período por data (naive: considera created_at em data local)
    if de:
        try:
            from datetime import datetime
            dt = datetime.strptime(de, '%Y-%m-%d').date()
            qs = qs.filter(created_at__date__gte=dt)
        except Exception:
            pass
    if ate:
        try:
            from datetime import datetime
            dt = datetime.strptime(ate, '%Y-%m-%d').date()
            qs = qs.filter(created_at__date__lte=dt)
        except Exception:
            pass

    # Export CSV (sem paginação)
    if (request.GET.get('export') or '').lower() == 'csv':
        import csv
        from io import StringIO
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(['Data/Hora','Origem','Minutos','HH:MM','Motivo','Criado por','Ref Tipo','Ref ID'])
        for l in qs:
            mins = int(getattr(l, 'minutos', 0) or 0)
            a = abs(mins); h = a // 60; m = a % 60
            hhmm = f"{h:02d}:{m:02d}"
            criado_por = (getattr(l.created_by, 'get_full_name', lambda: '')() or (getattr(l.created_by, 'username', '') or ''))
            writer.writerow([
                timezone.localtime(l.created_at).strftime('%d/%m/%Y %H:%M') if getattr(l, 'created_at', None) else '',
                l.get_origem_display(),
                f"{mins:+d}",
                hhmm,
                l.motivo or '',
                criado_por,
                l.ref_type or '',
                l.ref_id or '',
            ])
        csv_data = buf.getvalue()
        buf.close()
        resp = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f"attachment; filename=lancamentos_banco_{alvo.id}.csv"
        return resp

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Preparar itens com HH:MM de minutos absolutos
    items = []
    for l in page_obj.object_list:
        mins = int(getattr(l, 'minutos', 0) or 0)
        a = abs(mins)
        h = a // 60
        m = a % 60
        hhmm = f"{h:02d}:{m:02d}"
        items.append({
            'id': l.id,
            'created_at': l.created_at,
            'origem': l.get_origem_display(),
            'minutos': mins,
            'hhmm': hhmm,
            'motivo': l.motivo,
            'created_by': getattr(l.created_by, 'get_full_name', lambda: '')() or (getattr(l.created_by, 'username', '') or ''),
            'ref_type': l.ref_type,
            'ref_id': l.ref_id,
        })

    # querystring base para manter filtros durante paginação
    qd = request.GET.copy()
    if 'page' in qd:
        qd.pop('page')
    base_query = qd.urlencode()
    extra_query = ('&' + base_query) if base_query else ''

    return render(request, 'core/adm_banco_horas_lancamentos.html', {
        'alvo': alvo,
        'perfil': getattr(alvo, 'perfil', None),
    'page_obj': page_obj,
    'items': items,
        'origem': origem,
        'de': de,
        'ate': ate,
        'q': q,
        'ORIGEM_CHOICES': BancoHorasLancamento.ORIGEM_CHOICES,
        'extra_query': extra_query,
        'base_query': base_query,
    })

@login_required
def escala_mensal(request):
    # permissão: apenas alguns usuários podem gerenciar
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    can_manage = request.user.username.lower() in allowed_users
    # ano selecionado
    try:
        ano = int(request.GET.get('ano') or timezone.localdate().year)
    except ValueError:
        ano = timezone.localdate().year
    # anos disponíveis (2025..2100)
    anos = list(range(2025, 2101))
    # nomes dos meses
    mes_nomes = {
        1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
        7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
    }
    # registros existentes
    registros_map = {e.mes: e for e in EscalaMensal.objects.filter(ano=ano)}
    # contexto por mês
    meses = [
        {
            'num': m,
            'nome': mes_nomes[m],
            'registro': registros_map.get(m)
        }
        for m in range(1,13)
    ]
    return render(request, 'core/adm_escala_mensal.html', {
        'ano': ano,
        'anos': anos,
        'meses': meses,
        'can_manage': can_manage,
    })

@login_required
def escala_mensal_upload(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para enviar arquivos')
    try:
        ano = int(request.POST.get('ano'))
        mes = int(request.POST.get('mes'))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Ano/Mês inválidos')
    arq = request.FILES.get('arquivo')
    if not arq:
        return HttpResponseBadRequest('Arquivo obrigatório')
    obj, _created = EscalaMensal.objects.get_or_create(ano=ano, mes=mes)
    # substituir
    obj.arquivo = arq
    obj.save()
    return redirect('core:escala_mensal')

@login_required
def escala_mensal_remover(request, ano: int, mes: int):
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para remover arquivos')
    try:
        obj = EscalaMensal.objects.get(ano=ano, mes=mes)
        obj.delete()
    except EscalaMensal.DoesNotExist:
        pass
    return redirect('core:escala_mensal')

@login_required
def ordem_servico(request):
    # permissão
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    can_manage = request.user.username.lower() in allowed_users
    # ano selecionado
    try:
        ano = int(request.GET.get('ano') or timezone.localdate().year)
    except ValueError:
        ano = timezone.localdate().year
    anos = list(range(2025, 2101))
    mes_nomes = {
        1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
        7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
    }
    # Buscar anexos por mês
    anexos = OrdemServico.objects.filter(ano=ano).order_by('mes', '-updated_at')
    por_mes = {m: [] for m in range(1,13)}
    for a in anexos:
        por_mes[a.mes].append(a)
    meses = [
        {
            'num': m,
            'nome': mes_nomes[m],
            'anexos': por_mes[m],
        }
        for m in range(1,13)
    ]
    return render(request, 'core/adm_ordem_servico.html', {
        'ano': ano,
        'anos': anos,
        'meses': meses,
        'can_manage': can_manage,
    })

@login_required
def ordem_servico_upload(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para enviar arquivos')
    try:
        ano = int(request.POST.get('ano'))
        mes = int(request.POST.get('mes'))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Ano/Mês inválidos')
    arq = request.FILES.get('arquivo')
    if not arq:
        return HttpResponseBadRequest('Arquivo obrigatório')
    OrdemServico.objects.create(ano=ano, mes=mes, arquivo=arq)
    return redirect('core:ordem_servico')

@login_required
def ordem_servico_remover(request, os_id: int):
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para remover arquivos')
    try:
        obj = OrdemServico.objects.get(pk=os_id)
        obj.delete()
    except OrdemServico.DoesNotExist:
        pass
    return redirect('core:ordem_servico')

@login_required
def oficio_diverso(request):
    # permissão
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    can_manage = request.user.username.lower() in allowed_users
    # ano selecionado
    try:
        ano = int(request.GET.get('ano') or timezone.localdate().year)
    except ValueError:
        ano = timezone.localdate().year
    anos = list(range(2025, 2101))
    mes_nomes = {
        1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
        7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
    }
    # Buscar anexos por mês
    anexos = OficioDiverso.objects.filter(ano=ano).order_by('mes', '-updated_at')
    por_mes = {m: [] for m in range(1,13)}
    for a in anexos:
        por_mes[a.mes].append(a)
    meses = [
        {
            'num': m,
            'nome': mes_nomes[m],
            'anexos': por_mes[m],
        }
        for m in range(1,13)
    ]
    return render(request, 'core/adm_oficio_diverso.html', {
        'ano': ano,
        'anos': anos,
        'meses': meses,
        'can_manage': can_manage,
    })

@login_required
def oficio_diverso_upload(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para enviar arquivos')
    try:
        ano = int(request.POST.get('ano'))
        mes = int(request.POST.get('mes'))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Ano/Mês inválidos')
    arq = request.FILES.get('arquivo')
    if not arq:
        return HttpResponseBadRequest('Arquivo obrigatório')
    OficioDiverso.objects.create(ano=ano, mes=mes, arquivo=arq)
    return redirect('core:oficio_diverso')

@login_required
def oficio_diverso_remover(request, od_id: int):
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para remover arquivos')
    try:
        obj = OficioDiverso.objects.get(pk=od_id)
        obj.delete()
    except OficioDiverso.DoesNotExist:
        pass
    return redirect('core:oficio_diverso')

@login_required
def oficio_interno(request):
    """Listas de Ofícios Internos segmentadas por visibilidade:

    - Meus Ofícios: todos criados pelo usuário (qualquer status)
    - Pendente da Aprovação do Supervisor: PEND_SUP visíveis ao criador e ao supervisor designado
    - Pendente da Aprovação do Comando: PEND_SUB/PEND_CMT visíveis ao criador, ao supervisor, ao responsável atual
      e, adicionalmente, para usuários 'comandante' e 'subcomandante' conforme o status
    """
    from django.db.models import Q, Subquery, OuterRef
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()

    base = OficioInterno.objects.select_related('criador', 'supervisor', 'responsavel_atual')

    # Meus Ofícios (sempre visíveis para o criador)
    meus = base.filter(criador=request.user)
    if q:
        meus = meus.filter(
            Q(texto__icontains=q) |
            Q(criador__username__icontains=q) |
            Q(criador__first_name__icontains=q) |
            Q(criador__last_name__icontains=q)
        )
    if status:
        meus = meus.filter(status=status)
    meus = meus.order_by('-created_at')

    # Pendente do Supervisor: visível ao supervisor e ao criador
    sup = base.filter(status='PEND_SUP').filter(Q(supervisor=request.user) | Q(criador=request.user))
    if q:
        sup = sup.filter(
            Q(texto__icontains=q) |
            Q(criador__username__icontains=q) |
            Q(criador__first_name__icontains=q) |
            Q(criador__last_name__icontains=q)
        )
    if status:
        sup = sup.filter(status=status)
    sup = sup.order_by('-created_at')

    # Pendente do Comando (inclui SUB e CMT)
    uname = (request.user.username or '').lower()
    cond_cmd = Q(status__in=['PEND_SUB','PEND_CMT']) & (Q(criador=request.user) | Q(supervisor=request.user) | Q(responsavel_atual=request.user))
    if uname == 'comandante':
        cond_cmd |= Q(status='PEND_CMT')
    if uname == 'subcomandante':
        cond_cmd |= Q(status='PEND_SUB')
    cmd = base.filter(cond_cmd)
    if q:
        cmd = cmd.filter(
            Q(texto__icontains=q) |
            Q(criador__username__icontains=q) |
            Q(criador__first_name__icontains=q) |
            Q(criador__last_name__icontains=q)
        )
    if status:
        cmd = cmd.filter(status=status)
    cmd = cmd.order_by('-created_at')

    # Ofícios em que EU decidi (deferi/indeferi) ou despachei (SUB/CMT)
    # Ordenar pela data/hora da última ação MINHA nesse ofício
    last_my_action = (
        OficioAcao.objects
        .filter(oficio=OuterRef('pk'), autor=request.user, acao__in=['DEFERIR','INDEFERIR','DESP_SUB','DESP_CMT'])
        .order_by('-created_at','-id')
        .values('created_at')[:1]
    )
    last_my_action_tipo = (
        OficioAcao.objects
        .filter(oficio=OuterRef('pk'), autor=request.user, acao__in=['DEFERIR','INDEFERIR','DESP_SUB','DESP_CMT'])
        .order_by('-created_at','-id')
        .values('acao')[:1]
    )
    minhas_acoes = (
        base
        .annotate(minha_ultima_acao=Subquery(last_my_action))
        .annotate(minha_ultima_acao_tipo=Subquery(last_my_action_tipo))
        .filter(minha_ultima_acao__isnull=False)
    )
    if q:
        minhas_acoes = minhas_acoes.filter(
            Q(texto__icontains=q) |
            Q(criador__username__icontains=q) |
            Q(criador__first_name__icontains=q) |
            Q(criador__last_name__icontains=q)
        )
    if status:
        minhas_acoes = minhas_acoes.filter(status=status)
    minhas_acoes = minhas_acoes.order_by('-minha_ultima_acao', '-created_at')

    # Paginação (5 por lista), com parâmetros independentes
    def _page(qs, name: str):
        paginator = Paginator(qs, 5)
        try:
            num = int(request.GET.get(name) or 1)
        except (TypeError, ValueError):
            num = 1
        return paginator.get_page(num)

    meus_page = _page(meus, 'page_meus')
    sup_page = _page(sup, 'page_sup')
    cmd_page = _page(cmd, 'page_cmd')
    minhas_page = _page(minhas_acoes, 'page_minhas')

    # querystrings extras para preservar filtros e outras páginas
    qd_all = request.GET.copy()
    def _extra_without(param: str) -> str:
        qd = qd_all.copy()
        if param in qd:
            qd.pop(param)
        base_qs = qd.urlencode()
        return ('&' + base_qs) if base_qs else ''

    extra_meus = _extra_without('page_meus')
    extra_sup = _extra_without('page_sup')
    extra_cmd = _extra_without('page_cmd')
    extra_minhas = _extra_without('page_minhas')

    return render(request, 'core/adm_oficio_interno.html', {
        'q': q,
        'status': status,
        'STATUS_CHOICES': OficioInterno.STATUS_CHOICES,
        'meus_page': meus_page,
        'sup_page': sup_page,
        'cmd_page': cmd_page,
        'minhas_page': minhas_page,
        'minhas_acoes_list': minhas_page.object_list,
        'extra_meus': extra_meus,
        'extra_sup': extra_sup,
        'extra_cmd': extra_cmd,
        'extra_minhas': extra_minhas,
    })

@login_required
def oficio_interno_novo(request):
    if request.method == 'POST':
        form = OficioInternoForm(request.POST)
        if form.is_valid():
            obj = form.save(user=request.user)
            # ação inicial
            try:
                OficioAcao.objects.create(oficio=obj, autor=request.user, acao='CRIAR', observacao='')
            except Exception:
                pass
            # notificar supervisor
            try:
                from common.models import PushDevice
                from common.views import enviar_push
                tokens = list(PushDevice.objects.filter(user=obj.supervisor, enabled=True).values_list('token', flat=True))
                if tokens:
                    enviar_push(tokens, title='Ofício Interno', body='Novo ofício pendente para sua análise.', data={'kind':'oficio','oficio_id':obj.id})
            except Exception:
                pass
            messages.success(request, 'Ofício criado e enviado ao supervisor.')
            return redirect('core:oficio_interno')
    else:
        form = OficioInternoForm()
    return render(request, 'core/oficio_interno_form.html', {
        'form': form,
        'is_edit': False,
    })

@login_required
def oficio_interno_ver(request, pk: int):
    obj = get_object_or_404(OficioInterno.objects.select_related('criador','supervisor','responsavel_atual'), pk=pk)
    # Visibilidade: criador, supervisor, responsável atual; CMT/SUBCMT conforme status
    uname = (request.user.username or '').lower()
    pode_ver = (
        request.user == obj.criador or
        request.user == obj.supervisor or
        (obj.responsavel_atual_id and request.user == obj.responsavel_atual) or
        (uname == 'comandante' and obj.status == 'PEND_CMT') or
        (uname == 'subcomandante' and obj.status == 'PEND_SUB')
    )
    # Participantes por ação (quem decidiu/ despachou) também podem visualizar
    if not pode_ver:
        try:
            if obj.acoes.filter(autor=request.user).exists():
                pode_ver = True
        except Exception:
            pass
    if not pode_ver:
        return HttpResponseForbidden('Sem permissão para visualizar este ofício.')
    pode_excluir = request.user.is_superuser or request.user.username.lower() == 'moises'
    pode_decidir = False
    allowed_actions = []
    if obj.status == 'PEND_SUP' and request.user == obj.supervisor:
        pode_decidir = True
        allowed_actions = [('DEFERIR','Deferir'), ('INDEFERIR','Indeferir'), ('DESP_SUB','Despachar para SUBCMT'), ('DESP_CMT','Despachar para CMT')]
    if obj.status == 'PEND_SUB' and request.user.username.lower() == 'subcomandante':
        pode_decidir = True
        allowed_actions = [('DEFERIR','Deferir'), ('INDEFERIR','Indeferir')]
    if obj.status == 'PEND_CMT' and request.user.username.lower() == 'comandante':
        pode_decidir = True
        allowed_actions = [('DEFERIR','Deferir'), ('INDEFERIR','Indeferir')]
    acao_form = OficioAcaoForm() if pode_decidir else None
    if acao_form and allowed_actions:
        acao_form.fields['acao'].choices = allowed_actions
    return render(request, 'core/oficio_interno_ver.html', {
        'obj': obj,
        'acoes': obj.acoes.all(),
        'acao_form': acao_form,
        'pode_excluir': pode_excluir,
    })

@login_required
def oficio_interno_excluir(request, pk: int):
    obj = get_object_or_404(OficioInterno, pk=pk)
    if not (request.user.is_superuser or request.user.username.lower() == 'moises'):
        return HttpResponseForbidden('Sem permissão para excluir.')
    if request.method == 'POST':
        obj.delete()
        return redirect('core:oficio_interno')
    return render(request, 'core/confirm_delete.html', {
        'titulo': f'Excluir Ofício #{obj.id}',
        'mensagem': 'Tem certeza que deseja excluir? Esta ação não pode ser desfeita.',
        'action_url': request.path,
    })

@login_required
def oficio_interno_acao(request, pk: int):
    obj = get_object_or_404(OficioInterno.objects.select_related('criador','supervisor','responsavel_atual'), pk=pk)
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')
    form = OficioAcaoForm(request.POST)
    if not form.is_valid():
        return render(request, 'core/oficio_interno_ver.html', {
            'obj': obj,
            'acoes': obj.acoes.all(),
            'acao_form': form,
        })
    acao = form.cleaned_data['acao']
    obs = form.cleaned_data.get('observacao') or ''

    allowed = False
    if obj.status == 'PEND_SUP' and request.user == obj.supervisor:
        allowed = True
    if obj.status == 'PEND_SUB' and request.user.username.lower() == 'subcomandante':
        allowed = True
    if obj.status == 'PEND_CMT' and request.user.username.lower() == 'comandante':
        allowed = True
    if not allowed:
        return HttpResponseForbidden('Sem permissão para decidir este ofício.')

    destino = None
    if acao == 'DEFERIR':
        obj.status = 'DEFERIDO'
        obj.responsavel_atual = None
    elif acao == 'INDEFERIR':
        obj.status = 'INDEFERIDO'
        obj.responsavel_atual = None
    elif acao == 'DESP_SUB' and obj.status == 'PEND_SUP':
        obj.status = 'PEND_SUB'
        from django.contrib.auth import get_user_model
        U = get_user_model(); destino = U.objects.filter(username__iexact='subcomandante').first()
        obj.responsavel_atual = destino
    elif acao == 'DESP_CMT' and obj.status == 'PEND_SUP':
        obj.status = 'PEND_CMT'
        from django.contrib.auth import get_user_model
        U = get_user_model(); destino = U.objects.filter(username__iexact='comandante').first()
        obj.responsavel_atual = destino
    else:
        messages.error(request, 'Ação inválida para o status atual.')
        return redirect('core:oficio_interno_ver', pk=obj.pk)

    obj.save(update_fields=['status', 'responsavel_atual', 'updated_at'])
    try:
        OficioAcao.objects.create(oficio=obj, autor=request.user, acao=acao, observacao=obs)
    except Exception:
        pass
    if destino is not None:
        try:
            from common.models import PushDevice
            from common.views import enviar_push
            tokens = list(PushDevice.objects.filter(user=destino, enabled=True).values_list('token', flat=True))
            if tokens:
                enviar_push(tokens, title='Ofício Interno', body='Novo ofício pendente para sua decisão.', data={'kind':'oficio','oficio_id':obj.id})
        except Exception:
            pass
    messages.success(request, 'Decisão registrada.')
    return redirect('core:oficio_interno_ver', pk=obj.pk)

@login_required
def audiencias(request):
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    can_manage = request.user.username.lower() in allowed_users
    doc = Audiencias.objects.order_by('-updated_at', '-created_at').first()
    return render(request, 'core/adm_audiencias.html', {
        'doc': doc,
        'can_manage': can_manage,
    })

@login_required
def audiencias_upload(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para enviar arquivos')
    arq = request.FILES.get('arquivo')
    if not arq:
        return HttpResponseBadRequest('Arquivo obrigatório')
    # substitui o documento único
    Audiencias.objects.all().delete()
    Audiencias.objects.create(arquivo=arq)
    return redirect('core:audiencias')

@login_required
def audiencias_remover(request):
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if request.user.username.lower() not in allowed_users:
        return HttpResponseForbidden('Sem permissão para remover arquivos')
    Audiencias.objects.all().delete()
    return redirect('core:audiencias')

@login_required
def log_sistema(request):
    """Lista de logs do sistema (auditoria). Apenas comando/adm e usuário 'moises'."""
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if (not request.user.is_superuser) and (request.user.username.lower() not in allowed_users):
        return HttpResponseForbidden('Sem permissão para visualizar logs')

    qs = AuditLog.objects.select_related('user').all()
    # filtros simples
    u = request.GET.get('usuario')
    if u:
        qs = qs.filter(user__username__iexact=u)
    m = request.GET.get('metodo')
    if m:
        qs = qs.filter(method__iexact=m)
    de = request.GET.get('de')
    ate = request.GET.get('ate')
    if de:
        try:
            from datetime import datetime
            dt = datetime.strptime(de, '%Y-%m-%d')
            qs = qs.filter(created_at__date__gte=dt.date())
        except Exception:
            pass
    if ate:
        try:
            from datetime import datetime
            dt = datetime.strptime(ate, '%Y-%m-%d')
            qs = qs.filter(created_at__date__lte=dt.date())
        except Exception:
            pass
    qs = qs.order_by('-created_at')

    # paginação
    per_page_options = [10, 25, 50, 100]
    try:
        per_page = int(request.GET.get('per_page') or 25)
    except ValueError:
        per_page = 25
    if per_page not in per_page_options:
        per_page = 25

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # querystring base sem o parâmetro page (para preservar filtros nos links)
    qd = request.GET.copy()
    if 'page' in qd:
        qd.pop('page')
    base_query = qd.urlencode()

    metodos = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    return render(request, 'core/adm_log_sistema.html', {
        'logs': page_obj.object_list,
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'querystring': base_query,
        'metodos': metodos,
    })

@login_required
def log_simplificado(request):
    """Lista de Log Simplificado (eventos legíveis). Mesmo controle de acesso do log técnico."""
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if (not request.user.is_superuser) and (request.user.username.lower() not in allowed_users):
        return HttpResponseForbidden('Sem permissão para visualizar logs')

    from common.models import SimpleLog

    qs = SimpleLog.objects.select_related('user').all()

    u = request.GET.get('usuario')
    if u:
        qs = qs.filter(user__username__iexact=u)
    app = request.GET.get('app')
    if app:
        qs = qs.filter(app_label__iexact=app)
    ev = request.GET.get('evento')
    if ev:
        qs = qs.filter(event__iexact=ev)
    de = request.GET.get('de')
    ate = request.GET.get('ate')
    if de:
        try:
            from datetime import datetime
            dt = datetime.strptime(de, '%Y-%m-%d')
            qs = qs.filter(created_at__date__gte=dt.date())
        except Exception:
            pass
    if ate:
        try:
            from datetime import datetime
            dt = datetime.strptime(ate, '%Y-%m-%d')
            qs = qs.filter(created_at__date__lte=dt.date())
        except Exception:
            pass
    qs = qs.order_by('-created_at', '-id')

    per_page_options = [10, 25, 50, 100]
    try:
        per_page = int(request.GET.get('per_page') or 25)
    except ValueError:
        per_page = 25
    if per_page not in per_page_options:
        per_page = 25

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    qd = request.GET.copy()
    if 'page' in qd:
        qd.pop('page')
    base_query = qd.urlencode()

    # Opções de filtro (listas distintas)
    try:
        apps = list(SimpleLog.objects.order_by().values_list('app_label', flat=True).distinct())
        eventos = list(SimpleLog.objects.order_by().values_list('event', flat=True).distinct())
    except Exception:
        apps, eventos = [], []

    return render(request, 'core/adm_log_simplificado.html', {
        'logs': page_obj.object_list,
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'querystring': base_query,
        'apps': apps,
        'eventos': eventos,
    })

@login_required
def almoxarifado(request):
    """Landing do módulo de Almoxarifado com seções Estoque e Cautelas."""
    return render(request, 'core/adm_almoxarifado.html')

@login_required
def estatisticas(request):
    """Visão geral simples de estatísticas (placeholder).

    Mantém a navegação funcionando com um painel inicial; podemos evoluir com
    gráficos e contagens conforme as métricas desejadas.
    """
    ctx = {}
    try:
        ctx['bos_em_edicao'] = BO.objects.filter(status='EDICAO').count()
        ctx['taloes_abertos'] = Talao.objects.filter(status='ABERTO').count()
        ctx['oficios_pendentes'] = OficioInterno.objects.exclude(status__in=['DEFERIDO','INDEFERIDO']).count()
    except Exception:
        pass
    return render(request, 'core/adm_estatisticas.html', ctx)

@login_required
def estatisticas_bo(request):
    """Estatísticas de BO (BOGCMI) – COMPLETO.

    Abas: dia | mes | semestre | ano (querystring ?tab=). Cada aba define o
    período padrão. Opcionalmente, de/ate podem sobrescrever.

    Exportações CSV: ?export=csv&what=[detalhes|ranking_usuarios|ranking_codigos|dvcm|flagrantes]
    """
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    # Períodos padrão por aba
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de = hoje
        default_ate = hoje
    elif tab == 'mes':
        default_de = hoje.replace(day=1)
        default_ate = hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de = date(hoje.year, 1, 1)
            default_ate = date(hoje.year, 6, 30)
        else:
            default_de = date(hoje.year, 7, 1)
            default_ate = date(hoje.year, 12, 31)
            if hoje < default_ate:
                default_ate = hoje
    else:  # ano
        default_de = date(hoje.year, 1, 1)
        default_ate = hoje

    # Overrides manuais
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate

    qs = BO.objects.select_related('viatura').filter(emissao__date__range=(de, ate))

    # Métricas básicas
    total = qs.count()
    abertos = qs.filter(status='EDICAO').count()
    finalizados = qs.filter(status='FINALIZADO').count()
    offline = qs.filter(offline=True).count()
    por_status = list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd'))
    top_viaturas = (
        qs.values('viatura_id', 'viatura__prefixo')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:5]
    )

    # Séries temporais por dia (para gráficos)
    serie_por_dia = list(
        qs.annotate(dia=TruncDate('emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    # Serializa para JSON seguro (datas como YYYY-MM-DD)
    serie_js = [
        {
            'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''),
            'qtd': int(row.get('qtd') or 0)
        }
        for row in serie_por_dia
    ]

    # Ranking por código de ocorrência (cod_natureza + natureza)
    ranking_codigos = list(
        qs.values('cod_natureza', 'natureza').annotate(qtd=Count('id')).order_by('-qtd')[:20]
    )

    # Ranking por Bairro (normalizado) e cruzado com código
    import unicodedata
    def _norm(txt: str) -> str:
        txt = (txt or '').strip().lower()
        try:
            txt = unicodedata.normalize('NFKD', txt)
            txt = ''.join([c for c in txt if not unicodedata.combining(c)])
        except Exception:
            pass
        return txt

    # Agrupar por bairro normalizado
    bairros_map_display = {}
    from collections import Counter
    c_bairros = Counter()
    for b in qs.values_list('bairro', flat=True):
        nb = _norm(b)
        c_bairros[nb] += 1
        if nb and nb not in bairros_map_display and b:
            bairros_map_display[nb] = b  # primeira variação preserva capitalização
    # Monta top 20 bairros
    ranking_bairros = [
        {
            'bairro': (bairros_map_display.get(nb) or (nb.title() if nb else 'Não informado')),
            'qtd': qtd,
            'bairro_norm': nb,
        }
        for nb, qtd in c_bairros.most_common(20)
    ]

    # Bairros x Códigos (tabela resumida)
    bairros_codigos_raw = (
        qs.values('bairro', 'cod_natureza', 'natureza')
          .annotate(qtd=Count('id'))
          .order_by('bairro', '-qtd')
    )
    bairros_codigos = []
    for row in bairros_codigos_raw:
        nb = _norm(row.get('bairro') or '')
        bairros_codigos.append({
            'bairro': (bairros_map_display.get(nb) or (row.get('bairro') or 'Não informado')),
            'cod': row.get('cod_natureza') or '-',
            'natureza': row.get('natureza') or '-',
            'qtd': int(row.get('qtd') or 0),
        })

    # DV contra Mulher (código A-18 ou natureza contendo 'mulher'/'maria da penha')
    dv_q = (
        Q(cod_natureza__istartswith='A-18') |
        Q(natureza__icontains='mulher') |
        Q(natureza__icontains='maria da penha')
    )
    dv_total = qs.filter(dv_q).count()

    # Flagrantes no período (considera 'SIM' ou valor não vazio)
    flagrantes = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S')).count()

    # Estatística por usuário (ENC encarregado): ranking + top códigos por usuário
    enc_group = (
        qs.values('encarregado_id', 'encarregado__first_name', 'encarregado__last_name', 'encarregado__username')
        .annotate(total=Count('id'))
        .order_by('-total')[:20]
    )
    # Top códigos por usuário (limitando a 3 por usuário para exibição)
    users_ranking = []
    if enc_group:
        enc_ids = [r['encarregado_id'] for r in enc_group if r['encarregado_id']]
        by_user_code = (
            qs.filter(encarregado_id__in=enc_ids)
              .values('encarregado_id', 'cod_natureza', 'natureza')
              .annotate(qtd=Count('id'))
              .order_by('encarregado_id', '-qtd')
        )
        # agregação python
        tmp = {}
        import re
        for row in by_user_code:
            uid = row['encarregado_id']
            cod = row.get('cod_natureza') or ''
            natureza = row.get('natureza') or ''
            # Remove prefixo duplicado do código na natureza, ex.: "A-04 - Homicídio" -> "Homicídio"
            if cod and natureza:
                try:
                    natureza_clean = re.sub(rf'^{re.escape(cod)}\s*[-–—:]?\s*', '', natureza, flags=re.IGNORECASE)
                except Exception:
                    natureza_clean = natureza
            else:
                natureza_clean = natureza
            tmp.setdefault(uid, []).append({'cod': cod, 'natureza': natureza_clean, 'qtd': row['qtd']})
        for r in enc_group:
            uid = r['encarregado_id']
            fn = r.get('encarregado__first_name') or ''
            ln = r.get('encarregado__last_name') or ''
            un = r.get('encarregado__username') or ''
            nome = (f"{fn} {ln}" if (fn or ln) else un).strip()
            users_ranking.append({
                'user_id': uid,
                'nome': nome,
                'total': r['total'],
                'top_codigos': (tmp.get(uid) or [])[:3],
            })

    # DV contra Mulher – quebras (top por código, usuário e viatura)
    dv_por_codigo = list(
        qs.filter(dv_q)
          .values('cod_natureza', 'natureza')
          .annotate(qtd=Count('id'))
          .order_by('-qtd')[:5]
    )
    dv_por_usuario = list(
        qs.filter(dv_q)
          .values('encarregado_id', 'encarregado__first_name', 'encarregado__last_name', 'encarregado__username')
          .annotate(qtd=Count('id'))
          .order_by('-qtd')[:5]
    )
    dv_por_viatura = list(
        qs.filter(dv_q)
          .values('viatura_id', 'viatura__prefixo')
          .annotate(qtd=Count('id'))
          .order_by('-qtd')[:5]
    )
    dv_percent = (round((dv_total / total) * 100, 1) if total else 0.0)

    # Dados para gráficos (Chart.js)
    chart_status_labels = [ (s.get('status') or '-') for s in por_status ]
    chart_status_values = [ int(s.get('qtd') or 0) for s in por_status ]
    top_codigos_10 = ranking_codigos[:10]
    chart_cod_labels = [ (r.get('cod_natureza') or '-') for r in top_codigos_10 ]
    chart_cod_values = [ int(r.get('qtd') or 0) for r in top_codigos_10 ]
    top_users_10 = users_ranking[:10]
    chart_user_labels = [ u.get('nome') for u in top_users_10 ]
    chart_user_values = [ int(u.get('total') or 0) for u in top_users_10 ]

    # Exportação PDF (apresentação)
    if (request.GET.get('export') or '').lower() == 'pdf':
        from django.template.loader import render_to_string
        import tempfile, subprocess
        html = render_to_string('core/adm_estatisticas_bo_pdf.html', {
            'tab': tab,
            'de': de,
            'ate': ate,
            'total': total,
            'abertos': abertos,
            'finalizados': finalizados,
            'offline': offline,
            'dv_total': dv_total,
            'dv_percent': dv_percent,
            'flagrantes': flagrantes,
            'ranking_codigos': ranking_codigos[:10],
            'users_ranking': users_ranking[:10],
            'por_status': por_status,
        })
        try:
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml or not os.path.exists(wkhtml):
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f_html:
                f_html.write(html.encode('utf-8'))
                f_html.flush()
                html_path = f_html.name
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f_pdf:
                pdf_path = f_pdf.name
            # Executa wkhtmltopdf
            args = [wkhtml, '--quiet', html_path, pdf_path]
            subprocess.run(args, check=True)
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path)
            except Exception:
                pass
            try:
                os.unlink(pdf_path)
            except Exception:
                pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=bo_{tab}_{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
            return resp
        except Exception:
            # fallback: retorna HTML simples para salvar/Imprimir como PDF
            resp = HttpResponse(html, content_type='text/html; charset=utf-8')
            resp['Content-Disposition'] = f"inline; filename=bo_{tab}_{de:%Y%m%d}_{ate:%Y%m%d}.html"
            return resp

    if (request.GET.get('export') or '').lower() == 'csv':
        what = (request.GET.get('what') or 'detalhes').lower()
        import csv
        from io import StringIO
        buf = StringIO()
        w = csv.writer(buf)
        if what == 'ranking_usuarios':
            w.writerow(['Usuário','Total','Top códigos'])
            for u in users_ranking:
                top_str = '; '.join([f"{(c['cod'] or '-')}: {c['qtd']}" for c in u['top_codigos']])
                w.writerow([u['nome'], u['total'], top_str])
        elif what == 'ranking_codigos':
            w.writerow(['Código','Natureza','Total'])
            for r in ranking_codigos:
                w.writerow([r['cod_natureza'] or '-', r['natureza'] or '-', r['qtd']])
        elif what == 'dvcm':
            w.writerow(['Número','Emissão','Código','Natureza','Status','Encarregado'])
            for b in qs.filter(dv_q).select_related('encarregado'):
                nome = (getattr(b.encarregado,'get_full_name',lambda:'' )() or getattr(b.encarregado,'username','')) if b.encarregado_id else ''
                w.writerow([b.numero, timezone.localtime(b.emissao).strftime('%d/%m/%Y %H:%M'), b.cod_natureza, b.natureza, b.status, nome])
        elif what == 'flagrantes':
            w.writerow(['Número','Emissão','Código','Natureza','Status','Flagrante'])
            for b in qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S')):
                w.writerow([b.numero, timezone.localtime(b.emissao).strftime('%d/%m/%Y %H:%M'), b.cod_natureza, b.natureza, b.status, b.flagrante])
        else:  # detalhes
            w.writerow(['Número','Emissão','Status','Código','Natureza','Viatura','Encarregado','Offline'])
            for b in qs.select_related('viatura','encarregado'):
                vtr = getattr(b.viatura, 'prefixo', '') or (b.viatura_id or '')
                nome = (getattr(b.encarregado,'get_full_name',lambda:'' )() or getattr(b.encarregado,'username','')) if b.encarregado_id else ''
                w.writerow([b.numero, timezone.localtime(b.emissao).strftime('%d/%m/%Y %H:%M'), b.status, b.cod_natureza, b.natureza, vtr, nome, 'SIM' if b.offline else 'NÃO'])
        data = buf.getvalue(); buf.close()
        resp = HttpResponse(data, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f"attachment; filename=bo_{tab}_{de:%Y%m%d}_{ate:%Y%m%d}.csv"
        return resp

    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'abas': abas,
        'total': total,
        'abertos': abertos,
        'finalizados': finalizados,
        'offline': offline,
        'por_status': por_status,
        'top_viaturas': top_viaturas,
    'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'ranking_codigos': ranking_codigos,
        'ranking_bairros': ranking_bairros,
        'bairros_codigos': bairros_codigos,
        'dv_total': dv_total,
        'dv_percent': dv_percent,
        'dv_por_codigo': dv_por_codigo,
        'dv_por_usuario': dv_por_usuario,
        'dv_por_viatura': dv_por_viatura,
        'flagrantes': flagrantes,
        'users_ranking': users_ranking,
        # Gráficos (JSON)
        'chart_status_labels': mark_safe(json.dumps(chart_status_labels, ensure_ascii=False)),
        'chart_status_values': mark_safe(json.dumps(chart_status_values)),
        'chart_cod_labels': mark_safe(json.dumps(chart_cod_labels, ensure_ascii=False)),
        'chart_cod_values': mark_safe(json.dumps(chart_cod_values)),
        'chart_user_labels': mark_safe(json.dumps(chart_user_labels, ensure_ascii=False)),
        'chart_user_values': mark_safe(json.dumps(chart_user_values)),
    }
    return render(request, 'core/adm_estatisticas_bo.html', ctx)


@login_required
def estatisticas_bo_mapa(request):
    """Página de Mapa de Ocorrências (BOs) com filtros de período, código e bairro."""
    hoje = timezone.localdate()
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{hoje:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = hoje.replace(day=1), hoje

    cod = (request.GET.get('cod') or '').strip()
    bairro = (request.GET.get('bairro') or '').strip()
    q = (request.GET.get('q') or '').strip()

    ctx = {
        'de': de,
        'ate': ate,
        'cod': cod,
        'bairro': bairro,
        'q': q,
    }
    return render(request, 'core/adm_estatisticas_bo_mapa.html', ctx)


@login_required
def estatisticas_bo_mapa_data(request):
    """Endpoint JSON para markers do mapa de BO.

    Filtros: de/ate (emissao), cod (cod_natureza), bairro (icontains), q (busca aproximada em rua/endereco/referencia/bairro).
    """
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de')), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate')), '%Y-%m-%d').date()
    except Exception:
        hoje = timezone.localdate()
        de, ate = hoje.replace(day=1), hoje

    cod = (request.GET.get('cod') or '').strip()
    bairro = (request.GET.get('bairro') or '').strip()
    q = (request.GET.get('q') or '').strip()

    qs = BO.objects.filter(emissao__date__range=(de, ate))
    if cod:
        qs = qs.filter(Q(cod_natureza__iexact=cod) | Q(natureza__icontains=cod))
    if bairro:
        qs = qs.filter(bairro__icontains=bairro)
    if q:
        # busca aproximada por tokens em rua/endereco/referencia/bairro
        tokens = [t for t in q.split() if t]
        for t in tokens:
            qs = qs.filter(
                Q(rua__icontains=t) |
                Q(endereco__icontains=t) |
                Q(referencia__icontains=t) |
                Q(bairro__icontains=t)
            )

    # Construir markers básicos
    items = []
    for b in qs.values('id','numero','emissao','cod_natureza','natureza','rua','numero_endereco','bairro','cidade','uf')[:2000]:
        items.append({
            'id': b['id'],
            'numero': b['numero'],
            'emissao': timezone.localtime(b['emissao']).strftime('%d/%m/%Y %H:%M') if b.get('emissao') else '',
            'cod': b.get('cod_natureza') or '',
            'natureza': b.get('natureza') or '',
            'rua': b.get('rua') or '',
            'numero': b.get('numero_endereco') or '',
            'bairro': b.get('bairro') or '',
            'cidade': b.get('cidade') or '',
            'uf': b.get('uf') or 'SP',
        })

    return JsonResponse({'items': items})


@login_required
def estatisticas_bo_usuario(request):
    """Estatísticas e listagem de BO por Usuário (encarregado).

    - Select com todos usuários (exibe "matrícula — Nome" quando houver).
    - Abas dia/mês/semestre/ano para filtrar o período rapidamente.
    - KPIs simples e tabela com os BOs do período do usuário.
    """
    from users.models import Perfil
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje

    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate

    # Usuário selecionado
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    flag = (request.GET.get('flag') or '').lower()
    user_nome = ''

    # Opções de usuários (ativos) para o select
    perfis = (
        Perfil.objects.select_related('user')
        .filter(ativo=True, user__is_active=True)
        .order_by('matricula', 'user__first_name', 'user__last_name')
    )
    user_options = []
    for p in perfis:
        nome = (p.user.get_full_name() or p.user.username).strip()
        # Ordem invertida: Nome — Matrícula (quando houver matrícula)
        label = f"{nome} — {p.matricula}" if p.matricula else nome
        user_options.append({'id': p.user_id, 'label': label})
        if p.user_id == uid:
            user_nome = nome

    # Base query somente quando há usuário selecionado
    qs = BO.objects.select_related('viatura','encarregado').filter(encarregado_id=uid, emissao__date__range=(de, ate)) if uid else BO.objects.none()
    if uid and flag == 'sim':
        qs = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))
    elif uid and flag == 'nao':
        qs = qs.exclude(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))

    total = qs.count()
    abertos = qs.filter(status='EDICAO').count()
    finalizados = qs.filter(status='FINALIZADO').count()
    offline = qs.filter(offline=True).count()
    flagrantes = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S')).count()

    from django.core.paginator import Paginator
    page_number = request.GET.get('page') or '1'
    bos_qs = qs.order_by('-emissao')
    paginator = Paginator(bos_qs, 50)
    try:
        page_obj = paginator.get_page(page_number)
    except Exception:
        page_obj = paginator.get_page(1)
    bos = list(page_obj.object_list)

    # Export CSV da lista do usuário (respeita filtros)
    if (request.GET.get('export') or '').lower() == 'csv':
        import csv
        from io import StringIO
        buf = StringIO(); w = csv.writer(buf)
        w.writerow(['Número','Emissão','Status','Código','Natureza','Viatura','Offline'])
        for b in qs.select_related('viatura'):
            vtr = getattr(b.viatura, 'prefixo', '') or (b.viatura_id or '')
            w.writerow([b.numero, timezone.localtime(b.emissao).strftime('%d/%m/%Y %H:%M'), b.status, b.cod_natureza, b.natureza, vtr, 'SIM' if b.offline else 'NÃO'])
        data = buf.getvalue(); buf.close()
        resp = HttpResponse(data, content_type='text/csv; charset=utf-8')
        flag_suffix = f"_flag-{flag}" if flag in {'sim','nao'} else ''
        resp['Content-Disposition'] = f"attachment; filename=bo_usuario_{uid}_{de:%Y%m%d}_{ate:%Y%m%d}{flag_suffix}.csv"
        return resp

    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'abas': abas,
        'uid': uid,
        'user_nome': user_nome,
        'user_options': user_options,
        'flag': flag,
        'total': total,
        'abertos': abertos,
        'finalizados': finalizados,
        'offline': offline,
        'flagrantes': flagrantes,
        'bos': bos,
        'page_obj': page_obj,
        'paginator': paginator,
    }
    return render(request, 'core/adm_estatisticas_bo_usuario.html', ctx)


@login_required
def estatisticas_bo_usuario_graficos(request):
    """Página focada em gráficos para um usuário específico.

    Mostra série por dia, pizza por status e barras de códigos mais usados
    no período selecionado.
    """
    from users.models import Perfil
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje

    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate

    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    flag = (request.GET.get('flag') or '').lower()

    # Identificação do usuário (label)
    user_nome = ''
    perfil = Perfil.objects.select_related('user').filter(user_id=uid).first()
    if perfil:
        user_nome = (perfil.user.get_full_name() or perfil.user.username).strip()

    qs = BO.objects.filter(encarregado_id=uid, emissao__date__range=(de, ate)) if uid else BO.objects.none()
    if uid and flag == 'sim':
        qs = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))
    elif uid and flag == 'nao':
        qs = qs.exclude(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))

    total = qs.count()
    por_status = list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd'))
    # Flagrante vs Não
    qtd_flag = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S')).count()
    qtd_nao = total - qtd_flag
    pct_flag = round((qtd_flag / total) * 100, 1) if total else 0.0
    pct_nao = round((qtd_nao / total) * 100, 1) if total else 0.0
    ranking_codigos = list(
        qs.values('cod_natureza', 'natureza').annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )
    serie_por_dia = list(
        qs.annotate(dia=TruncDate('emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie_por_dia
    ]
    chart_status_labels = [ (s.get('status') or '-') for s in por_status ]
    chart_status_values = [ int(s.get('qtd') or 0) for s in por_status ]
    chart_cod_labels = [ (r.get('cod_natureza') or '-') for r in ranking_codigos ]
    chart_cod_values = [ int(r.get('qtd') or 0) for r in ranking_codigos ]

    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'flag': flag,
        'abas': abas,
        'total': total,
        'ranking_codigos': ranking_codigos,
        'por_status': por_status,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'chart_status_labels': mark_safe(json.dumps(chart_status_labels, ensure_ascii=False)),
        'chart_status_values': mark_safe(json.dumps(chart_status_values)),
        'chart_cod_labels': mark_safe(json.dumps(chart_cod_labels, ensure_ascii=False)),
        'chart_cod_values': mark_safe(json.dumps(chart_cod_values)),
        'chart_flag_labels': mark_safe(json.dumps([f'Flagrante {pct_flag}%', f'Não flagrante {pct_nao}%'], ensure_ascii=False)),
        'chart_flag_values': mark_safe(json.dumps([qtd_flag, qtd_nao])),
        'pct_flag': pct_flag,
        'pct_nao': pct_nao,
    }
    return render(request, 'core/adm_estatisticas_bo_usuario_graficos.html', ctx)

@login_required
def estatisticas_bo_usuario_graficos_pdf(request):
    """Exportação PDF dos gráficos por usuário (resumo textual + dados numéricos).

    Geramos um HTML simplificado (sem JS) e convertemos via wkhtmltopdf se disponível.
    """
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    tab = (request.GET.get('tab') or 'mes').lower()
    flag = (request.GET.get('flag') or '').lower()
    from users.models import Perfil
    hoje = timezone.localdate()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    perfil = Perfil.objects.select_related('user').filter(user_id=uid).first()
    user_nome = (perfil.user.get_full_name() or perfil.user.username).strip() if perfil else ''
    qs = BO.objects.filter(encarregado_id=uid, emissao__date__range=(de, ate)) if uid else BO.objects.none()
    if uid and flag == 'sim':
        qs = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))
    elif uid and flag == 'nao':
        qs = qs.exclude(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S'))
    total = qs.count()
    por_status = list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd'))
    qtd_flag = qs.filter(Q(flagrante__iexact='SIM') | Q(flagrante__iexact='S')).count()
    qtd_nao = total - qtd_flag
    pct_flag = round((qtd_flag / total) * 100, 1) if total else 0.0
    pct_nao = round((qtd_nao / total) * 100, 1) if total else 0.0
    ranking_codigos = list(qs.values('cod_natureza','natureza').annotate(qtd=Count('id')).order_by('-qtd')[:10])
    serie_por_dia = list(qs.annotate(dia=TruncDate('emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia'))
    html = render_to_string('core/adm_estatisticas_bo_usuario_graficos_pdf.html', {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'flag': flag,
        'total': total,
        'por_status': por_status,
        'qtd_flag': qtd_flag,
        'qtd_nao': qtd_nao,
        'pct_flag': pct_flag,
        'pct_nao': pct_nao,
        'ranking_codigos': ranking_codigos,
        'serie_por_dia': serie_por_dia,
    })
    # Converter
    try:
        wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
        if not wkhtml or not os.path.exists(wkhtml):
            raise FileNotFoundError('wkhtmltopdf não encontrado')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f_html:
            f_html.write(html.encode('utf-8')); f_html.flush(); html_path=f_html.name
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f_pdf:
            pdf_path = f_pdf.name
        subprocess.run([wkhtml, '--quiet', html_path, pdf_path], check=True)
        with open(pdf_path,'rb') as pf: pdf_bytes = pf.read()
        try: os.unlink(html_path)
        except Exception: pass
        try: os.unlink(pdf_path)
        except Exception: pass
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f"attachment; filename=bo_usuario_graficos_{uid}_{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
        return resp
    except Exception:
        return HttpResponse(html, content_type='text/html; charset=utf-8')

@login_required
def estatisticas_bo_codigo(request):
    """Lista e estatísticas por Código de Ocorrência (BOGCMI).

    - Filtros de período com abas (?tab=dia|mes|semestre|ano) e de/ate
    - Seleção de código por sigla (param 'cod') usando taloes.CodigoOcorrencia
    - Gráficos: série por dia e barras por bairros
    - Export: CSV da lista de BO e PDF de apresentação
    """
    from taloes.models import CodigoOcorrencia
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje

    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate

    # seleção do código
    cod = (request.GET.get('cod') or '').strip()
    cod_obj = None
    if cod:
        cod_obj = CodigoOcorrencia.objects.filter(sigla__iexact=cod).first()

    # base query
    qs = BO.objects.select_related('viatura','encarregado').filter(emissao__date__range=(de, ate))
    if cod:
        qs = qs.filter(cod_natureza__iexact=cod)

    total = qs.count()
    por_status = list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd'))
    por_bairro = list(
        qs.values('bairro').annotate(qtd=Count('id')).order_by('-qtd')[:20]
    )
    serie = list(
        qs.annotate(dia=TruncDate('emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {
            'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''),
            'qtd': int(row.get('qtd') or 0)
        }
        for row in serie
    ]
    # ranking usuários
    usuarios = list(
        qs.values('encarregado_id','encarregado__first_name','encarregado__last_name','encarregado__username')
          .annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )

    # Exports
    exp = (request.GET.get('export') or '').lower()
    if exp == 'csv':
        import csv
        from io import StringIO
        buf = StringIO(); w = csv.writer(buf)
        w.writerow(['Número','Emissão','Status','Bairro','Rua','Viatura','Encarregado','Código','Natureza'])
        for b in qs:
            vtr = getattr(b.viatura,'prefixo','') or (b.viatura_id or '')
            enc = (getattr(b.encarregado,'get_full_name',lambda:'' )() or getattr(b.encarregado,'username','')) if b.encarregado_id else ''
            w.writerow([b.numero, timezone.localtime(b.emissao).strftime('%d/%m/%Y %H:%M'), b.status, b.bairro, b.rua, vtr, enc, b.cod_natureza, b.natureza])
        data = buf.getvalue(); buf.close()
        resp = HttpResponse(data, content_type='text/csv; charset=utf-8')
        suf = f"{cod.lower()}_" if cod else ''
        resp['Content-Disposition'] = f"attachment; filename=bo_por_codigo_{suf}{de:%Y%m%d}_{ate:%Y%m%d}.csv"
        return resp
    if exp == 'pdf':
        from django.template.loader import render_to_string
        import tempfile, subprocess
        html = render_to_string('core/adm_estatisticas_bo_codigo_pdf.html', {
            'tab': tab, 'de': de, 'ate': ate, 'cod': cod, 'cod_obj': cod_obj,
            'total': total, 'por_status': por_status, 'por_bairro': por_bairro, 'usuarios': usuarios,
        })
        try:
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml or not os.path.exists(wkhtml):
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f_html:
                f_html.write(html.encode('utf-8')); f_html.flush(); html_path=f_html.name
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f_pdf:
                pdf_path=f_pdf.name
            subprocess.run([wkhtml, '--quiet', html_path, pdf_path], check=True)
            with open(pdf_path,'rb') as pf: pdf_bytes = pf.read()
            try: os.unlink(html_path)
            except Exception: pass
            try: os.unlink(pdf_path)
            except Exception: pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            suf = f"{cod.lower()}_" if cod else ''
            resp['Content-Disposition'] = f"attachment; filename=bo_codigo_{suf}{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    # dropdown com todos os códigos existentes (para o select)
    codigos = list(CodigoOcorrencia.objects.all().order_by('sigla').values('sigla','descricao'))

    # datasets gráfico
    chart_bairros_labels = [ (r.get('bairro') or '-') for r in por_bairro ]
    chart_bairros_values = [ int(r.get('qtd') or 0) for r in por_bairro ]
    chart_status_labels = [ (s.get('status') or '-') for s in por_status ]
    chart_status_values = [ int(s.get('qtd') or 0) for s in por_status ]
    ctx = {
        'abas': [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')],
        'tab': tab, 'de': de, 'ate': ate,
        'cod': cod, 'cod_obj': cod_obj,
        'codigos': codigos,
        'total': total,
        'por_status': por_status,
        'por_bairro': por_bairro,
        'usuarios': usuarios,
    'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'chart_bairros_labels': mark_safe(json.dumps(chart_bairros_labels, ensure_ascii=False)),
        'chart_bairros_values': mark_safe(json.dumps(chart_bairros_values)),
        'chart_status_labels': mark_safe(json.dumps(chart_status_labels, ensure_ascii=False)),
        'chart_status_values': mark_safe(json.dumps(chart_status_values)),
    }
    return render(request, 'core/adm_estatisticas_bo_codigo.html', ctx)

@login_required
def estatisticas_ait(request):
    """Estatísticas de AIT (números registrados nos Talões).

    Base: taloes.AitRegistro (campo criado_em).
    Filtros: ?de=YYYY-MM-DD&ate=YYYY-MM-DD.
    """
    from taloes.models import AitRegistro
    from collections import Counter
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Select de integrantes (GCMs)
    try:
        from users.models import Perfil
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        user_options = []
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
    except Exception:
        user_options = []
    hoje = timezone.localdate()
    try:
        de_str = (request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}")
        ate_str = (request.GET.get('ate') or f"{hoje:%Y-%m-%d}")
        from datetime import datetime
        de = datetime.strptime(de_str, '%Y-%m-%d').date()
        ate = datetime.strptime(ate_str, '%Y-%m-%d').date()
    except Exception:
        de = hoje.replace(day=1)
        ate = hoje
    # uid apenas para manter seleção visual nas métricas desta tela; será aplicado no CSV (export) se informado
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0

    qs = AitRegistro.objects.select_related(
        'talao', 
        'integrante',
        'talao__criado_por',
        'talao__encarregado',
        'talao__motorista',
        'talao__auxiliar1',
        'talao__auxiliar2'
    ).filter(criado_em__date__range=(de, ate))
    
    # Filtro por GCM (considera integrante do AIT OU todos os campos do talão)
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(integrante_id=uid) |
            Q(talao__criado_por_id=uid) | 
            Q(talao__encarregado_id=uid) | 
            Q(talao__motorista_id=uid) | 
            Q(talao__auxiliar1_id=uid) | 
            Q(talao__auxiliar2_id=uid)
        )
    
    # Exportação CSV (detalhes) do período; aplica filtro de usuário se fornecido
    if (request.GET.get('export') or '').lower() == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f"attachment; filename=ait_{de:%Y%m%d}_{ate:%Y%m%d}{('_user_'+str(uid)) if uid else ''}.csv"
        w = csv.writer(resp)
        w.writerow(['ID','Criado em','Talao ID','Integrante ID','Integrante','Matrícula'])
        for r in qs.select_related('integrante__perfil').order_by('criado_em'):
            u = getattr(r,'integrante',None)
            nome = (u.get_full_name() or u.username).strip() if u else ''
            perf = getattr(u,'perfil',None) if u else None
            mat = getattr(perf,'matricula','') if perf else ''
            criado = timezone.localtime(getattr(r,'criado_em', None)).strftime('%Y-%m-%d %H:%M:%S') if getattr(r,'criado_em', None) else ''
            w.writerow([r.id, criado, getattr(r,'talao_id',''), getattr(u,'id',''), nome, mat])
        return resp
    
    total = qs.count()
    
    # Top 5 por GCM (considera integrante do AIT + todos os integrantes do talão)
    contador_integrantes = Counter()
    for ait in qs:
        # Coletar integrantes: primeiro o integrante direto do AIT
        integrantes_ids = set()
        if ait.integrante_id:
            integrantes_ids.add(ait.integrante_id)
        
        # Depois todos os integrantes do talão
        talao = ait.talao
        if talao:
            if talao.criado_por_id:
                integrantes_ids.add(talao.criado_por_id)
            if talao.encarregado_id:
                integrantes_ids.add(talao.encarregado_id)
            if talao.motorista_id:
                integrantes_ids.add(talao.motorista_id)
            if talao.auxiliar1_id:
                integrantes_ids.add(talao.auxiliar1_id)
            if talao.auxiliar2_id:
                integrantes_ids.add(talao.auxiliar2_id)
        
        # Incrementar contador para cada integrante
        for user_id in integrantes_ids:
            contador_integrantes[user_id] += 1
    
    # Montar top 5 com dados dos usuários
    top_integrantes = []
    for user_id, qtd in contador_integrantes.most_common(5):
        try:
            user = User.objects.get(pk=user_id)
            top_integrantes.append({
                'integrante_id': user_id,
                'integrante__first_name': user.first_name,
                'integrante__last_name': user.last_name,
                'integrante__username': user.username,
                'qtd': qtd
            })
        except User.DoesNotExist:
            pass
    # Top 5 por dia do período
    top_dias = (
        qs.extra(select={'dia': "DATE(criado_em)"})
        .values('dia')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:10]
    )

    # Exportação PDF (apresentação)
    if (request.GET.get('export') or '').lower() == 'pdf':
        # Top 10 para PDF
        top_10_pdf = []
        for user_id, qtd in contador_integrantes.most_common(10):
            try:
                user = User.objects.get(pk=user_id)
                top_10_pdf.append({
                    'integrante__first_name': user.first_name,
                    'integrante__last_name': user.last_name,
                    'integrante__username': user.username,
                    'qtd': qtd
                })
            except User.DoesNotExist:
                pass
        
        html = render_to_string('core/adm_estatisticas_ait_pdf.html', {
            'de': de,
            'ate': ate,
            'total': total,
            'top_integrantes': top_10_pdf,
            'top_dias': list(
                qs.extra(select={'dia': "DATE(criado_em)"})
                  .values('dia').annotate(qtd=Count('id')).order_by('-qtd')[:10]
            ),
            'uid': uid,
        })
        try:
            import tempfile, os, subprocess
            from django.conf import settings
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as fhtml:
                fhtml.write(html.encode('utf-8'))
                html_path = fhtml.name
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml:
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as fpdf:
                pdf_path = fpdf.name
            args = [wkhtml, '--quiet', html_path, pdf_path]
            subprocess.check_call(args)
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path)
                os.unlink(pdf_path)
            except Exception:
                pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=ait_{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    ctx = {
        'de': de,
        'ate': ate,
        'total': total,
        'top_integrantes': top_integrantes,
        'top_dias': top_dias,
        'user_options': user_options,
        'uid': uid,
    }
    return render(request, 'core/adm_estatisticas_ait.html', ctx)

@login_required
def estatisticas_ait_graficos(request):
    """Gráfico de linha (série diária) de AIT por período, com filtro opcional por integrante."""
    from taloes.models import AitRegistro
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    # Options para select
    user_options = []
    user_nome = ''
    if Perfil:
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
            if p.user_id == uid:
                user_nome = nome
    # Query base
    qs = AitRegistro.objects.filter(criado_em__date__range=(de, ate))
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(integrante_id=uid) |
            Q(talao__criado_por_id=uid) | 
            Q(talao__encarregado_id=uid) | 
            Q(talao__motorista_id=uid) | 
            Q(talao__auxiliar1_id=uid) | 
            Q(talao__auxiliar2_id=uid)
        )
    total = qs.count()
    serie = list(
        qs.annotate(dia=TruncDate('criado_em')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie
    ]
    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'user_options': user_options,
        'total': total,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'abas': abas,
    }
    return render(request, 'core/adm_estatisticas_ait_graficos.html', ctx)

@login_required
def estatisticas_cecom(request):
    """Estatísticas de Despachos do CECOM.

    Métricas: totais por status no período, tempos médios (resposta/finalização).
    """
    from cecom.models import DespachoOcorrencia
    # Options para selects (Operador e Código de Ocorrência)
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    try:
        from taloes.models import CodigoOcorrencia
    except Exception:
        CodigoOcorrencia = None
    hoje = timezone.localdate()
    try:
        de_str = (request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}")
        ate_str = (request.GET.get('ate') or f"{hoje:%Y-%m-%d}")
        from datetime import datetime
        de = datetime.strptime(de_str, '%Y-%m-%d').date()
        ate = datetime.strptime(ate_str, '%Y-%m-%d').date()
    except Exception:
        de = hoje.replace(day=1)
        ate = hoje

    # Filtros opcionais
    try:
        op = int(request.GET.get('op') or 0)
    except Exception:
        op = 0
    cod = (request.GET.get('cod') or '').strip()

    qs = DespachoOcorrencia.objects.select_related('viatura','despachado_por').filter(despachado_em__date__range=(de, ate))
    if op:
        qs = qs.filter(despachado_por_id=op)
    if cod:
        qs = qs.filter(cod_natureza=cod)
    # Export CSV (detalhes)
    if (request.GET.get('export') or '').lower() == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        name_parts = [f"cecom_{de:%Y%m%d}_{ate:%Y%m%d}"]
        if op:
            name_parts.append(f"op{op}")
        if cod:
            name_parts.append(f"cod_{cod}")
        resp['Content-Disposition'] = f"attachment; filename={'_'.join(name_parts)}.csv"
        w = csv.writer(resp)
        w.writerow(['ID','Despachado em','Viatura','Código','Descrição','Status','Respondido em','Finalizado em','Arquivado','Operador'])
        for d in qs.order_by('despachado_em'):
            disp = timezone.localtime(d.despachado_em).strftime('%Y-%m-%d %H:%M:%S') if d.despachado_em else ''
            resp_dt = timezone.localtime(d.respondido_em).strftime('%Y-%m-%d %H:%M:%S') if d.respondido_em else ''
            fin_dt = timezone.localtime(d.finalizado_em).strftime('%Y-%m-%d %H:%M:%S') if d.finalizado_em else ''
            viat = getattr(d.viatura,'prefixo','') if getattr(d,'viatura',None) else ''
            operador = (getattr(d.despachado_por,'get_full_name',lambda: '')() or getattr(d.despachado_por,'username','')).strip() if getattr(d,'despachado_por',None) else ''
            w.writerow([d.id, disp, viat, d.cod_natureza or '', d.natureza or '', d.status, resp_dt, fin_dt, 'SIM' if d.arquivado else 'NÃO', operador])
        return resp
    total = qs.count()
    por_status = list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd'))
    pendentes = qs.filter(status='PENDENTE').count()
    aceitos = qs.filter(status__in=['ACEITO','EM_ANDAMENTO','FINALIZADO']).count()
    recusados = qs.filter(status='RECUSADO').count()
    finalizados = qs.filter(status='FINALIZADO').count()

    # Tempos médios (em minutos)
    from django.db.models.functions import Cast
    resp_com_delta = qs.filter(respondido_em__isnull=False).annotate(
        delta=ExpressionWrapper(F('respondido_em') - F('despachado_em'), output_field=DurationField())
    )
    media_resp = resp_com_delta.aggregate(m=Avg('delta')).get('m')
    fim_com_delta = qs.filter(finalizado_em__isnull=False).annotate(
        delta=ExpressionWrapper(F('finalizado_em') - F('despachado_em'), output_field=DurationField())
    )
    media_fim = fim_com_delta.aggregate(m=Avg('delta')).get('m')

    def fmt_minutos(td):
        try:
            total_sec = int(td.total_seconds())
            m = total_sec // 60
            h = m // 60
            mm = m % 60
            return f"{h:02d}:{mm:02d}"
        except Exception:
            return None

    # Montar listas para selects
    user_options = []
    if Perfil:
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
    codigo_options = []
    if CodigoOcorrencia:
        codigo_options = list(CodigoOcorrencia.objects.all().order_by('sigla').values('sigla','descricao'))

    # Rankings
    ranking_codigos = list(
        qs.values('cod_natureza', 'natureza').annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )
    ranking_operadores = list(
        qs.values('despachado_por__first_name', 'despachado_por__last_name', 'despachado_por__username')
          .annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )

    # Export PDF (apresentação)
    if (request.GET.get('export') or '').lower() == 'pdf':
        html = render_to_string('core/adm_estatisticas_cecom_pdf.html', {
            'de': de, 'ate': ate,
            'total': total,
            'por_status': list(qs.values('status').annotate(qtd=Count('id')).order_by('-qtd')),
            'pendentes': pendentes,
            'aceitos': aceitos,
            'recusados': recusados,
            'finalizados': finalizados,
            'media_resposta': fmt_minutos(media_resp) if media_resp else None,
            'media_finalizacao': fmt_minutos(media_fim) if media_fim else None,
            'ranking_codigos': list(qs.values('cod_natureza','natureza').annotate(qtd=Count('id')).order_by('-qtd')[:10]),
            'ranking_operadores': list(qs.values('despachado_por__first_name','despachado_por__last_name','despachado_por__username').annotate(qtd=Count('id')).order_by('-qtd')[:10]),
            'op': op, 'cod': cod,
        })
        try:
            import tempfile, os, subprocess
            from django.conf import settings
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as fhtml:
                fhtml.write(html.encode('utf-8'))
                html_path = fhtml.name
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml:
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as fpdf:
                pdf_path = fpdf.name
            subprocess.check_call([wkhtml, '--quiet', html_path, pdf_path])
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path); os.unlink(pdf_path)
            except Exception:
                pass
            name_parts = [f"cecom_{de:%Y%m%d}_{ate:%Y%m%d}"]
            if op:
                name_parts.append(f"op{op}")
            if cod:
                name_parts.append(f"cod_{cod}")
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename={'_'.join(name_parts)}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    ctx = {
        'de': de,
        'ate': ate,
        'op': op,
        'cod': cod,
        'user_options': user_options,
        'codigo_options': codigo_options,
        'total': total,
        'por_status': por_status,
        'pendentes': pendentes,
        'aceitos': aceitos,
        'recusados': recusados,
        'finalizados': finalizados,
        'media_resposta': fmt_minutos(media_resp) if media_resp else None,
        'media_finalizacao': fmt_minutos(media_fim) if media_fim else None,
        'ranking_codigos': ranking_codigos,
        'ranking_operadores': ranking_operadores,
    }
    return render(request, 'core/adm_estatisticas_cecom.html', ctx)


@login_required
def estatisticas_cecom_graficos(request):
    """Gráficos de despachos CECOM (série diária) com filtros de Operador e Código."""
    from cecom.models import DespachoOcorrencia
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    try:
        from taloes.models import CodigoOcorrencia
    except Exception:
        CodigoOcorrencia = None

    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    try:
        op = int(request.GET.get('op') or 0)
    except Exception:
        op = 0
    cod = (request.GET.get('cod') or '').strip()

    # Options
    user_options = []
    op_nome = ''
    if Perfil:
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
            if p.user_id == op:
                op_nome = nome
    codigo_options = []
    cod_label = ''
    if CodigoOcorrencia:
        for c in CodigoOcorrencia.objects.all().order_by('sigla'):
            codigo_options.append({'sigla': c.sigla, 'descricao': c.descricao})
            if cod and c.sigla == cod:
                cod_label = f"{c.sigla} — {c.descricao}"

    # Query base
    qs = DespachoOcorrencia.objects.filter(despachado_em__date__range=(de, ate))
    if op:
        qs = qs.filter(despachado_por_id=op)
    if cod:
        qs = qs.filter(cod_natureza=cod)
    total = qs.count()
    serie = list(
        qs.annotate(dia=TruncDate('despachado_em')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie
    ]
    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'op': op,
        'op_nome': op_nome,
        'cod': cod,
        'cod_label': cod_label,
        'user_options': user_options,
        'codigo_options': codigo_options,
        'total': total,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'abas': abas,
    }
    return render(request, 'core/adm_estatisticas_cecom_graficos.html', ctx)

@login_required
def estatisticas_remocoes(request):
    """Estatísticas de Veículos Removidos (BOGCMI - VeiculoEnvolvido com campos de apreensão).

    Critério: considerar removido se possuir algum campo de apreensão preenchido
    (apreensao_ait, apreensao_crr, apreensao_destino, apreensao_responsavel_guincho).
    Período baseado em BO.emissao (data).
    """
    from bogcmi.models import VeiculoEnvolvido
    from collections import Counter
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    
    hoje = timezone.localdate()
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    try:
        de_str = (request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}")
        ate_str = (request.GET.get('ate') or f"{hoje:%Y-%m-%d}")
        from datetime import datetime
        de = datetime.strptime(de_str, '%Y-%m-%d').date()
        ate = datetime.strptime(ate_str, '%Y-%m-%d').date()
    except Exception:
        de = hoje.replace(day=1)
        ate = hoje

    # Filtro por encarregado (usuario)
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0

    base = VeiculoEnvolvido.objects.select_related(
        'bo',
        'bo__encarregado',
        'bo__motorista',
        'bo__auxiliar1',
        'bo__auxiliar2',
        'bo__cecom'
    ).filter(bo__emissao__date__range=(de, ate))
    
    # Filtro por GCM (considera TODOS os campos do BO)
    if uid:
        base = base.filter(
            Q(bo__encarregado_id=uid) | 
            Q(bo__motorista_id=uid) | 
            Q(bo__auxiliar1_id=uid) | 
            Q(bo__auxiliar2_id=uid) | 
            Q(bo__cecom_id=uid)
        )
    
    removidos = base.filter(
        Q(apreensao_ait__gt='') | Q(apreensao_crr__gt='') | Q(apreensao_destino__gt='') | Q(apreensao_responsavel_guincho__gt='')
    )
    total = removidos.count()
    # Série por dia
    serie = list(
        removidos.annotate(dia=TruncDate('bo__emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie
    ]
    # Top 10 dias
    top_dias = list(
        removidos.annotate(dia=TruncDate('bo__emissao')).values('dia').annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )
    # Ranking usuários (considera TODOS os integrantes do BO)
    contador_usuarios = Counter()
    for veiculo in removidos:
        bo = veiculo.bo
        if not bo:
            continue
        # Coletar todos os integrantes do BO
        integrantes_ids = set()
        if bo.encarregado_id:
            integrantes_ids.add(bo.encarregado_id)
        if bo.motorista_id:
            integrantes_ids.add(bo.motorista_id)
        if bo.auxiliar1_id:
            integrantes_ids.add(bo.auxiliar1_id)
        if bo.auxiliar2_id:
            integrantes_ids.add(bo.auxiliar2_id)
        if bo.cecom_id:
            integrantes_ids.add(bo.cecom_id)
        
        # Incrementar contador para cada integrante
        for user_id in integrantes_ids:
            contador_usuarios[user_id] += 1
    
    # Montar top 10 com dados dos usuários
    top_usuarios = []
    for user_id, qtd in contador_usuarios.most_common(10):
        try:
            user = User.objects.get(pk=user_id)
            top_usuarios.append({
                'bo__encarregado__first_name': user.first_name,
                'bo__encarregado__last_name': user.last_name,
                'bo__encarregado__username': user.username,
                'qtd': qtd
            })
        except User.DoesNotExist:
            pass
    por_destino = list(
        removidos.values('apreensao_destino').annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )
    por_guincho = list(
        removidos.values('apreensao_responsavel_guincho').annotate(qtd=Count('id')).order_by('-qtd')[:10]
    )
    com_ait = removidos.filter(apreensao_ait__gt='').count()

    # Options usuários
    user_options = []
    if Perfil:
        profs = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula','user__first_name','user__last_name')
        )
        for p in profs:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})

    # Export PDF (apresentação)
    if (request.GET.get('export') or '').lower() == 'pdf':
        html = render_to_string('core/adm_estatisticas_remocoes_pdf.html', {
            'de': de, 'ate': ate,
            'uid': uid,
            'total': total,
            'com_ait': com_ait,
            'top_dias': top_dias,
            'top_usuarios': top_usuarios,
            'por_destino': por_destino,
            'por_guincho': por_guincho,
        })
        try:
            import tempfile, os, subprocess
            from django.conf import settings
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as fhtml:
                fhtml.write(html.encode('utf-8'))
                html_path = fhtml.name
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml:
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as fpdf:
                pdf_path = fpdf.name
            subprocess.check_call([wkhtml, '--quiet', html_path, pdf_path])
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path); os.unlink(pdf_path)
            except Exception:
                pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=remocoes_{de:%Y%m%d}_{ate:%Y%m%d}{('_user_'+str(uid)) if uid else ''}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    ctx = {
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_options': user_options,
        'total': total,
        'por_destino': por_destino,
        'por_guincho': por_guincho,
        'com_ait': com_ait,
        'top_dias': top_dias,
        'top_usuarios': top_usuarios,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
    }
    # CSV export (detalhes)
    if (request.GET.get('export') or '').lower() == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        fn = f"remocoes_{de:%Y%m%d}_{ate:%Y%m%d}{('_user_'+str(uid)) if uid else ''}.csv"
        resp['Content-Disposition'] = f"attachment; filename={fn}"
        w = csv.writer(resp)
        w.writerow(['BO','Emissão','AIT','CRR','Destino','Resp. Guincho','Encarregado'])
        for v in removidos.select_related('bo','bo__encarregado').order_by('bo__emissao'):
            bo = getattr(v,'bo',None)
            emissao = timezone.localtime(getattr(bo,'emissao', None)).strftime('%Y-%m-%d %H:%M:%S') if bo and getattr(bo,'emissao',None) else ''
            enc = getattr(bo,'encarregado',None)
            enc_nome = (enc.get_full_name() or enc.username).strip() if enc else ''
            w.writerow([getattr(bo,'numero',''), emissao, v.apreensao_ait, v.apreensao_crr, v.apreensao_destino, v.apreensao_responsavel_guincho, enc_nome])
        return resp
    return render(request, 'core/adm_estatisticas_remocoes.html', ctx)


@login_required
def estatisticas_remocoes_graficos(request):
    """Gráficos de Veículos Removidos por período, com filtro por encarregado."""
    from bogcmi.models import VeiculoEnvolvido
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0

    # Options de usuário
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    user_options = []
    user_nome = ''
    if Perfil:
        for p in Perfil.objects.select_related('user').filter(ativo=True, user__is_active=True).order_by('matricula','user__first_name','user__last_name'):
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
            if p.user_id == uid:
                user_nome = nome

    base = VeiculoEnvolvido.objects.select_related('bo','bo__encarregado').filter(bo__emissao__date__range=(de, ate))
    removidos = base.filter(Q(apreensao_ait__gt='') | Q(apreensao_crr__gt='') | Q(apreensao_destino__gt='') | Q(apreensao_responsavel_guincho__gt=''))
    if uid:
        from django.db.models import Q
        removidos = removidos.filter(
            Q(bo__encarregado_id=uid) | 
            Q(bo__motorista_id=uid) | 
            Q(bo__auxiliar1_id=uid) | 
            Q(bo__auxiliar2_id=uid) | 
            Q(bo__cecom_id=uid)
        )
    total = removidos.count()
    serie = list(removidos.annotate(dia=TruncDate('bo__emissao')).values('dia').annotate(qtd=Count('id')).order_by('dia'))
    serie_js = [ {'dia': (r.get('dia').strftime('%Y-%m-%d') if r.get('dia') else ''), 'qtd': int(r.get('qtd') or 0)} for r in serie ]
    abas = [('dia','Dia'),('mes','Mês'),('semestre','Semestre'),('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'user_options': user_options,
        'total': total,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'abas': abas,
    }
    return render(request, 'core/adm_estatisticas_remocoes_graficos.html', ctx)

@login_required
def dispensas(request):
    """Página de gestão de Dispensas.

    - Filtro por plantão (A/B/C/D)
    - Calendário do mês selecionado
    - Seções: Minhas solicitações, Pendentes (aprovação), Aprovadas, Recusadas
    """
    # Filtros básicos
    plantao = (request.GET.get('plantao') or 'A').upper()
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get('ano') or hoje.year)
        mes = int(request.GET.get('mes') or hoje.month)
    except ValueError:
        ano, mes = hoje.year, hoje.month

    # Intervalo do mês
    _, last_day = calendar.monthrange(ano, mes)
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, last_day)

    # Calendário em semanas (lista de listas, sempre 7 dias por semana)
    cal = calendar.Calendar(firstweekday=0)  # 0 = segunda-feira
    weeks = cal.monthdatescalendar(ano, mes)

    # URLs prev/next mês
    prev_ano, prev_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    next_ano, next_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    prev_url = f"?plantao={plantao}&ano={prev_ano}&mes={prev_mes}"
    next_url = f"?plantao={plantao}&ano={next_ano}&mes={next_mes}"

    # Consultas
    minhas = (
        Dispensa.objects.select_related('supervisor', 'solicitante')
        .filter(solicitante=request.user, data__range=(inicio, fim))
        .order_by('data')
    )
    pendentes = (
        Dispensa.objects.select_related('solicitante')
        .filter(supervisor=request.user, status='PENDENTE', data__range=(inicio, fim))
        .order_by('data')
    )
    aprovadas = (
        Dispensa.objects.select_related('supervisor')
        .filter(solicitante=request.user, status='APROVADA', data__range=(inicio, fim))
        .order_by('data')
    )
    recusadas = (
        Dispensa.objects.select_related('supervisor')
        .filter(solicitante=request.user, status='RECUSADA', data__range=(inicio, fim))
        .order_by('data')
    )

    # Calendário por plantão: dispensas do mês filtradas pelo plantão selecionado
    cal_regs = (
        Dispensa.objects.select_related('solicitante')
        .filter(data__range=(inicio, fim), plantao=plantao)
        .order_by('data', 'solicitante__first_name', 'solicitante__username')
    )
    cal_por_dia: dict[int, list[dict]] = {}
    for r in cal_regs:
        dia = r.data.day
        nome = r.solicitante.get_full_name() or r.solicitante.get_username()
        cal_por_dia.setdefault(dia, []).append({
            'nome': nome,
            'status': r.status,
        })

    # Aprovadas sob minha supervisão (para permitir cancelamento)
    allowed_admin = request.user.username.lower() in {"moises", "comandante", "subcomandante"} or request.user.is_superuser
    aprovadas_supervisao_qs = (
        Dispensa.objects.select_related('solicitante', 'supervisor')
        .filter(status='APROVADA', data__range=(inicio, fim))
        .order_by('data')
    )
    if not allowed_admin:
        aprovadas_supervisao_qs = aprovadas_supervisao_qs.filter(supervisor=request.user)

    return render(request, 'core/adm_dispensas.html', {
        'plantao': plantao,
        'ano': ano,
        'mes': mes,
        'weeks': weeks,
        'inicio': inicio,
        'fim': fim,
        'minhas': minhas,
        'pendentes': pendentes,
        'aprovadas': aprovadas,
        'recusadas': recusadas,
        'aprovadas_supervisao': aprovadas_supervisao_qs,
        'cal_por_dia': cal_por_dia,
        'prev_url': prev_url,
        'next_url': next_url,
    })

@login_required
def dispensas_solicitar(request):
    """Cria uma solicitação de dispensa para um dia específico."""
    initial = {}
    # Pré-preencher data/plantão
    data_str = request.GET.get('data')
    if data_str:
        try:
            y,m,d = map(int, data_str.split('-'))
            initial['data'] = date(y,m,d)
        except Exception:
            pass
    initial['plantao'] = (request.GET.get('plantao') or 'A').upper()

    if request.method == 'POST':
        form = DispensaSolicitacaoForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.solicitante = request.user
            # status padrão PENDENTE
            try:
                obj.save()
                # notificar supervisor (badge + push opcional)
                try:
                    from .models import UserNotification
                    titulo = 'Dispensa pendente de aprovação'
                    msg = (
                        f"Solicitante: {(request.user.get_full_name() or request.user.get_username())}\n"
                        f"Data: {obj.data:%d/%m/%Y} · Plantão {obj.plantao} · {obj.get_turno_display()}\n"
                        f"Tipo: {obj.get_tipo_display()}"
                    )
                    if obj.observacao:
                        msg += f"\nObs: {obj.observacao[:200]}"
                    # Token de referência para remoção automática ao decidir
                    msg += f"\nRef: DISPENSA #{obj.id}"
                    UserNotification.objects.create(
                        user=obj.supervisor,
                        title=titulo,
                        message=msg,
                        link_url=request.build_absolute_uri(reverse('core:dispensas')),
                    )
                except Exception:
                    pass
                # push opcional, se dispositivo existir
                try:
                    from common.models import PushDevice
                    from common.views import enviar_push
                    tokens = list(PushDevice.objects.filter(user=obj.supervisor, enabled=True).values_list('token', flat=True))
                    if tokens:
                        enviar_push(tokens, title='Dispensa', body='Nova solicitação pendente para sua aprovação.', data={'kind':'dispensa','dispensa_id':obj.id})
                except Exception:
                    pass
                # redireciona para o mês correspondente
                return redirect('core:dispensas')
            except Exception as e:
                # Provável violação de unicidade (mesmo dia e turno não cancelados)
                form.add_error('data', 'Já existe uma solicitação sua para este dia e turno.')
    else:
        form = DispensaSolicitacaoForm(initial=initial)
    return render(request, 'core/dispensas_form.html', {
        'form': form,
    })

def _calcular_minutos_dispensa(obj: Dispensa) -> int:
    """Calcula, de forma simplificada, a duração da dispensa em minutos.

    Assumimos, por padrão, 12 horas para DIURNO e 12 horas para NOTURNO,
    conforme prática comum nos plantões. Ajuste futuramente se necessário.
    """
    try:
        turno = (obj.turno or 'DIURNO').upper()
    except Exception:
        turno = 'DIURNO'
    dur_map = {
        'DIURNO': 12 * 60,
        'NOTURNO': 12 * 60,
    }
    return int(dur_map.get(turno, 12 * 60))

@login_required
def dispensas_aprovar(request, dispensa_id: int):
    obj = get_object_or_404(Dispensa.objects.select_related('solicitante', 'supervisor'), pk=dispensa_id)
    allowed_users = {"moises", "administrativo", "comandante", "subcomandante"}
    if not (request.user == obj.supervisor or request.user.username.lower() in allowed_users or request.user.is_superuser):
        return HttpResponseForbidden('Sem permissão para aprovar/recusar esta solicitação.')

    if request.method == 'POST':
        form = DispensaAprovacaoForm(request.POST)
        if form.is_valid():
            acao = form.cleaned_data['acao']
            if acao == 'aprovar':
                obj.status = 'APROVADA'
                obj.aprovado_em = timezone.now()
                obj.mensagem_recusa = ''
                # Integra Banco de Horas: ao aprovar dispensa do tipo BANCO, lançar débito
                try:
                    if obj.tipo == 'BANCO':
                        # evitar duplicidade por reprocessamento
                        ref_id = str(obj.id)
                        ja_lancado = BancoHorasLancamento.objects.filter(user=obj.solicitante, ref_type='DISPENSA', ref_id=ref_id).exists()
                        if not ja_lancado:
                            # cálculo de minutos por turno (assumido 12h para DIURNO/NOTURNO)
                            minutos = _calcular_minutos_dispensa(obj)
                            if minutos > 0:
                                BancoHorasLancamento.ajustar_saldo(
                                    obj.solicitante,
                                    -minutos,
                                    origem='DISPENSA',
                                    motivo=f'Dispensa BANCO {obj.data:%d/%m/%Y} · {obj.get_turno_display()}',
                                    ref_type='DISPENSA',
                                    ref_id=ref_id,
                                    created_by=request.user,
                                )
                except Exception:
                    # Não bloquear o fluxo de aprovação por falha no banco de horas
                    pass
            else:
                obj.status = 'RECUSADA'
                obj.recusado_em = timezone.now()
                obj.mensagem_recusa = form.cleaned_data.get('mensagem') or ''
            obj.save(update_fields=['status','aprovado_em','recusado_em','mensagem_recusa','updated_at'])
            # Remover notificação pendente do supervisor referente a esta dispensa
            try:
                from .models import UserNotification
                (UserNotification.objects
                    .filter(user=obj.supervisor, title='Dispensa pendente de aprovação', message__icontains=f'DISPENSA #{obj.id}')
                    .delete())
            except Exception:
                pass
            # voltar para índice do mês correspondente
            return redirect('core:dispensas')
    else:
        form = DispensaAprovacaoForm()

    return render(request, 'core/dispensas_aprovar.html', {
        'obj': obj,
        'form': form,
    })

@login_required
def dispensas_cancelar(request, dispensa_id: int):
    """Cancela uma dispensa já aprovada.

    Permissões:
    - Supervisor que aprovou a solicitação (obj.supervisor)
    - Perfis especiais: moises, comandante, subcomandante, ou superuser
    """
    obj = get_object_or_404(Dispensa.objects.select_related('solicitante', 'supervisor'), pk=dispensa_id)
    if request.method != 'POST':
        return HttpResponseBadRequest('Método inválido')

    allowed_admin = request.user.username.lower() in {"moises", "comandante", "subcomandante"} or request.user.is_superuser
    if not (allowed_admin or request.user == obj.supervisor):
        return HttpResponseForbidden('Sem permissão para cancelar esta solicitação.')

    if obj.status != 'APROVADA':
        messages.error(request, 'Somente solicitações aprovadas podem ser canceladas.')
        return redirect('core:dispensas')

    obj.status = 'CANCELADA'
    obj.cancelado_em = timezone.now()
    obj.cancelado_por = request.user
    obj.save(update_fields=['status', 'cancelado_em', 'cancelado_por', 'updated_at'])
    # Reversão no Banco de Horas para tipo BANCO
    try:
        if obj.tipo == 'BANCO':
            ref_id = str(obj.id)
            # Evitar reversão duplicada
            ja_revertido = BancoHorasLancamento.objects.filter(user=obj.solicitante, ref_type='DISPENSA_CANCEL', ref_id=ref_id).exists()
            if not ja_revertido:
                # Buscar lançamento original p/ obter minutos
                lanc_orig = (
                    BancoHorasLancamento.objects
                    .filter(user=obj.solicitante, ref_type='DISPENSA', ref_id=ref_id)
                    .order_by('created_at')
                    .first()
                )
                minutos = abs(getattr(lanc_orig, 'minutos', 0)) or _calcular_minutos_dispensa(obj)
                if minutos > 0:
                    BancoHorasLancamento.ajustar_saldo(
                        obj.solicitante,
                        minutos,
                        origem='DISPENSA',
                        motivo=f'Reversão dispensa BANCO {obj.data:%d/%m/%Y} · {obj.get_turno_display()} (cancelada)',
                        ref_type='DISPENSA_CANCEL',
                        ref_id=ref_id,
                        created_by=request.user,
                    )
    except Exception:
        pass
    messages.success(request, 'Dispensa cancelada com sucesso.')
    return redirect('core:dispensas')

@login_required
def dispensas_excluir(request, dispensa_id: int):
    """Exclui definitivamente uma solicitação de dispensa.

    Permissão: apenas usuário 'moises' (ou superuser).
    """
    obj = get_object_or_404(Dispensa, pk=dispensa_id)
    if request.method != 'POST':
        return render(request, 'core/confirm_delete.html', {
            'titulo': f'Excluir Dispensa #{obj.id}',
            'mensagem': 'Tem certeza que deseja excluir esta solicitação? Esta ação não pode ser desfeita.',
            'action_url': request.path,
        })

    if not (request.user.is_superuser or request.user.username.lower() == 'moises'):
        return HttpResponseForbidden('Sem permissão para excluir esta solicitação.')

    # Remover possíveis notificações persistentes relacionadas a esta dispensa
    try:
        from .models import UserNotification
        (UserNotification.objects
            .filter(message__icontains=f'DISPENSA #{obj.id}')
            .delete())
    except Exception:
        pass

    obj.delete()
    messages.success(request, 'Solicitação excluída.')
    return redirect('core:dispensas')

@login_required
def notificacoes_usuario(request):
    """
    View para listar notificações do usuário.
    Agora considera:
    - Talões ativos onde o usuário participa (encarregado, motorista, aux1, aux2)
    - Plantões CECOM ativos onde o usuário participa e que tenham viatura vinculada
    """
    from cecom.models import DespachoOcorrencia, PlantaoCECOM
    from taloes.models import Talao
    from django.db.models import Q

    # Talões ativos onde o usuário participa em qualquer função
    taloes_ativos = (
        Talao.objects
        .select_related('viatura')
        .filter(
            status='ABERTO',
        )
        .filter(
            Q(encarregado=request.user) |
            Q(motorista=request.user) |
            Q(auxiliar1=request.user) |
            Q(auxiliar2=request.user)
        )
    )

    # Plantões ativos (CECOM) onde o usuário participa, com viatura vinculada
    plantoes_user = (
        PlantaoCECOM.objects
        .select_related('viatura')
        .filter(ativo=True)
        .filter(
            Q(iniciado_por=request.user) |
            Q(participantes__usuario=request.user, participantes__saida_em__isnull=True)
        )
        .distinct()
    )

    # Conjunto de viaturas que o usuário tem vínculo (por talão ou plantão)
    viaturas_ids = set()
    for t in taloes_ativos:
        if t.viatura_id:
            viaturas_ids.add(t.viatura_id)
    for p in plantoes_user:
        if p.viatura_id:
            viaturas_ids.add(p.viatura_id)

    notificacoes = []
    user_notifs = []

    # Ofícios Internos pendentes para este usuário (Supervisor/SubCMT/CMT)
    oficios_pendentes = []
    try:
        from django.db.models import Q
        cond = Q(status='PEND_SUP', supervisor=request.user)
        uname = (request.user.username or '').lower()
        if uname == 'subcomandante':
            cond |= Q(status='PEND_SUB')
        if uname == 'comandante':
            cond |= Q(status='PEND_CMT')
        oficios_pendentes = list(
            OficioInterno.objects
            .select_related('criador','supervisor')
            .filter(cond)
            .order_by('-created_at')[:20]
        )
    except Exception:
        oficios_pendentes = []

    if viaturas_ids:
        # Buscar despachos pendentes para as viaturas do usuário
        despachos_pendentes = (
            DespachoOcorrencia.objects
            .select_related('viatura')
            .filter(
                viatura_id__in=viaturas_ids,
                status='PENDENTE',
                respondido_em__isnull=True
            )
            .order_by('-despachado_em')
        )

        for despacho in despachos_pendentes:
            # Marcar como notificado quando o usuário visualiza
            despacho.marcar_como_notificado()

            notificacoes.append({
                'id': despacho.pk,
                'tipo': 'despacho',
                'titulo': f'Nova Ocorrência - Viatura {getattr(despacho.viatura, "prefixo", "").upper() or despacho.viatura_id}',
                'endereco': despacho.endereco,
                'descricao': despacho.descricao,
                'despachado_em': despacho.despachado_em,
                'solicitante': despacho.nome_solicitante or 'Não informado',
                'telefone': despacho.telefone_solicitante or '',
                'urgente': True,
                'talao_id': None,
                'cod_natureza': getattr(despacho, 'cod_natureza', ''),
                'natureza': getattr(despacho, 'natureza', ''),
            })

    # BOs em edição onde o usuário é integrante (encarregado, motorista, aux1, aux2 ou cecom)
    integrante_q = (
        Q(encarregado=request.user) |
        Q(motorista=request.user) |
        Q(auxiliar1=request.user) |
        Q(auxiliar2=request.user) |
        Q(cecom=request.user)
    )
    bos_ativos_user = (
        BO.objects.select_related('viatura')
        .filter(integrante_q, status='EDICAO')
        .order_by('-emissao')
    )

    # Documentos pendentes de assinatura (CMT/SUBCMT veem PLANTAO/BOGCMI; Administrativo vê LIVRO CECOM)
    docs_pendentes = []
    try:
        from common.models import DocumentoAssinavel
        uname = (request.user.username or '').lower()
        ronda_count = bogcm_count = livro_count = 0
        if uname in {'comandante', 'subcomandante'}:
            # Contagens por tipo
            ronda_count = DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='PLANTAO').count()
            bogcm_count = DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='BOGCMI').count()
            docs_pendentes = list(
                DocumentoAssinavel.objects
                .filter(status='PENDENTE', tipo__in=['PLANTAO','BOGCMI'])
                .order_by('-created_at')[:20]
            )
        elif uname in {'administrativo', 'admnistrativo'}:
            livro_count = DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM').count()
            docs_pendentes = list(
                DocumentoAssinavel.objects
                .filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM')
                .order_by('-created_at')[:20]
            )
    except Exception:
        docs_pendentes = []
        ronda_count = bogcm_count = livro_count = 0

    # Notificações persistentes do usuário (não lidas)
    try:
        from .models import UserNotification
        user_notifs = list(UserNotification.objects.filter(user=request.user, read_at__isnull=True).order_by('-created_at')[:50])
    except Exception:
        user_notifs = []

    total_pendentes = (
        len(notificacoes)
        + (len(oficios_pendentes) if oficios_pendentes else 0)
        + (len(docs_pendentes) if docs_pendentes else 0)
        + (len(user_notifs) if user_notifs else 0)
    )
    resumo_tipos = {
        'despachos': len(notificacoes),
        'oficios': len(oficios_pendentes or []),
        'avisos': len(user_notifs or []),
        'assinaturas': {
            'ronda': ronda_count,
            'bogcmi': bogcm_count,
            'livro': livro_count,
        }
    }

    return render(request, 'core/notificacoes.html', {
        'notificacoes': notificacoes,
        'user_notifs': user_notifs,
        'taloes_ativos': taloes_ativos,
        'bos_ativos': bos_ativos_user,
        'oficios_pendentes': oficios_pendentes,
        'docs_pendentes': docs_pendentes,
        'total_pendentes': total_pendentes,
        'resumo_tipos': resumo_tipos,
    })


@login_required
def push_teste_usuario(request):
    """Envia uma notificação de teste via FCM para os dispositivos do usuário logado.

    Não requer perfil de comando; restringe o envio aos próprios dispositivos do usuário.
    Aceita POST opcional com JSON: {"title": str, "body": str}
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido'}, status=405)
    try:
        from common.models import PushDevice
        from common.views import enviar_push
        payload = {}
        if request.body:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
            except Exception:
                payload = {}
        title = (payload.get('title') or 'GCM - Teste').strip()
        body = (payload.get('body') or 'Notificação de teste do aplicativo.').strip()
        tokens = list(PushDevice.objects.filter(user=request.user, enabled=True).values_list('token', flat=True))
        if not tokens:
            return JsonResponse({'ok': False, 'error': 'Nenhum dispositivo registrado para seu usuário.'}, status=404)
        res = enviar_push(tokens, title=title, body=body, data={'kind': 'test'}, return_details=True)
        # res é dict quando return_details=True
        if isinstance(res, dict):
            return JsonResponse({'ok': True, 'sent': res.get('success', 0), 'failures': res.get('failures', 0), 'disabled': res.get('disabled', 0), 'errors': res.get('errors', [])})
        return JsonResponse({'ok': True, 'sent': int(res)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def confirmar_notificacao_usuario(request, pk: int):
    """Confirma leitura de uma notificação do usuário e a remove da lista.

    Aceita POST; retorna JSON para uso via fetch.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido'}, status=405)
    try:
        from .models import UserNotification
        obj = get_object_or_404(UserNotification, pk=pk, user=request.user)
        # Remoção direta para atender requisito (apaga a notificação)
        obj.delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def responder_despacho(request, despacho_id):
    """
    View para aceitar ou recusar um despacho.
    Permissões:
    - Encarregado do Talão ativo da viatura
    - ENC do Plantão CECOM ativo vinculado à viatura
    """
    if request.method == 'POST':
        from cecom.models import DespachoOcorrencia, PlantaoCECOM
        
        despacho = get_object_or_404(DespachoOcorrencia, pk=despacho_id)
        permitido = False
        talao_ativo = None
        try:
            from taloes.models import Talao
            talao_ativo = Talao.objects.get(
                encarregado=request.user,
                viatura=despacho.viatura,
                status='ABERTO'
            )
            permitido = True
        except Talao.DoesNotExist:
            permitido = False

        if not permitido:
            # Permitir ENC do Plantão CECOM ativo vinculado à mesma viatura
            from django.db.models import Q
            enc_plantao_existe = (
                PlantaoCECOM.objects
                .filter(
                    ativo=True,
                    viatura=despacho.viatura,
                )
                .filter(
                    Q(participantes__usuario=request.user, participantes__saida_em__isnull=True, participantes__funcao='ENC') |
                    Q(iniciado_por=request.user)
                )
                .exists()
            )
            if enc_plantao_existe:
                permitido = True

        if not permitido:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Sem permissão para responder: apenas o encarregado do talão ativo ou o ENC do plantão podem responder por esta viatura.'
            })
        
        try:
            data = json.loads(request.body)
            acao = data.get('acao')  # 'aceitar' ou 'recusar'
            observacoes = data.get('observacoes', '')
            
            if acao == 'aceitar':
                despacho.aceitar(request.user, observacoes)
                return JsonResponse({
                    'sucesso': True,
                    'mensagem': 'Despacho aceito com sucesso!',
                    'novo_status': despacho.get_status_display()
                })
            elif acao == 'recusar':
                despacho.recusar(request.user, observacoes)
                return JsonResponse({
                    'sucesso': True,
                    'mensagem': 'Despacho recusado.',
                    'novo_status': despacho.get_status_display()
                })
            else:
                return JsonResponse({
                    'sucesso': False,
                    'erro': 'Ação inválida.'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Dados inválidos.'
            })
    
    return JsonResponse({
        'sucesso': False,
        'erro': 'Método não permitido.'
    })

# --- Fiscalização ---
@login_required
def fiscalizacao_notificacao(request):
    # Lista paginada com busca por nome
    qs = NotificacaoFiscalizacao.objects.select_related('fiscal_responsavel')
    q = (request.GET.get('q') or '').strip()
    endereco_q = (request.GET.get('endereco') or '').strip()
    if q:
        qs = qs.filter(notificado_nome__icontains=q)
    if endereco_q:
        qs = qs.filter(endereco__icontains=endereco_q)
    qs = qs.order_by('-emissao_em')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/fisc_notificacao.html', {
        'page_obj': page_obj,
        'q': q,
        'endereco': endereco_q,
    })


@login_required
def fiscalizacao_auto_comercio(request):
    qs = AutoInfracaoComercio.objects.select_related('fiscal_responsavel')
    q = (request.GET.get('q') or '').strip()
    endereco_q = (request.GET.get('endereco') or '').strip()
    if q:
        qs = qs.filter(notificado_nome__icontains=q)
    if endereco_q:
        qs = qs.filter(endereco__icontains=endereco_q)
    qs = qs.order_by('-emissao_em')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/fisc_auto_comercio.html', {
        'page_obj': page_obj,
        'q': q,
        'endereco': endereco_q,
    })


@login_required
def fiscalizacao_auto_som(request):
    qs = AutoInfracaoSom.objects.select_related('fiscal_responsavel')
    q = (request.GET.get('q') or '').strip()
    endereco_q = (request.GET.get('endereco') or '').strip()
    if q:
        qs = qs.filter(notificado_nome__icontains=q)
    if endereco_q:
        qs = qs.filter(endereco__icontains=endereco_q)
    qs = qs.order_by('-emissao_em')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/fisc_auto_som.html', {
        'page_obj': page_obj,
        'q': q,
        'endereco': endereco_q,
    })


@login_required
def fiscalizacao_alterar_status(request, tipo: str, pk: int):
    """Altera o status de Notificação/Auto. Permitido somente aos usuários
    'moises' e 'administrativo' (aceita também 'admnistrativo') ou superuser.

    tipo: 'not' | 'com' | 'som'
    payload: POST form/json com campo 'status' (AGUARDANDO|DESPACHADO)
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método não permitido'}, status=405)
    allowed = {"moises", "administrativo", "admnistrativo"}
    if not (request.user.is_superuser or request.user.username.lower() in allowed):
        return JsonResponse({'ok': False, 'error': 'Sem permissão'}, status=403)
    # obter novo status
    status_val = (request.POST.get('status') or request.body.decode('utf-8') or '').strip()
    # se veio JSON
    if status_val and status_val.startswith('{'):
        try:
            data = json.loads(status_val)
            status_val = (data.get('status') or '').strip()
        except Exception:
            status_val = ''
    if not status_val:
        status_val = (request.POST.get('status') or '').strip()
    status_val = status_val.upper()
    if status_val not in {"AGUARDANDO", "DESPACHADO"}:
        return JsonResponse({'ok': False, 'error': 'Status inválido'}, status=400)
    # carregar objeto
    Model = None
    if tipo == 'not':
        Model = NotificacaoFiscalizacao
    elif tipo == 'com':
        Model = AutoInfracaoComercio
    elif tipo == 'som':
        Model = AutoInfracaoSom
    else:
        return JsonResponse({'ok': False, 'error': 'Tipo inválido'}, status=400)
    obj = get_object_or_404(Model, pk=pk)
    if getattr(obj, 'status', None) == status_val:
        return JsonResponse({'ok': True, 'status': status_val, 'changed': False})
    obj.status = status_val
    try:
        obj.save(update_fields=['status', 'updated_at'])
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True, 'status': status_val, 'changed': True})


@login_required
def fiscalizacao_notificacao_novo(request):
    if request.method == 'POST':
        form = NotificacaoFiscalizacaoForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_notificacao(request, obj, via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_notificacao')
    else:
        initial = {
            'fiscal_matricula': getattr(getattr(request.user, 'perfil', None), 'matricula', '')
        }
        form = NotificacaoFiscalizacaoForm(initial=initial)
    return render(request, 'core/fisc_notificacao_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def fiscalizacao_notificacao_editar(request, pk: int):
    obj = get_object_or_404(NotificacaoFiscalizacao, pk=pk)
    if request.method == 'POST':
        form = NotificacaoFiscalizacaoForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_notificacao(request, obj, via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_notificacao')
    else:
        form = NotificacaoFiscalizacaoForm(instance=obj)
    return render(request, 'core/fisc_notificacao_form.html', {
        'form': form,
        'is_edit': True,
        'obj': obj,
    })


@login_required
def fiscalizacao_notificacao_excluir(request, pk: int):
    obj = get_object_or_404(NotificacaoFiscalizacao, pk=pk)
    # Permissão: somente superadmin 'moises' (ou superuser)
    if not (request.user.is_superuser or request.user.username.lower() == 'moises'):
        return HttpResponseForbidden('Sem permissão para excluir este registro.')
    if request.method == 'POST':
        obj.delete()
        return redirect('core:fisc_notificacao')
    return render(request, 'core/confirm_delete.html', {
        'titulo': f'Excluir Notificação {obj.numero}',
        'mensagem': 'Tem certeza que deseja excluir este registro? Esta ação não pode ser desfeita.',
        'action_url': request.path,
    })

# ---- Documento Notificação (visualizar/baixar PDF) ----
def _find_wkhtmltopdf_path_core():
    path_cfg = getattr(settings, 'WKHTMLTOPDF_CMD', '') or ''
    if path_cfg and os.path.exists(path_cfg):
        return path_cfg
    candidates = [
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    try:
        import shutil
        found = shutil.which('wkhtmltopdf')
        if found:
            return found
    except Exception:
        pass
    return None

def _pdf_from_html_core(html: str, request) -> bytes:
    base_url = request.build_absolute_uri('/')
    body = html
    if '<html' not in body.lower():
        body = "<!doctype html><html lang='pt-br'><head><meta charset='utf-8'></head><body>" + body + "</body></html>"
    # Tentar resolver /static/ locais para wkhtmltopdf
    try:
        static_root = getattr(settings, 'STATIC_ROOT', '')
        static_dirs = list(getattr(settings, 'STATICFILES_DIRS', []))
        def _resolve_static(rel_path: str) -> str | None:
            # 1) STATIC_ROOT (coletado via collectstatic)
            if static_root and os.path.isdir(static_root):
                local = os.path.join(static_root, rel_path.replace('/', os.sep))
                if os.path.exists(local):
                    return local
            # 2) STATICFILES_DIRS (desenvolvimento)
            for d in static_dirs:
                local = os.path.join(str(d), rel_path.replace('/', os.sep))
                if os.path.exists(local):
                    return local
            return None
        def _repl(m):
            rel = m.group(1)
            local = _resolve_static(rel)
            if local:
                return f"src='file:///{local.replace(os.sep,'/')}'"
            return m.group(0)
        body = re.sub(r"src=['\"]/static/(.+?)['\"]", _repl, body)
        # Resolver /media/ para caminhos locais (assinaturas, anexos)
        media_root = getattr(settings, 'MEDIA_ROOT', '')
        if media_root and os.path.isdir(media_root):
            def _repl_media(m):
                rel = m.group(1)
                local = os.path.join(media_root, rel.replace('/', os.sep))
                if os.path.exists(local):
                    return f"src='file:///{local.replace(os.sep,'/')}'"
                return m.group(0)
            body = re.sub(r"src=['\"]/media/(.+?)['\"]", _repl_media, body)
    except Exception:
        pass
    if '<head' in body.lower() and '<base ' not in body.lower():
        body = re.sub(r'<head(.*?)>', lambda m: f"<head{m.group(1)}><base href='{base_url}'>", body, count=1, flags=re.I)

    wk = _find_wkhtmltopdf_path_core()
    if wk:
        try:
            with tempfile.TemporaryDirectory() as td:
                html_f = os.path.join(td, 'doc.html'); pdf_f = os.path.join(td, 'out.pdf')
                with open(html_f,'w',encoding='utf-8') as f: f.write(body)
                cmd = [wk,'--enable-local-file-access','--encoding','utf-8','--page-size','A4','--margin-top','14mm','--margin-bottom','16mm','--margin-left','12mm','--margin-right','12mm','--print-media-type','--disable-smart-shrinking','--zoom','1.0','--dpi','96',html_f,pdf_f]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                if proc.returncode == 0 and os.path.exists(pdf_f):
                    return open(pdf_f,'rb').read()
        except Exception:
            pass
    # Fallback simples (xhtml2pdf)
    try:
        from xhtml2pdf import pisa  # type: ignore
        from io import BytesIO
        out = BytesIO()
        status = pisa.CreatePDF(body, dest=out, encoding='utf-8')
        if not status.err:
            return out.getvalue()
    except Exception:
        pass
    return body.encode('utf-8', errors='ignore')

@login_required
def fisc_notificacao_documento(request, pk: int):
    n = get_object_or_404(NotificacaoFiscalizacao, pk=pk)
    # Gera QR (token + hash) se possível
    qr_b64 = _gerar_qr_code_para_notificacao(request, n)
    return render(request, 'core/visualizar_documento_notificacao.html', {'n': n, 'qr_code_base64': qr_b64})

@login_required
def fisc_notificacao_baixar_pdf(request, pk: int):
    n = get_object_or_404(NotificacaoFiscalizacao, pk=pk)
    qr_b64 = _gerar_qr_code_para_notificacao(request, n)
    html = render_to_string('core/documento_notificacao.html', {'n': n, 'request': request, 'qr_code_base64': qr_b64})
    pdf = _pdf_from_html_core(html, request)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f"attachment; filename=Notificacao_{n.numero or n.pk}.pdf"
    resp['Cache-Control'] = 'no-store'
    return resp

def _gerar_qr_code_para_notificacao(request, n: NotificacaoFiscalizacao):
    try:
        import qrcode
        import secrets, hashlib, base64
        mudou = False
        if not n.validacao_token:
            n.validacao_token = secrets.token_hex(16)
            mudou = True
        # hash baseado em número/id/fiscal/timestamp
        ts = int(n.emissao_em.timestamp()) if n.emissao_em else 0
        resumo = f"NOT:{n.numero}|ID:{n.id}|FISC:{n.fiscal_responsavel_id}|TS:{ts}"
        calc = hashlib.sha256(resumo.encode()).hexdigest()
        if n.validacao_hash != calc:
            n.validacao_hash = calc
            mudou = True
        if mudou:
            try:
                n.save(update_fields=['validacao_token','validacao_hash'])
            except Exception:
                pass
        url = request.build_absolute_uri(reverse('core:fisc_notificacao_validar', args=[n.pk, n.validacao_token]))
        img = qrcode.make(url)
        from io import BytesIO
        buf = BytesIO(); img.save(buf, format='PNG'); b = buf.getvalue(); buf.close()
        return 'data:image/png;base64,' + base64.b64encode(b).decode()
    except Exception:
        return None

def _enviar_segunda_via_notificacao(request, n: NotificacaoFiscalizacao, *, via_do_notificado: bool = False, destinatario_override: str | None = None):
    """Gera o PDF da notificação e envia por e-mail para o notificado.
    Retorna (ok, erro).

    Parâmetros:
    - via_do_notificado: quando True, renderiza o documento com selo "Via do Notificado".
    - destinatario_override: quando informado, usa este e-mail como destino, ignorando o cadastro.
    """
    email = (destinatario_override or n.notificado_email or '').strip()
    if not email:
        return False, 'E-mail do notificado ausente.'
    try:
        qr_b64 = _gerar_qr_code_para_notificacao(request, n)
        html = render_to_string('core/documento_notificacao.html', {
            'n': n,
            'request': request,
            'qr_code_base64': qr_b64,
            'via_do_notificado': via_do_notificado,
        })
        pdf_bytes = _pdf_from_html_core(html, request)
        subject = f"Segunda via - Notificação {n.numero}"
        body = (
            "Prezados,\n\n"
            f"Segue em anexo a segunda via da Notificação {n.numero}.\n"
            f"Você também pode visualizar no navegador: {request.build_absolute_uri(reverse('core:fisc_notificacao_documento', args=[n.pk]))}\n\n"
            "Este e-mail foi gerado automaticamente pelo Sistema GCM."
        )
        msg = EmailMessage(subject, body, to=[email])
        msg.attach(f"Notificacao_{n.numero or n.pk}.pdf", pdf_bytes, 'application/pdf')
        msg.send(fail_silently=True)
        return True, None
    except Exception as e:
        return False, str(e)

def fisc_notificacao_validar(request, pk: int, token: str):
    n = get_object_or_404(NotificacaoFiscalizacao, pk=pk)
    ok = False; motivo = ''
    if not n.validacao_token:
        motivo = 'Documento sem token registrado.'
    elif n.validacao_token != token:
        motivo = 'Token inválido.'
    else:
        if not n.validacao_hash:
            motivo = 'Hash ausente.'
        else:
            try:
                ts = int(n.emissao_em.timestamp()) if n.emissao_em else 0
                resumo = f"NOT:{n.numero}|ID:{n.id}|FISC:{n.fiscal_responsavel_id}|TS:{ts}"
                import hashlib
                calc = hashlib.sha256(resumo.encode()).hexdigest()
                ok = (calc == n.validacao_hash)
                if not ok:
                    motivo = 'Hash divergente.'
            except Exception as e:
                motivo = f'Erro ao validar: {e}'
    if request.headers.get('accept','').startswith('application/json'):
        return JsonResponse({'ok': ok, 'motivo': motivo, 'numero': n.numero, 'emissao_em': n.emissao_em})
    return render(request, 'core/validacao_resultado_notificacao.html', {'ok': ok, 'motivo': motivo, 'n': n})


# --------------------- Autos de Infração (Comércio e Som) ---------------------
def _gerar_qr_code_para_auto(request, obj, *, tipo: str):
    """Gera QR para autos de infração (COM ou SOM)."""
    try:
        import qrcode
        import secrets, hashlib, base64
        mudou = False
        if not obj.validacao_token:
            obj.validacao_token = secrets.token_hex(16)
            mudou = True
        ts = int(obj.emissao_em.timestamp()) if obj.emissao_em else 0
        resumo = f"AUTO:{tipo}|NUM:{obj.numero}|ID:{obj.id}|FISC:{obj.fiscal_responsavel_id}|TS:{ts}"
        calc = hashlib.sha256(resumo.encode()).hexdigest()
        if obj.validacao_hash != calc:
            obj.validacao_hash = calc
            mudou = True
        if mudou:
            try:
                obj.save(update_fields=['validacao_token','validacao_hash'])
            except Exception:
                pass
        if tipo == 'COM':
            url = request.build_absolute_uri(reverse('core:fisc_auto_comercio_validar', args=[obj.pk, obj.validacao_token]))
        else:
            url = request.build_absolute_uri(reverse('core:fisc_auto_som_validar', args=[obj.pk, obj.validacao_token]))
        img = qrcode.make(url)
        from io import BytesIO
        buf = BytesIO(); img.save(buf, format='PNG'); b = buf.getvalue(); buf.close()
        return 'data:image/png;base64,' + base64.b64encode(b).decode()
    except Exception:
        return None


def _enviar_segunda_via_auto(request, obj, *, tipo: str, via_do_notificado: bool = False, destinatario_override: str | None = None):
    email = (destinatario_override or obj.notificado_email or '').strip()
    if not email:
        return False, 'E-mail do autuado ausente.'
    try:
        qr_b64 = _gerar_qr_code_para_auto(request, obj, tipo=('COM' if tipo=='COM' else 'SOM'))
        if tipo == 'COM':
            tpl = 'core/documento_auto_comercio.html'
            link_view = request.build_absolute_uri(reverse('core:fisc_auto_comercio_documento', args=[obj.pk]))
            filename = f"Auto_Comercio_{obj.numero or obj.pk}.pdf"
        else:
            tpl = 'core/documento_auto_som.html'
            link_view = request.build_absolute_uri(reverse('core:fisc_auto_som_documento', args=[obj.pk]))
            filename = f"Auto_Som_{obj.numero or obj.pk}.pdf"
        html = render_to_string(tpl, {
            'a': obj,
            'request': request,
            'qr_code_base64': qr_b64,
            'via_do_notificado': via_do_notificado,
        })
        pdf_bytes = _pdf_from_html_core(html, request)
        subject = f"Segunda via - Auto {obj.numero}"
        body = (
            "Prezados,\n\n"
            f"Segue em anexo a segunda via do Auto {obj.numero}.\n"
            f"Você também pode visualizar no navegador: {link_view}\n\n"
            "Este e-mail foi gerado automaticamente pelo Sistema GCM."
        )
        msg = EmailMessage(subject, body, to=[email])
        msg.attach(filename, pdf_bytes, 'application/pdf')
        msg.send(fail_silently=True)
        return True, None
    except Exception as e:
        return False, str(e)


@login_required
def fiscalizacao_auto_comercio_novo(request):
    if request.method == 'POST':
        form = AutoInfracaoComercioForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_auto(request, obj, tipo='COM', via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_auto_comercio')
    else:
        initial = {
            'fiscal_matricula': getattr(getattr(request.user, 'perfil', None), 'matricula', '')
        }
        form = AutoInfracaoComercioForm(initial=initial)
    return render(request, 'core/fisc_auto_comercio_form.html', {'form': form, 'is_edit': False})


@login_required
def fiscalizacao_auto_comercio_editar(request, pk: int):
    obj = get_object_or_404(AutoInfracaoComercio, pk=pk)
    if request.method == 'POST':
        form = AutoInfracaoComercioForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_auto(request, obj, tipo='COM', via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_auto_comercio')
    else:
        form = AutoInfracaoComercioForm(instance=obj)
    return render(request, 'core/fisc_auto_comercio_form.html', {'form': form, 'is_edit': True, 'obj': obj})


@login_required
def fiscalizacao_auto_comercio_excluir(request, pk: int):
    obj = get_object_or_404(AutoInfracaoComercio, pk=pk)
    if not (request.user.is_superuser or request.user.username.lower() == 'moises'):
        return HttpResponseForbidden('Sem permissão para excluir este registro.')
    if request.method == 'POST':
        obj.delete()
        return redirect('core:fisc_auto_comercio')
    return render(request, 'core/confirm_delete.html', {
        'titulo': f'Excluir Auto (Comércio) {obj.numero}',
        'mensagem': 'Tem certeza que deseja excluir este registro? Esta ação não pode ser desfeita.',
        'action_url': request.path,
    })


@login_required
def fiscalizacao_auto_som_novo(request):
    if request.method == 'POST':
        form = AutoInfracaoSomForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_auto(request, obj, tipo='SOM', via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_auto_som')
    else:
        initial = {
            'fiscal_matricula': getattr(getattr(request.user, 'perfil', None), 'matricula', '')
        }
        form = AutoInfracaoSomForm(initial=initial)
    return render(request, 'core/fisc_auto_som_form.html', {'form': form, 'is_edit': False})


@login_required
def fiscalizacao_auto_som_editar(request, pk: int):
    obj = get_object_or_404(AutoInfracaoSom, pk=pk)
    if request.method == 'POST':
        form = AutoInfracaoSomForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            obj = form.save(user=request.user)
            try:
                if form.cleaned_data.get('enviar_segunda_via'):
                    ok, err = _enviar_segunda_via_auto(request, obj, tipo='SOM', via_do_notificado=True)
                    if ok:
                        messages.success(request, 'Segunda via enviada por e-mail.')
                    else:
                        messages.warning(request, f'Não foi possível enviar o e-mail: {err or "erro desconhecido"}.')
            except Exception as e:
                messages.warning(request, f'Falha ao preparar e-mail: {e}')
            return redirect('core:fisc_auto_som')
    else:
        form = AutoInfracaoSomForm(instance=obj)
    return render(request, 'core/fisc_auto_som_form.html', {'form': form, 'is_edit': True, 'obj': obj})


@login_required
def fiscalizacao_auto_som_excluir(request, pk: int):
    obj = get_object_or_404(AutoInfracaoSom, pk=pk)
    if not (request.user.is_superuser or request.user.username.lower() == 'moises'):
        return HttpResponseForbidden('Sem permissão para excluir este registro.')
    if request.method == 'POST':
        obj.delete()
        return redirect('core:fisc_auto_som')
    return render(request, 'core/confirm_delete.html', {
        'titulo': f'Excluir Auto (Som) {obj.numero}',
        'mensagem': 'Tem certeza que deseja excluir este registro? Esta ação não pode ser desfeita.',
        'action_url': request.path,
    })


# ---- Documento Auto (visualizar/baixar PDF) ----
@login_required
def fisc_auto_comercio_documento(request, pk: int):
    a = get_object_or_404(AutoInfracaoComercio, pk=pk)
    qr_b64 = _gerar_qr_code_para_auto(request, a, tipo='COM')
    return render(request, 'core/visualizar_documento_auto_comercio.html', {'a': a, 'qr_code_base64': qr_b64})


@login_required
def fisc_auto_comercio_baixar_pdf(request, pk: int):
    a = get_object_or_404(AutoInfracaoComercio, pk=pk)
    qr_b64 = _gerar_qr_code_para_auto(request, a, tipo='COM')
    html = render_to_string('core/documento_auto_comercio.html', {'a': a, 'request': request, 'qr_code_base64': qr_b64})
    pdf = _pdf_from_html_core(html, request)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f"attachment; filename=Auto_Comercio_{a.numero or a.pk}.pdf"
    resp['Cache-Control'] = 'no-store'
    return resp


@login_required
def fisc_auto_som_documento(request, pk: int):
    a = get_object_or_404(AutoInfracaoSom, pk=pk)
    qr_b64 = _gerar_qr_code_para_auto(request, a, tipo='SOM')
    return render(request, 'core/visualizar_documento_auto_som.html', {'a': a, 'qr_code_base64': qr_b64})


@login_required
def fisc_auto_som_baixar_pdf(request, pk: int):
    a = get_object_or_404(AutoInfracaoSom, pk=pk)
    qr_b64 = _gerar_qr_code_para_auto(request, a, tipo='SOM')
    html = render_to_string('core/documento_auto_som.html', {'a': a, 'request': request, 'qr_code_base64': qr_b64})
    pdf = _pdf_from_html_core(html, request)
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f"attachment; filename=Auto_Som_{a.numero or a.pk}.pdf"
    resp['Cache-Control'] = 'no-store'
    return resp


def fisc_auto_comercio_validar(request, pk: int, token: str):
    a = get_object_or_404(AutoInfracaoComercio, pk=pk)
    ok = False; motivo = ''
    if not a.validacao_token:
        motivo = 'Documento sem token registrado.'
    elif a.validacao_token != token:
        motivo = 'Token inválido.'
    else:
        if not a.validacao_hash:
            motivo = 'Hash ausente.'
        else:
            try:
                ts = int(a.emissao_em.timestamp()) if a.emissao_em else 0
                resumo = f"AUTO:COM|NUM:{a.numero}|ID:{a.id}|FISC:{a.fiscal_responsavel_id}|TS:{ts}"
                import hashlib
                calc = hashlib.sha256(resumo.encode()).hexdigest()
                ok = (calc == a.validacao_hash)
                if not ok:
                    motivo = 'Hash divergente.'
            except Exception as e:
                motivo = f'Erro ao validar: {e}'
    if request.headers.get('accept','').startswith('application/json'):
        return JsonResponse({'ok': ok, 'motivo': motivo, 'numero': a.numero, 'emissao_em': a.emissao_em})
    return render(request, 'core/validacao_resultado_auto_comercio.html', {'ok': ok, 'motivo': motivo, 'a': a})


def fisc_auto_som_validar(request, pk: int, token: str):
    a = get_object_or_404(AutoInfracaoSom, pk=pk)
    ok = False; motivo = ''
    if not a.validacao_token:
        motivo = 'Documento sem token registrado.'
    elif a.validacao_token != token:
        motivo = 'Token inválido.'
    else:
        if not a.validacao_hash:
            motivo = 'Hash ausente.'
        else:
            try:
                ts = int(a.emissao_em.timestamp()) if a.emissao_em else 0
                resumo = f"AUTO:SOM|NUM:{a.numero}|ID:{a.id}|FISC:{a.fiscal_responsavel_id}|TS:{ts}"
                import hashlib
                calc = hashlib.sha256(resumo.encode()).hexdigest()
                ok = (calc == a.validacao_hash)
                if not ok:
                    motivo = 'Hash divergente.'
            except Exception as e:
                motivo = f'Erro ao validar: {e}'
    if request.headers.get('accept','').startswith('application/json'):
        return JsonResponse({'ok': ok, 'motivo': motivo, 'numero': a.numero, 'emissao_em': a.emissao_em})
    return render(request, 'core/validacao_resultado_auto_som.html', {'ok': ok, 'motivo': motivo, 'a': a})
