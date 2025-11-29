# viaturas/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from taloes.models import ChecklistViatura
from .models import Viatura, ViaturaAvariaEstado, AvariaResolvidaLog
from cecom.models import PlantaoCECOM

 
from .forms import ViaturaForm, ObservacoesViaturaForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse

# --- Rastreamento em tempo real (endpoint leve para app móvel) ---
@login_required
@require_POST
def track(request):
    """Recebe coordenadas de geolocalização do usuário (guarda mínima ou só log futuro).

    Payload esperado (JSON): latitude, longitude, precisao (accuracy), velocidade (km/h), direcao (heading).
    Por enquanto persiste somente em log simplificado (pode evoluir para model ViaturaPosicaoHist).
    Retorna JSON {ok:true} ou erro com status 400.
    """
    try:
        import json, math, time
        data = json.loads(request.body.decode('utf-8') or '{}')
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'payload inválido'}, status=400)
    # Valida faixa básica
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({'ok': False, 'error': 'coordenadas fora de faixa'}, status=400)
    # TODO: associar a viatura ativa do usuário (se houver) e salvar histórico.
    # Log rápido (django logger root)
    try:
        import logging
        logging.getLogger(__name__).info('TRACK %s (%s, %s)', request.user.username, lat, lng)
    except Exception:
        pass
    return JsonResponse({'ok': True})

@login_required
def lista(request):
    status = request.GET.get("status")
    mostrar_inativas = request.GET.get("inativas") == "1"
    qs = Viatura.objects.all()
    if status:
        qs = qs.filter(status=status)
    if not mostrar_inativas:
        qs = qs.filter(ativo=True)

    termo = request.GET.get("q")
    if termo:
        qs = qs.filter(Q(prefixo__icontains=termo) | Q(placa__icontains=termo))

    paginator = Paginator(qs.order_by('prefixo'), 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Fonte primária: estado persistente por viatura (independe do checklist de hoje)
    estados = {e.viatura_id: set(e.get_labels()) for e in ViaturaAvariaEstado.objects.all()}
    # Fallback lazily hydrates missing states from last 7 days of checklists
    faltantes = {v.id for v in page_obj.object_list if v.id not in estados}
    if faltantes:
        try:
            from datetime import timedelta
            hoje = timezone.localdate()
            cks = list(ChecklistViatura.objects.filter(data__gte=hoje - timedelta(days=7), plantao_id__isnull=False))
            pl_map = {pl['id']: pl['viatura_id'] for pl in PlantaoCECOM.objects.filter(id__in=list({ck.plantao_id for ck in cks if ck.plantao_id})).values('id','viatura_id')}
            acc: dict[int,set] = {}
            for ck in cks:
                vid = pl_map.get(ck.plantao_id)
                if vid in faltantes:
                    try:
                        labels = set(ck.itens_marcados())
                    except Exception:
                        labels = set()
                    if labels:
                        acc.setdefault(vid,set()).update(labels)
            # criar estados para os faltantes com labels encontrados
            for vid, labels in acc.items():
                if labels:
                    try:
                        est, _ = ViaturaAvariaEstado.objects.get_or_create(viatura_id=vid)
                        est.set_labels(sorted(labels))
                        est.save(update_fields=["labels_json","atualizado_em"])
                        estados[vid] = set(est.get_labels())
                    except Exception:
                        estados[vid] = labels
        except Exception:
            pass

    # Atribui atributo auxiliar em cada viatura da página
    for v in page_obj.object_list:
        try:
            val = estados.get(v.id, set())
            v.avarias_rel = len(val) if isinstance(val, set) else int(val or 0)
        except Exception:
            v.avarias_rel = 0

    return render(request, "viaturas/lista.html", {
        "viaturas": page_obj.object_list,
        "page_obj": page_obj,
        "status": status,
        "mostrar_inativas": mostrar_inativas,
    })

@login_required
def criar(request):
    if request.method == "POST":
        form = ViaturaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Viatura criada.")
            return redirect("viaturas:lista")
    else:
        form = ViaturaForm()
    return render(request, "viaturas/form.html", {"form": form, "titulo": "Nova Viatura"})

@login_required
def editar(request, pk):
    v = get_object_or_404(Viatura, pk=pk)
    if request.method == "POST":
        form = ViaturaForm(request.POST, instance=v)
        if form.is_valid():
            form.save()
            messages.success(request, "Alterações salvas.")
            return redirect("viaturas:lista")
    else:
        form = ViaturaForm(instance=v)
    return render(request, "viaturas/form.html", {"form": form, "titulo": f"Editar {v.prefixo}"})


@login_required
def avarias(request, pk):
    """Lista detalhada das avarias relatadas hoje para a VTR, com base nos checklists vinculados a plantoes desta viatura."""
    v = get_object_or_404(Viatura, pk=pk)
    hoje = timezone.localdate()
    # Filtros de auditoria
    data_de = request.GET.get("data_de")
    data_ate = request.GET.get("data_ate")
    mostrar_mais = request.GET.get("mais") == "1"
    trocar_viatura = request.GET.get("viatura")

    # Se o usuário selecionou outra viatura no filtro, redireciona mantendo os filtros de data/mais
    if trocar_viatura and str(trocar_viatura) != str(pk):
        from urllib.parse import urlencode
        params = {}
        if data_de:
            params["data_de"] = data_de
        if data_ate:
            params["data_ate"] = data_ate
        if mostrar_mais:
            params["mais"] = "1"
        url = reverse("viaturas:avarias", args=[trocar_viatura])
        if params:
            url = f"{url}?{urlencode(params)}"
        return redirect(url)
    # Encontrar plantoes de hoje com esta viatura
    plantoes_ids = list(PlantaoCECOM.objects.filter(viatura=v, inicio__date=hoje).values_list('id', flat=True))
    itens: list[str] = []
    reg_count = 0
    if plantoes_ids:
        for ck in ChecklistViatura.objects.filter(plantao_id__in=plantoes_ids, data=hoje):
            marcados = ck.itens_marcados()
            if marcados:
                itens.extend(marcados)
                reg_count += 1
    # Fallback: checklists do dia do usuário sem plantao atrelado não entram, pois queremos a VTR específica do plantão
    # Unir com estado persistente, para mostrar mesmo sem checklist de hoje
    try:
        estado = ViaturaAvariaEstado.objects.filter(viatura=v).first()
        base_labels = set(estado.get_labels()) if estado else set()
    except Exception:
        base_labels = set()
    itens_unicos = sorted(set(itens).union(base_labels))
    paginator = Paginator(itens_unicos, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    # Logs do dia (todos usuários enxergam)
    from taloes.models import AvariaLog
    logs_dia = list(AvariaLog.objects.select_related('usuario').filter(viatura=v, data=hoje).order_by('-criado_em'))
    # Resoluções - com filtros (por padrão mostra só as de hoje; com "mais" mostra últimas N; com datas aplica intervalo)
    resolvidos_qs = AvariaResolvidaLog.objects.select_related('usuario').filter(viatura=v).order_by('-criado_em')
    has_interval = False
    from datetime import datetime
    if data_de:
        try:
            d1 = datetime.strptime(data_de, '%Y-%m-%d').date()
            resolvidos_qs = resolvidos_qs.filter(criado_em__date__gte=d1)
            has_interval = True
        except Exception:
            pass
    if data_ate:
        try:
            d2 = datetime.strptime(data_ate, '%Y-%m-%d').date()
            resolvidos_qs = resolvidos_qs.filter(criado_em__date__lte=d2)
            has_interval = True
        except Exception:
            pass
    if not has_interval and not mostrar_mais:
        resolvidos_qs = resolvidos_qs.filter(criado_em__date=hoje)
    if mostrar_mais and not has_interval:
        resolvidos_qs = resolvidos_qs[:20]
    resolvidos = list(resolvidos_qs)

    # Viaturas para filtro de troca rápida
    viaturas_all = Viatura.objects.filter(ativo=True).only('id','prefixo').order_by('prefixo')

    # Buscar anexos de avarias dos checklists de hoje
    from taloes.models import AvariaAnexo
    anexos_map = {}
    if plantoes_ids:
        checklists_ids = list(ChecklistViatura.objects.filter(plantao_id__in=plantoes_ids, data=hoje).values_list('id', flat=True))
        if checklists_ids:
            anexos = AvariaAnexo.objects.filter(checklist_id__in=checklists_ids).select_related('checklist').order_by('-criado_em')
            for anexo in anexos:
                campo = anexo.campo_label
                if campo not in anexos_map:
                    anexos_map[campo] = []
                anexos_map[campo].append(anexo)

    contexto = {
        "viatura": v,
        "page_obj": page_obj,
        "quantidade": len(itens_unicos),
        "registros": reg_count,
        "data": hoje,
        "logs_dia": logs_dia,
        "resolvidos_dia": [r for r in resolvidos if getattr(r, 'criado_em', None) and r.criado_em.date() == hoje],  # compat
        "resolvidos": resolvidos,
        "resolvidos_is_expanded": bool(mostrar_mais or has_interval),
        "data_de": data_de or "",
        "data_ate": data_ate or "",
        "viaturas_all": viaturas_all,
        "anexos_map": anexos_map,
    }
    return render(request, "viaturas/avarias.html", contexto)


@login_required
@require_POST
def resolver_avarias(request, pk):
    """Marca como resolvidas as avarias selecionadas, limpando os campos correspondentes
    nos checklists de hoje vinculados aos plantões dessa viatura.

    Entrada: POST com 'itens' = lista de labels exatamente como exibidas em itens_marcados().
    Efeito: seta False nos booleans correspondentes e, se "Outros: <texto>" estiver entre os itens,
    limpa o campo 'outros'.
    """
    v = get_object_or_404(Viatura, pk=pk)
    selecionados = request.POST.getlist('itens')
    if not selecionados:
        messages.info(request, "Nenhuma avaria selecionada.")
        return redirect("viaturas:avarias", pk=pk)
    hoje = timezone.localdate()
    # Plantões de hoje desta viatura (opcional)
    plantoes_ids = list(PlantaoCECOM.objects.filter(viatura=v, inicio__date=hoje).values_list('id', flat=True))

    # Mapa reverso label->campo (igual ao usado em itens_marcados)
    label_to_field = {
        'Rádio Comunicador': 'radio_comunicador',
        'Sistema Luminoso (High Light)': 'sistema_luminoso',
        'Bancos': 'bancos',
        'Tapetas': 'tapetas',
        'Painel': 'painel',
        'Limpeza Interna': 'limpeza_interna',
        'Antena': 'antena',
        'Pneus': 'pneus',
        'Calotas': 'calotas',
        'Rodas de Liga': 'rodas_liga',
        'Para-brisa': 'para_brisa',
        'Palhetas dianteiras': 'palhetas_dianteiras',
        'Palheta Traseira': 'palheta_traseira',
        'Faróis/Piscas Dianteiros': 'farois_dianteiros',
        'Faróis de Neblina': 'farois_neblina',
        'Lanterna/Piscas Traseiros': 'lanternas_traseiras',
        'Luz de Ré': 'luz_re',
        'Sensor de Estacionamento': 'sensor_estacionamento',
        'Portinhola Tanque Combustível': 'portinhola_tanque',
        'Fluido de Freio': 'fluido_freio',
        'Líquido de Arrefecimento': 'liquido_arrefecimento',
        'Fluido Direção Hidráulica': 'fluido_direcao',
        'Bateria (Controle Visual)': 'bateria',
        'Amortecedor': 'amortecedor',
        'Tampa do Porta-Malas': 'tampa_porta_malas',
        'Estepe': 'estepe',
        'Triângulo': 'triangulo',
        'Chave de Rodas': 'chave_rodas',
        'Macaco': 'macaco',
        'Suspensão (Barulhos)': 'suspensao',
        'Documentação': 'documentacao',
        'Óleo (nível e troca)': 'oleo',
    }

    outros_marcado = any(it.startswith('Outros:') for it in selecionados)
    campos_alvo = {label_to_field[it] for it in selecionados if it in label_to_field}

    alterados = 0
    if plantoes_ids:
        for ck in ChecklistViatura.objects.filter(plantao_id__in=plantoes_ids, data=hoje):
            updates = []
            for campo in campos_alvo:
                if getattr(ck, campo, False):
                    setattr(ck, campo, False)
                    updates.append(campo)
            if outros_marcado and getattr(ck, 'outros', ''):
                ck.outros = ''
                updates.append('outros')
            if updates:
                ck.save(update_fields=list(set(updates)))
                alterados += 1

    # Mensagens amigáveis
    if campos_alvo or outros_marcado:
        if alterados:
            messages.success(request, f"Avarias resolvidas (atualizados {alterados} checklist(s) de hoje).")
        else:
            messages.success(request, "Avarias resolvidas.")
    # Atualizar estado persistente desta viatura removendo os labels selecionados
    try:
        estado, _ = ViaturaAvariaEstado.objects.get_or_create(viatura=v)
        atuais = set(estado.get_labels())
        novas = [lbl for lbl in atuais if (lbl not in selecionados and not (lbl.startswith('Outros:') and outros_marcado))]
        estado.set_labels(novas)
        estado.save(update_fields=["labels_json","atualizado_em"])
    except Exception:
        pass

    # Registro de auditoria (quem resolveu, quando, itens)
    try:
        import json as _json
        AvariaResolvidaLog.objects.create(
            viatura=v,
            usuario=request.user if request.user.is_authenticated else None,
            itens_json=_json.dumps(list(selecionados), ensure_ascii=False),
            criado_em=timezone.now(),
        )
    except Exception:
        pass
    return redirect("viaturas:avarias", pk=pk)


@login_required
def observacoes(request, pk):
    """Edição rápida apenas das observações da viatura."""
    v = get_object_or_404(Viatura, pk=pk)
    if request.method == "POST":
        form = ObservacoesViaturaForm(request.POST, instance=v)
        if form.is_valid():
            form.save(update_fields=["observacoes", "atualizado_em"])
            messages.success(request, f"Observações da viatura {v.prefixo} atualizadas.")
            return redirect("viaturas:lista")
    else:
        form = ObservacoesViaturaForm(instance=v)
    return render(request, "viaturas/observacoes.html", {"form": form, "viatura": v})

@login_required
def arquivar(request, pk):
    v = get_object_or_404(Viatura, pk=pk)
    v.ativo = False
    v.save(update_fields=["ativo"])
    messages.info(request, f"Viatura {v.prefixo} arquivada.")
    return redirect("viaturas:lista")

@login_required
def restaurar(request, pk):
    v = get_object_or_404(Viatura, pk=pk)
    v.ativo = True
    v.save(update_fields=["ativo"])
    messages.success(request, f"Viatura {v.prefixo} restaurada.")
    return redirect("viaturas:lista")

@login_required
@require_POST
def excluir(request, pk):
    v = get_object_or_404(Viatura, pk=pk)
    prefixo = v.prefixo
    v.delete()
    messages.warning(request, f"Viatura {prefixo} excluída.")
    return redirect("viaturas:lista")
