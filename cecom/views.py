# cecom/views.py
from __future__ import annotations

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
import json
import hashlib

from .models import (
    DespachoOcorrencia, PlantaoCecomPrincipal, LivroPlantaoCecom,
    LivroPlantaoCecomViatura, LivroPlantaoCecomPostoFixo, LivroPlantaoCecomRelatorio,
    LivroPlantaoCecomPessoa,
    PlantaoCECOM, ViaturaLocalizacao, ViaturaLocalizacaoPonto,
)
from .forms import (
    DespachoOcorrenciaForm,
    PlantaoCecomIniciarForm,
    LivroPlantaoCecomForm,
    LivroPlantaoCecomViaturaForm,
    LivroPlantaoCecomPostoFixoForm,
)
from common.models import PushDevice
from common.views import enviar_push
from taloes.views_extra import SESSION_PLANTAO

# Pega o modelo sem depender de taloes.models existir como arquivo
Talao = apps.get_model("taloes", "Talao")
ChecklistViatura = apps.get_model("taloes", "ChecklistViatura")


def _taloes_abertos():
    """
    Retorna todos os talões com status ABERTO no sistema.
    """
    return (
        Talao.objects.select_related("viatura", "codigo_ocorrencia", "encarregado", "motorista")
        .filter(status="ABERTO")
        .order_by("-iniciado_em")
    )


@login_required
def painel(request):
    """Painel principal do CECOM com paginação em talões e despachos recentes."""
    # Novo comportamento: painel sempre visível (somente leitura) para todos.
    # Ações (iniciar / encerrar / editar livro) restringidas ao iniciador do plantão ativo ou superadmin 'moises'.
    ativo_global = PlantaoCecomPrincipal.objects.filter(ativo=True).order_by('-inicio').first()
    pode_editar_global = False
    if ativo_global and (ativo_global.usuario_id == request.user.id or (request.user.username == 'moises' and request.user.is_superuser)):
        pode_editar_global = True
    # Apenas quem iniciou o plantão (ou superadmin moises) pode abrir nova ocorrência enquanto plantão ativo
    pode_criar_ocorrencia = False
    if ativo_global and (ativo_global.usuario_id == request.user.id or (request.user.username == 'moises' and request.user.is_superuser)):
        pode_criar_ocorrencia = True
    taloes_list = _taloes_abertos()
    despachos_qs = (
        DespachoOcorrencia.objects
        .select_related("viatura", "despachado_por")
        .filter(arquivado=False)
        .exclude(status="FINALIZADO")
        .order_by("-despachado_em")
    )

    # Cancelados ou recusados (não arquivados) para exibição separada
    cancelados_recusados_qs = DespachoOcorrencia.objects.select_related("viatura", "despachado_por").filter(
        arquivado=False, status__in=["CANCELADO", "RECUSADO"]
    ).order_by("-despachado_em")
    # Paginação separada (query params distintos)
    taloes_paginator = Paginator(taloes_list, 10)
    despachos_paginator = Paginator(despachos_qs, 10)
    taloes_page = taloes_paginator.get_page(request.GET.get('page_tal'))
    despachos_page = despachos_paginator.get_page(request.GET.get('page_des'))

    despachos_pendentes_count = DespachoOcorrencia.objects.filter(
        status='PENDENTE', respondido_em__isnull=True, arquivado=False
    ).count()
    cancelados_recusados_count = cancelados_recusados_qs.count()

    plantao_cecom = PlantaoCecomPrincipal.ativo_do_usuario_ou_aux(request.user)
    # Letra da equipe para exibição junto dos integrantes
    plantao_equipe = ''
    try:
        for obj in [plantao_cecom, ativo_global]:
            if obj and hasattr(obj, 'livro') and getattr(obj.livro, 'equipe_plantao', ''):
                plantao_equipe = obj.livro.equipe_plantao or ''
                break
    except Exception:
        plantao_equipe = ''
    # Fallback: usar a equipe selecionada no módulo de Talões (sessão)
    if not plantao_equipe:
        try:
            plantao_equipe = (request.session.get(SESSION_PLANTAO) or '').strip()
        except Exception:
            plantao_equipe = ''
    relatorios_livro = []
    if plantao_cecom:
        # Pré-visualização dos relatórios que serão gerados no encerramento
        from datetime import datetime
        data_ref = timezone.localtime(plantao_cecom.inicio).strftime('%Y-%m-%d')
        pid = plantao_cecom.pk
        relatorios_livro = [
            {
                'codigo': 'resumo',
                'titulo': 'Resumo do Plantão',
                'arquivo_previsto': f'resumo_plantao_cecom_{pid}_{data_ref}.pdf',
                'descricao': 'Dados gerais, equipe, CGA, horários.'
            },
            {
                'codigo': 'viaturas',
                'titulo': 'Viaturas e Equipes',
                'arquivo_previsto': f'viaturas_equipes_cecom_{pid}_{data_ref}.pdf',
                'descricao': 'Lista das viaturas e integrantes registrados no livro.'
            },
            {
                'codigo': 'postos',
                'titulo': 'Postos Fixos',
                'arquivo_previsto': f'postos_fixos_cecom_{pid}_{data_ref}.pdf',
                'descricao': 'Postos fixos com GCMs designados.'
            },
            {
                'codigo': 'anotacoes',
                'titulo': 'Anotações e Checklist',
                'arquivo_previsto': f'anotacoes_checklist_cecom_{pid}_{data_ref}.pdf',
                'descricao': 'Dispensados, atrasos, banco de horas, checklist e ocorrências.'
            },
        ]
    # --------- Avarias por viatura (plantões ativos) ---------
    hoje = timezone.localdate()
    ativos_pl = PlantaoCECOM.objects.select_related('viatura').prefetch_related('participantes__usuario').filter(ativo=True, viatura__isnull=False)
    viatura_por_plantao = {p.id: p.viatura_id for p in ativos_pl}
    prefixo_por_viatura = {p.viatura_id: getattr(p.viatura, 'prefixo', '') for p in ativos_pl}
    # Mapa de integrantes por viatura (plantões ativos)
    func_map = { 'ENC': 'Enc', 'MOT': 'Mot', 'AUX1': 'Aux1', 'AUX2': 'Aux2' }
    integrantes_map: dict[int, str] = {}
    for p in ativos_pl:
        try:
            nomes: list[str] = []
            for part in p.participantes.select_related('usuario').filter(saida_em__isnull=True):
                u = part.usuario
                if not u:
                    continue
                nome = (getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', '')).strip()
                label = func_map.get(part.funcao or '', '')
                nomes.append(f"{label+': ' if label else ''}{nome}")
            integrantes_map[p.viatura_id] = " · ".join(nomes)
        except Exception:
            integrantes_map[p.viatura_id] = ""
    avarias_map: dict[int, list[str]] = {}
    try:
        from viaturas.models import ViaturaAvariaEstado
        estados = {e.viatura_id: e.get_labels() for e in ViaturaAvariaEstado.objects.filter(viatura_id__in=list(prefixo_por_viatura.keys()))}
        avarias_map.update({vid: (labels or []) for vid, labels in estados.items()})
    except Exception:
        pass

    # Contador de pânico em aberto para badge na UI
    panico_abertos_count = 0
    try:
        from panic.models import DisparoPanico  # import local para evitar acoplamento
        panico_abertos_count = DisparoPanico.objects.filter(status='ABERTA').count()
    except Exception:
        panico_abertos_count = 0

    ctx = {
        "taloes_page": taloes_page,
        "despachos_page": despachos_page,
        "taloes_abertos_count": taloes_list.count(),
        "despachos_pendentes_count": despachos_pendentes_count,
        "cancelados_recusados_count": cancelados_recusados_count,
        "cancelados_recusados": cancelados_recusados_qs[:10],  # mostrar últimos 10
        "agora": timezone.localtime(),
        "plantao_cecom": plantao_cecom,
        "ativo_global": ativo_global,
        "plantao_cecom_iniciar_form": PlantaoCecomIniciarForm(request_user=request.user) if (not plantao_cecom and not ativo_global) else None,
    "pode_editar_global": pode_editar_global,
    "pode_criar_ocorrencia": pode_criar_ocorrencia,
        "relatorios_livro": relatorios_livro,
        # Avarias atuais por viatura ativa
        "avarias_map": avarias_map,
        "prefixo_por_viatura": prefixo_por_viatura,
        # Integrantes atuais por viatura ativa (para exibir mesmo se o talão não gravou FKs/equipe_texto)
        "integrantes_map": integrantes_map,
        # Equipe (A/B/C/D) para exibir junto dos integrantes
        "plantao_equipe": plantao_equipe,
        # Badge Pânico
        "panico_abertos_count": panico_abertos_count,
    }
    return render(request, "cecom/painel.html", ctx)


@login_required
def iniciar_plantao_cecom(request):
    if request.method != 'POST':
        return redirect('cecom:painel')
    if PlantaoCecomPrincipal.ativo_do_usuario(request.user):
        messages.warning(request, 'Você já possui um plantão CECOM ativo.')
        return redirect('cecom:painel')
    form = PlantaoCecomIniciarForm(request.POST, request_user=request.user)
    if form.is_valid():
        plantao = form.save(commit=False)
        plantao.usuario = request.user
        plantao.save()
        messages.success(request, 'Plantão CECOM iniciado.')
    else:
        if form.errors.get('aux_cecom'):
            messages.error(request, 'Selecione o operador para iniciar.')
        else:
            messages.error(request, 'Não foi possível iniciar o plantão.')
    return redirect('cecom:painel')


@login_required
def encerrar_plantao_cecom(request, pk):
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk, usuario=request.user)
    # Validações obrigatórias antes de encerrar
    # 1) Livro eletrônico deve existir com Coordenador (CGA) e Equipe definidos
    livro = getattr(plantao, 'livro', None)
    if not livro:
        messages.error(request, 'Preencha o Livro Eletrônico do CECOM antes de encerrar o plantão.')
        return redirect('cecom:livro_cecom', pk=plantao.pk)
    if not getattr(livro, 'cga_do_dia', None):
        messages.error(request, 'Defina o Coordenador/Líder (CGA do dia) no Livro do Plantão.')
        return redirect('cecom:livro_cecom', pk=plantao.pk)
    equipe_codigo = (getattr(livro, 'equipe_plantao', '') or '').strip()
    if not equipe_codigo:
        messages.error(request, 'Selecione a Equipe de Plantão (A/B/C/D) no Livro do Plantão.')
        return redirect('cecom:livro_cecom', pk=plantao.pk)
    # 2) Não pode haver despachos não arquivados no período do plantão
    from django.utils import timezone as _tz
    inicio_ref = getattr(plantao, 'inicio', None) or _tz.now()  # fallback seguro
    nao_arquivados_qs = (
        DespachoOcorrencia.objects
        .filter(arquivado=False, despachado_em__gte=inicio_ref)
    )
    if nao_arquivados_qs.exists():
        qtd = nao_arquivados_qs.count()
        messages.error(request, f'Existem {qtd} despachos não arquivados. Arquive todos os despachos para encerrar o plantão.')
        return redirect('cecom:despachos')
    # Primeiro encerra o plantão para garantir encerrado_em preenchido
    plantao.encerrar()
    # Integração: somar Banco de Horas dos registros do Livro (tipo BANCO)
    try:
        livro = getattr(plantao, 'livro', None)
        if livro:
            # Somar minutos por usuário (um lançamento consolidado por livro)
            from collections import defaultdict
            minutos_por_user: dict[int, int] = defaultdict(int)
            for pp in livro.pessoas.select_related('usuario').filter(tipo='BANCO'):
                u = getattr(pp, 'usuario', None)
                tot = int(getattr(pp, 'total_minutos', 0) or 0)
                if u and u.id and tot > 0:
                    minutos_por_user[u.id] += tot
            if minutos_por_user:
                # Import local para evitar acoplamento circular em import top-level
                from core.models import BancoHorasLancamento, BancoHorasSaldo  # type: ignore
                from django.contrib.auth import get_user_model
                U = get_user_model()
                ref_type = 'LIVRO_CECOM'
                ref_id = str(plantao.id)
                for uid, minutos in minutos_por_user.items():
                    try:
                        # Evitar lançamentos duplicados para o mesmo livro/usuário
                        existe = BancoHorasLancamento.objects.filter(user_id=uid, ref_type=ref_type, ref_id=ref_id).exists()
                        if existe:
                            continue
                        alvo = U.objects.get(pk=uid)
                        motivo = f"Livro CECOM #{plantao.id} ({timezone.localtime(plantao.inicio):%d/%m/%Y})"
                        BancoHorasLancamento.ajustar_saldo(
                            alvo,
                            minutos,
                            origem=ref_type,
                            motivo=motivo,
                            ref_type=ref_type,
                            ref_id=ref_id,
                            created_by=request.user,
                        )
                    except Exception:
                        # Não bloquear encerramento por falhas de integração
                        pass
    except Exception:
        # Segurança: qualquer exceção na integração não deve impedir o fluxo
        pass
    # Gera relatório (se existir livro)
    livro = getattr(plantao, 'livro', None)
    if livro and not hasattr(plantao, 'relatorio_pdf'):
        try:
            gerar_relatorio_livro_cecom(plantao, livro)
        except Exception as e:
            messages.error(request, f'Falha gerando relatório: {e}')
    messages.success(request, 'Plantão CECOM encerrado e relatório consolidado gerado.')
    return redirect('cecom:relatorios_livro')


def _fmt_user_line(u):
    if not u:
        return '-'
    perfil = getattr(u, 'perfil', None)
    mat = getattr(perfil, 'matricula', '') if perfil else ''
    nome = (u.get_full_name() or u.username).strip()
    return f"{mat} - {nome}" if mat else nome


def gerar_relatorio_livro_cecom(plantao: PlantaoCecomPrincipal, livro: LivroPlantaoCecom):
    """Gera PDF consolidado com todas as seções do livro e cria registro LivroPlantaoCecomRelatorio.

    Atualizado para usar cabeçalho institucional unificado com logo e metadados (similar aos relatórios de talões)
    e incluir assinatura do Operador do CECOM (aux_cecom) ao final.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from django.conf import settings
    from pathlib import Path
    import base64, textwrap as _tw
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w,h = A4
    y = h - 40  # topo mais justo
    # Cabeçalho institucional (texto deslocado levemente à esquerda)
    header_lines = [
        'PREFEITURA DA ESTÂNCIA TURÍSTICA DE IBIÚNA',
        'Secretaria Municipal de Segurança Pública',
        'Livro Eletrônico do CECOM da Guarda Civil Municipal'
    ]
    line_spacing = 12
    header_top_y = y
    logo_path = None
    logo_w = logo_h = 0
    try:
        candidates = [Path(settings.BASE_DIR)/'static'/'img'/'logo_gcm.png']
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            candidates.append(Path(static_root)/'img'/'logo_gcm.png')
        for p in candidates:
            if p.exists():
                logo_path = p; break
        if logo_path:
            from PIL import Image as _PIL
            from reportlab.lib.utils import ImageReader
            with _PIL.open(logo_path) as im:
                w0,h0 = im.size
                max_side = 75
                esc = min(max_side/w0, max_side/h0, 1)
                logo_w = w0*esc; logo_h = h0*esc
            logo_reader = ImageReader(str(logo_path))
            # Logo mais para esquerda e topo
            logo_x = 60
            logo_y = header_top_y - logo_h + 5
            c.drawImage(logo_reader, logo_x, logo_y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    # Textos ao lado do logo, centralizados verticalmente com o meio do logo
    text_x = 60 + (logo_w or 70) + 20  # espaço após logo
    c.setFont('Helvetica-Bold',10)
    # Calcular início Y para centralizar o bloco de 3 linhas no meio do logo
    logo_center_y = (header_top_y - (logo_h - 5)) + (logo_h / 2) if logo_h else header_top_y - 20
    text_block_height = (len(header_lines)-1) * line_spacing
    text_start_y = logo_center_y + (text_block_height / 2)
    for i, hl in enumerate(header_lines):
        c.drawString(text_x, text_start_y - (i*line_spacing), hl)
    # Linha divisória sob o cabeçalho (abaixo do final do texto e do logo)
    text_bottom = text_start_y - text_block_height
    logo_bottom = header_top_y - logo_h if logo_h else text_bottom
    y = min(text_bottom, logo_bottom) - 12
    c.setLineWidth(0.6); c.line(50,y,w-50,y); y -= 20
    # Bloco informações básicas
    c.setFont('Helvetica-Bold',12)
    c.drawString(50,y, 'Resumo do Plantão'); y -= 18
    c.setFont('Helvetica',9)
    # Garantir que as datas sejam convertidas para timezone local antes de formatar
    # Normalizar Início/Encerrado usando timezone atual
    try:
        gerado_dt = timezone.localtime()
    except Exception:
        gerado_dt = timezone.now()
    tz_for_display = getattr(gerado_dt, 'tzinfo', None) or timezone.get_current_timezone()
    def _to_tz(dt):
        if not dt:
            return None
        try:
            # Se é naïve, tratar como estando na timezone de exibição (tz_for_display)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, tz_for_display)
            # Converte para a timezone de display
            return dt.astimezone(tz_for_display)
        except Exception:
            return dt
    inicio_dt = _to_tz(plantao.inicio)
    if inicio_dt:
        c.drawString(50,y, f"Início: {inicio_dt:%d/%m/%Y %H:%M}"); y -= 12
    encerrado_dt = _to_tz(plantao.encerrado_em)
    if encerrado_dt:
        c.drawString(50,y, f"Encerrado: {encerrado_dt:%d/%m/%Y %H:%M}"); y -= 12
    c.drawString(50,y, f"Equipe: {livro.equipe_plantao or '-'}"); y -= 18
    # Coordenador / Líder (CGA do dia)
    try:
        if getattr(livro, 'cga_do_dia', None):
            u = livro.cga_do_dia
            perfil = getattr(u, 'perfil', None)
            mat = getattr(perfil, 'matricula', '') if perfil else ''
            nome = (u.get_full_name() or u.username).strip()
            label = f"{mat+' - ' if mat else ''}{nome}" if nome else (mat or '-')
            c.drawString(50, y, f"Coordenador / Líder: {label}"); y -= 18
    except Exception:
        pass
    # Viaturas
    c.setFont('Helvetica-Bold',11); c.drawString(40,y,'Viaturas / Integrantes'); y -= 16; c.setFont('Helvetica',9)
    for v in livro.viaturas.select_related('viatura','integrante1','integrante2','integrante3','integrante4'):
        integrantes = [ _fmt_user_line(x) for x in v.integrantes() ] or ['(sem integrantes)']
        line = f"VTR {getattr(v.viatura,'prefixo','?')}: "+ ", ".join(integrantes)
        for part in _wrap(line, 95):
            if y < 80: c.showPage(); y = h-50; c.setFont('Helvetica',9)
            c.drawString(50,y,part); y -= 12
    # Postos Fixos
    c.setFont('Helvetica-Bold',11); c.drawString(40,y,'Postos Fixos'); y -= 16; c.setFont('Helvetica',9)
    for p in livro.postos_fixos.select_related('gcm1','gcm2'):
        g1 = _fmt_user_line(p.gcm1); g2 = _fmt_user_line(p.gcm2)
        desc = f"{p.get_tipo_display()}" + (f" ({p.descricao_outros})" if p.tipo=='OUTROS' and p.descricao_outros else '')
        line = f"{desc}: {g1}; {g2}" if (p.gcm1 or p.gcm2) else f"{desc}: (sem GCMs)"
        for part in _wrap(line, 95):
            if y < 80: c.showPage(); y = h-50; c.setFont('Helvetica',9)
            c.drawString(50,y,part); y -= 12
    # Anotações
    def bloco(titulo, texto):
        nonlocal y
        c.setFont('Helvetica-Bold',11); c.drawString(40,y,titulo); y-=14; c.setFont('Helvetica',9)
        if not texto.strip():
            c.drawString(50,y,'(sem registros)'); y-=12; return
        for part in _wrap(texto, 100):
            if y<80: c.showPage(); y=h-50; c.setFont('Helvetica',9)
            c.drawString(50,y,part); y-=12
        y-=6
    # Pessoas por categorias (usar registros estruturados se existirem; senão, cair para texto livre)
    def _lista_pessoas(tipo_code):
        try:
            itens = []
            qs = livro.pessoas.select_related('usuario__perfil').filter(tipo=tipo_code)
            for pp in qs:
                u = pp.usuario
                if not u:
                    continue
                perfil = getattr(u,'perfil',None)
                mat = getattr(perfil,'matricula','') if perfil else ''
                nome = (u.get_full_name() or u.username).strip()
                itens.append(f"{mat+' - ' if mat else ''}{nome}")
            return ", ".join(itens)
        except Exception:
            return ''
    def _lista_pessoas_com_tempo(tipo_code):
        try:
            linhas = []
            qs = livro.pessoas.select_related('usuario__perfil').filter(tipo=tipo_code)
            for pp in qs:
                u = pp.usuario
                if not u:
                    continue
                perfil = getattr(u,'perfil',None)
                mat = getattr(perfil,'matricula','') if perfil else ''
                nome = (u.get_full_name() or u.username).strip()
                base = f"{mat+' - ' if mat else ''}{nome}"
                if pp.hora_inicio and pp.hora_fim and (pp.total_minutos or 0) > 0:
                    hh = (pp.total_minutos or 0)//60; mm=(pp.total_minutos or 0)%60
                    base += f" — {pp.hora_inicio:%H:%M}-{pp.hora_fim:%H:%M} ({hh}h{mm:02d}m)"
                linhas.append(base)
            return "; ".join(linhas)
        except Exception:
            return ''
    disp_txt = _lista_pessoas('DISP') or (livro.dispensados or '')
    atraso_txt = _lista_pessoas_com_tempo('ATRASO') or (livro.atraso_servico or '')
    banco_txt = _lista_pessoas_com_tempo('BANCO') or (livro.banco_horas or '')
    hora_extra_txt = _lista_pessoas_com_tempo('HORA_EXTRA') or (livro.hora_extra or '')
    bloco('Dispensados', disp_txt)
    bloco('Atraso ao Serviço', atraso_txt)
    bloco('Banco de Horas', banco_txt)
    bloco('Hora Extra', hora_extra_txt)
    bloco('Ocorrências Não Atendidas', livro.ocorrencias_nao_atendidas)
    bloco('Ocorrências do Plantão', livro.ocorrencias_do_plantao)
    bloco("Observações", livro.observacoes)
    if y < 120: c.showPage(); y = h-50
    # Checklist
    c.setFont('Helvetica-Bold',11); c.drawString(40,y,'Checklist'); y-=16; c.setFont('Helvetica',9)
    itens = [
        ('Rádio', livro.chk_radio), ('Computador', livro.chk_computador), ('Câmeras', livro.chk_cameras),
        ('Celulares', livro.chk_celulares), ('Carregadores', livro.chk_carregadores), ('Telefones', livro.chk_telefones),
        ('Livros', livro.chk_livros), ('Monitor', livro.chk_monitor)
    ]
    for nome, val in itens:
        txt = f"[{'X' if val else ' '}] {nome}"
        if y < 80: c.showPage(); y = h-50; c.setFont('Helvetica',9)
        c.drawString(50,y,txt); y-=12
    # Assinatura do Operador (aux_cecom) com QR dentro de uma caixa (estilo relatório de plantão)
    operador = plantao.aux_cecom
    qr_token = None  # token único para verificação, gerado uma vez e reutilizado
    if operador:
        perfil_op = getattr(operador,'perfil',None)
        if perfil_op:
            # Força assinatura mais baixa para espaço de preenchimento, sem sobrepor conteúdo anterior
            if y > 250:
                y = 250  # empurra bloco para baixo caso tenha sobrado muito espaço
            y -= 30
            if y < 140: c.showPage(); y = h - 160
            # Dados do operador (vamos renderizar dentro da caixa de assinatura)
            nome_op = (operador.get_full_name() or operador.username).strip()
            cargo_op = getattr(perfil_op,'cargo','')
            mat_op = getattr(perfil_op,'matricula','')

            # Caixa estilo assinatura + QR (similar ao relatório de plantão)
            box_left = 50
            box_right = w - 50
            box_width = box_right - box_left
            box_height = 160
            if y - box_height < 60:
                c.showPage(); y = h - 80
            c.setLineWidth(0.5)
            c.roundRect(box_left, y - box_height, box_width, box_height, 6, stroke=1, fill=0)

            # Cabeçalho e dados do operador dentro da caixa (canto superior esquerdo)
            text_x = box_left + 12
            text_y = y - 20
            c.setFont('Helvetica-Bold',11); c.drawString(text_x, text_y, 'Operador do CECOM');
            text_y -= 14
            c.setFont('Helvetica',9)
            c.drawString(text_x, text_y, f"Nome: {nome_op}"); text_y -= 12
            if cargo_op:
                c.drawString(text_x, text_y, f"Cargo: {cargo_op}"); text_y -= 12
            if mat_op:
                c.drawString(text_x, text_y, f"Matrícula: {mat_op}"); text_y -= 12
            text_y -= 6  # espacinho entre dados e área de assinatura

            # Área da assinatura (esquerda)
            left_pad = 12
            sig_area_w = box_width * 0.60
            sig_x = box_left + left_pad
            # topo da área de assinatura respeitando o bloco de dados
            sig_y_top = min(y - 18, text_y)
            sig_y_bottom = y - box_height + 18

            # Desenhar imagem de assinatura se existir
            draw_w = draw_h = 0
            assinatura = getattr(perfil_op,'assinatura_img',None)
            assinatura_reader = None
            try:
                if assinatura and getattr(assinatura,'path',None):
                    from reportlab.lib.utils import ImageReader
                    assinatura_reader = ImageReader(assinatura.path)
                elif getattr(perfil_op,'assinatura_digital',None):
                    import base64, io
                    from reportlab.lib.utils import ImageReader
                    b64 = perfil_op.assinatura_digital.split(',')[-1].strip()
                    raw = base64.b64decode(b64)
                    assinatura_reader = ImageReader(io.BytesIO(raw))
            except Exception:
                assinatura_reader = None

            if assinatura_reader:
                # Tentar obter dimensões aproximadas (usar limites)
                max_w, max_h = sig_area_w - 60, max(40, (sig_y_top - sig_y_bottom) - 60)
                # fallback: desenhar com uma largura/hora padrão se não conseguirmos tamanho original
                try:
                    # Não é trivial obter dimensões do ImageReader; usamos tamanho alvo diretamente
                    draw_w = max_w
                    draw_h = min(60, max_h)
                except Exception:
                    draw_w = max_w; draw_h = min(60, max_h)
                draw_x = sig_x + (sig_area_w - draw_w) / 2
                draw_y = sig_y_bottom + ((sig_y_top - sig_y_bottom) - draw_h) / 2 + 6
                c.drawImage(assinatura_reader, draw_x, draw_y, width=draw_w, height=draw_h, mask='auto')

            # Linha de assinatura centralizada
            line_y = y - box_height + 26
            line_len = max(180, min(sig_area_w - 80, (draw_w or 200) + 60))
            line_x1 = sig_x + (sig_area_w - line_len) / 2
            line_x2 = line_x1 + line_len
            c.line(line_x1, line_y, line_x2, line_y)
            c.setFont('Helvetica',8)
            c.drawString(line_x1, line_y - 12, 'Assinatura')

            # Área do QR (direita) — alinhado e com token visível (igual aos demais docs)
            qr_pad = 12
            QR_W = 108
            qr_x = box_left + sig_area_w + qr_pad
            qr_y = y - box_height + (box_height - QR_W) / 2 + 8
            try:
                import qrcode, io as _io
                # URL de verificação com token único
                from django.conf import settings as _s
                if not qr_token:
                    now_ts = int(timezone.now().timestamp())
                    raw = f"livro:{plantao.id}|ts:{now_ts}|secret:{getattr(_s,'SECRET_KEY','gcm')}".encode('utf-8')
                    qr_token = hashlib.sha256(raw).hexdigest()[:32]
                # Construir base URL (tenta SITE_BASE_URL; senão primeira origem confiável não-local; senão localhost)
                base = getattr(_s, 'SITE_BASE_URL', '') or ''
                if not base:
                    origins = [o for o in getattr(_s, 'CSRF_TRUSTED_ORIGINS', []) if o.startswith('http')]
                    prefer = [o for o in origins if '127.0.0.1' not in o and 'localhost' not in o]
                    base = (prefer[0] if prefer else (origins[0] if origins else 'http://localhost:8000')).rstrip('/')
                verify_url = f"{base}/cecom/relatorios-livro/verificar/{qr_token}/"
                img = qrcode.make(verify_url)
                buf = _io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
                from reportlab.lib.utils import ImageReader as _IR
                c.drawImage(_IR(buf), qr_x, qr_y, width=QR_W, height=QR_W, mask='auto')
                # Legendinha de validação e token (duas linhas para não estourar)
                c.setFont('Helvetica',7); c.drawCentredString(qr_x + QR_W/2, qr_y - 10, 'Verificação Online')
                # Exibe token em duas linhas, 16+16 chars
                try:
                    tok_a = qr_token[:16]
                    tok_b = qr_token[16:]
                    c.setFont('Helvetica',6)
                    c.drawCentredString(qr_x + QR_W/2, qr_y - 22, f"Token: {tok_a}")
                    c.drawCentredString(qr_x + QR_W/2, qr_y - 32, tok_b)
                except Exception:
                    pass
            except Exception:
                pass

            # Avançar Y após a caixa
            y = y - box_height - 20
    c.showPage(); c.save()
    pdf_bytes = buffer.getvalue()
    from django.core.files.base import ContentFile
    perfil_cga = getattr(livro.cga_do_dia,'perfil',None)
    rel = LivroPlantaoCecomRelatorio(
        plantao=plantao,
        equipe_plantao=livro.equipe_plantao or '',
        cga_nome=(livro.cga_do_dia.get_full_name() or livro.cga_do_dia.username) if livro.cga_do_dia else '',
        cga_matricula=getattr(perfil_cga,'matricula','') if perfil_cga else ''
    )
    # Definir token antes do primeiro save para evitar colisão de UNIQUE com valor vazio
    try:
        if not qr_token:
            from django.conf import settings as _s
            raw2 = f"livro:{plantao.id}|ts:{int(timezone.now().timestamp())}|secret:{getattr(_s,'SECRET_KEY','gcm')}".encode('utf-8')
            qr_token = hashlib.sha256(raw2).hexdigest()[:32]
        rel.verificacao_token = qr_token
    except Exception:
        pass
    nome_arquivo = f"livro_cecom_{plantao.id}_{timezone.localtime(plantao.inicio):%Y%m%d}.pdf"
    rel.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=True)
    # Preencher token de verificação (reforço), se por algum motivo não ficou salvo acima
    try:
        if not getattr(rel, 'verificacao_token', None):
            if qr_token:
                rel.verificacao_token = qr_token
            else:
                from django.conf import settings as _s
                raw2 = f"livro:{plantao.id}|ts:{int(timezone.now().timestamp())}|secret:{getattr(_s,'SECRET_KEY','gcm')}".encode('utf-8')
                rel.verificacao_token = hashlib.sha256(raw2).hexdigest()[:32]
        rel.save(update_fields=['verificacao_token'])
    except Exception:
        pass
    # Registrar também como DocumentoAssinavel para fluxo de assinatura do Administrativo
    try:
        from common.models import DocumentoAssinavel
        if not DocumentoAssinavel.objects.filter(arquivo__icontains=nome_arquivo, tipo='LIVRO_CECOM').exists():
            from django.core.files.base import File
            # Precisamos reabrir o arquivo salvo em rel.arquivo
            with rel.arquivo.open('rb') as fpdf:
                doc = DocumentoAssinavel(
                    tipo='LIVRO_CECOM',
                    usuario_origem=plantao.usuario,
                    encarregado_assinou=True,
                    status='PENDENTE_ADM'
                )
                doc.arquivo.save(nome_arquivo, File(fpdf), save=True)
    except Exception:
        pass


def _wrap(texto, largura):
    # simples quebra de linha
    import textwrap
    return textwrap.wrap(texto, largura) if texto else []


@login_required
def relatorios_livro(request):
    qs = LivroPlantaoCecomRelatorio.objects.select_related('plantao').all()
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'cecom/relatorios_livro.html', {'page': page})


@login_required
def relatorio_livro_download(request, rid: int):
    rel = get_object_or_404(LivroPlantaoCecomRelatorio.objects.select_related('plantao'), pk=rid)
    if not rel.arquivo:
        return JsonResponse({'erro':'Arquivo inexistente'}, status=404)
    from django.http import FileResponse
    response = FileResponse(rel.arquivo.open('rb'), as_attachment=True, filename=rel.arquivo.name.split('/')[-1])
    return response


@login_required
def relatorio_livro_excluir(request, rid: int):
    if request.method != 'POST':
        return JsonResponse({'erro':'Método não permitido'}, status=405)
    rel = get_object_or_404(LivroPlantaoCecomRelatorio, pk=rid)
    # Apenas superuser username=moises
    if not (request.user.is_superuser and request.user.username == 'moises'):
        return JsonResponse({'erro':'Sem permissão'}, status=403)
    try:
        storage_file = rel.arquivo
        nome = storage_file.name
        rel.delete()
        try:
            storage_file.storage.delete(nome)
        except Exception:
            pass
        messages.success(request, 'Relatório excluído.')
    except Exception as e:
        messages.error(request, f'Erro ao excluir: {e}')
    return redirect('cecom:relatorios_livro')


@login_required
def livro_cecom(request, pk):
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    # Modo somente leitura para quem não é iniciador nem superadmin 'moises'
    is_editor = (plantao.usuario_id == request.user.id) or (request.user.username == 'moises' and request.user.is_superuser)
    livro, _ = LivroPlantaoCecom.objects.get_or_create(plantao=plantao)
    if request.method == 'POST':
        if not is_editor:
            from django.contrib import messages
            messages.error(request, 'Você não pode editar este livro. (Somente leitura)')
            return redirect('cecom:livro_cecom', pk=plantao.pk)
        form = LivroPlantaoCecomForm(request.POST, instance=livro, request_user=request.user)
        if form.is_valid():
            form.save()
            # Resposta JSON para AJAX
            if request.headers.get('X-Requested-With') in ('XMLHttpRequest','Fetch'):
                return JsonResponse({'sucesso': True, 'mensagem': 'Dados salvos com sucesso.'})
            messages.success(request, 'Dados salvos com sucesso.')
            # Após salvar pelo submit normal, voltar ao painel do CECOM
            return redirect('cecom:painel')
        else:
            if request.headers.get('X-Requested-With') in ('XMLHttpRequest','Fetch'):
                return JsonResponse({'sucesso': False, 'erros': form.errors}, status=400)
    else:
        form = LivroPlantaoCecomForm(instance=livro, request_user=request.user)
    # Se readonly, desabilita campos
    if not is_editor:
        for f in form.fields.values():
            f.widget.attrs['disabled'] = 'disabled'
    viatura_form = LivroPlantaoCecomViaturaForm()
    posto_form = LivroPlantaoCecomPostoFixoForm()
    viaturas_qs = livro.viaturas.select_related(
        'viatura', 'integrante1__perfil','integrante2__perfil','integrante3__perfil','integrante4__perfil'
    ).all()
    postos_qs = livro.postos_fixos.select_related('gcm1__perfil','gcm2__perfil').all()
    pessoas_qs = livro.pessoas.select_related('usuario__perfil').all()

    def _fmt_user(u):
        if not u:
            return None
        perfil = getattr(u, 'perfil', None)
        matricula = getattr(perfil, 'matricula', '') if perfil else ''
        return {
            'nome': (u.get_full_name() or u.username),
            'matricula': matricula or u.username
        }
    initial_viaturas = []
    for v in viaturas_qs:
        initial_viaturas.append({
            'id': v.id,
            'viatura': getattr(v.viatura, 'prefixo', ''),
            'integrantes': [i for i in [_fmt_user(v.integrante1), _fmt_user(v.integrante2), _fmt_user(v.integrante3), _fmt_user(v.integrante4)] if i]
        })
    initial_postos = []
    for p in postos_qs:
        initial_postos.append({
            'id': p.id,
            'tipo': p.get_tipo_display(),
            'descricao_outros': p.descricao_outros,
            'gcm1': _fmt_user(p.gcm1),
            'gcm2': _fmt_user(p.gcm2)
        })

    # Pessoas por tipo
    def _fmt_pessoa(pp):
        u = getattr(pp, 'usuario', None)
        if not u:
            return None
        perfil = getattr(u, 'perfil', None)
        mat = getattr(perfil, 'matricula', '') if perfil else ''
        return {
            'id': pp.id,
            'nome': (u.get_full_name() or u.username),
            'matricula': mat or u.username,
            'tipo': pp.tipo,
            'inicio': pp.hora_inicio.strftime('%H:%M') if getattr(pp, 'hora_inicio', None) else '',
            'fim': pp.hora_fim.strftime('%H:%M') if getattr(pp, 'hora_fim', None) else '',
            'total_minutos': pp.total_minutos or 0,
        }
    initial_pessoas = {
        'DISP': [], 'ATRASO': [], 'BANCO': [], 'HORA_EXTRA': []
    }
    for pp in pessoas_qs:
        d = _fmt_pessoa(pp)
        if d:
            initial_pessoas.setdefault(pp.tipo, []).append(d)

    # CGA inicial para UI
    initial_cga = None
    try:
        u = getattr(livro, 'cga_do_dia', None)
        if u:
            perfil = getattr(u, 'perfil', None)
            mat = getattr(perfil, 'matricula', '') if perfil else ''
            initial_cga = {
                'id': u.id,
                'nome': (u.get_full_name() or u.username),
                'matricula': mat or u.username
            }
    except Exception:
        initial_cga = None

    return render(request, 'cecom/livro_cecom.html', {
        'plantao': plantao,
        'livro': livro,
        'form': form,
        'viatura_form': viatura_form,
        'posto_form': posto_form,
        'initial_viaturas_json': json.dumps(initial_viaturas, ensure_ascii=False),
        'initial_postos_json': json.dumps(initial_postos, ensure_ascii=False),
        'initial_pessoas_json': json.dumps(initial_pessoas, ensure_ascii=False),
        'initial_cga_json': json.dumps(initial_cga or {}, ensure_ascii=False),
        'livro_readonly': not is_editor,
    })


@login_required
def livro_cecom_set_cga(request, pk):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    # Apenas o iniciador ou superadmin 'moises'
    if not ((plantao.usuario_id == request.user.id) or (request.user.username == 'moises' and request.user.is_superuser)):
        return JsonResponse({'erro': 'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    # Não permitir múltiplos (se já tem, precisa remover antes)
    if livro.cga_do_dia_id:
        return JsonResponse({'erro': 'Já existe um CGA definido. Remova para trocar.'}, status=400)
    uid = request.POST.get('usuario')
    if not uid:
        return JsonResponse({'erro': 'Usuário inválido'}, status=400)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        u = User.objects.select_related('perfil').get(pk=uid, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'erro': 'Usuário inválido'}, status=400)
    livro.cga_do_dia = u
    livro.save(update_fields=['cga_do_dia', 'atualizado_em'])
    perfil = getattr(u, 'perfil', None)
    mat = getattr(perfil, 'matricula', '') if perfil else ''
    return JsonResponse({'sucesso': True, 'id': u.id, 'nome': (u.get_full_name() or u.username), 'matricula': mat or u.username})


@login_required
def livro_cecom_clear_cga(request, pk):
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if not ((plantao.usuario_id == request.user.id) or (request.user.username == 'moises' and request.user.is_superuser)):
        return JsonResponse({'erro': 'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    livro.cga_do_dia = None
    livro.save(update_fields=['cga_do_dia', 'atualizado_em'])
    return JsonResponse({'sucesso': True})


@login_required
def livro_cecom_add_viatura(request, pk):
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    form = LivroPlantaoCecomViaturaForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.livro = livro
        obj.save()
        integrantes_fmt = []
        for u in obj.integrantes():
            perfil = getattr(u,'perfil',None)
            matricula = getattr(perfil,'matricula','') if perfil else ''
            integrantes_fmt.append({'nome': (u.get_full_name() or u.username), 'matricula': matricula or u.username})
        return JsonResponse({
            'sucesso':True,
            'id':obj.id,
            'viatura': getattr(obj.viatura,'prefixo',''),
            'integrantes': integrantes_fmt,
        })
    return JsonResponse({'erro':'Dados inválidos'}, status=400)


@login_required
def livro_cecom_del_viatura(request, pk, vid):
    if request.method != 'POST':
        return JsonResponse({'erro':'Método não permitido'}, status=405)
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    try:
        obj = livro.viaturas.get(id=vid)
        obj.delete()
        return JsonResponse({'sucesso': True, 'id': vid})
    except LivroPlantaoCecomViatura.DoesNotExist:
        return JsonResponse({'erro': 'Registro não encontrado'}, status=404)


@login_required
def livro_cecom_add_posto(request, pk):
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    form = LivroPlantaoCecomPostoFixoForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.livro = livro
        obj.save()
        def fmt(u):
            if not u: return None
            perfil = getattr(u,'perfil',None)
            matricula = getattr(perfil,'matricula','') if perfil else ''
            return {'nome': (u.get_full_name() or u.username), 'matricula': matricula or u.username}
        return JsonResponse({
            'sucesso':True,
            'id':obj.id,
            'tipo': obj.get_tipo_display(),
            'descricao_outros': obj.descricao_outros,
            'gcm1': fmt(obj.gcm1),
            'gcm2': fmt(obj.gcm2),
        })
    return JsonResponse({'erro':'Dados inválidos'}, status=400)


@login_required
def livro_cecom_del_posto(request, pk, pid):
    if request.method != 'POST':
        return JsonResponse({'erro':'Método não permitido'}, status=405)
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    try:
        obj = livro.postos_fixos.get(id=pid)
        obj.delete()
        return JsonResponse({'sucesso': True, 'id': pid})
    except LivroPlantaoCecomPostoFixo.DoesNotExist:
        return JsonResponse({'erro': 'Registro não encontrado'}, status=404)


@login_required
def livro_cecom_add_pessoa(request, pk):
    """Adiciona pessoa em uma das listas (Dispensados, Atraso, Banco, Hora Extra)."""
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    tipo = request.POST.get('tipo')
    usuario_id = request.POST.get('usuario')
    inicio_txt = (request.POST.get('inicio') or '').strip()
    fim_txt = (request.POST.get('fim') or '').strip()
    validos = dict(LivroPlantaoCecomPessoa.TIPO_CHOICES).keys()
    if tipo not in validos:
        return JsonResponse({'erro':'Tipo inválido'}, status=400)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        u = User.objects.select_related('perfil').get(pk=usuario_id)
    except User.DoesNotExist:
        return JsonResponse({'erro':'Usuário inválido'}, status=400)
    # Validar horários quando necessário
    from datetime import datetime, timedelta
    inicio_time = fim_time = None
    total_min = None
    if tipo in ('ATRASO','BANCO','HORA_EXTRA'):
        if not (inicio_txt and fim_txt):
            return JsonResponse({'erro':'Informe horário inicial e final'}, status=400)
        try:
            inicio_time = datetime.strptime(inicio_txt, '%H:%M').time()
            fim_time = datetime.strptime(fim_txt, '%H:%M').time()
            # calcular diferença (considera cruzar meia-noite)
            dt0 = datetime.combine(datetime.today(), inicio_time)
            dt1 = datetime.combine(datetime.today(), fim_time)
            if dt1 < dt0:
                dt1 += timedelta(days=1)
            total_min = int((dt1 - dt0).total_seconds() // 60)
            if total_min < 0:
                total_min = 0
        except Exception:
            return JsonResponse({'erro':'Horário inválido'}, status=400)
    try:
        obj, created = LivroPlantaoCecomPessoa.objects.get_or_create(livro=livro, tipo=tipo, usuario=u, defaults={
            'hora_inicio': inicio_time,
            'hora_fim': fim_time,
            'total_minutos': total_min,
        })
        if not created:
            # Atualiza horários se fornecidos
            if inicio_time or fim_time or total_min is not None:
                obj.hora_inicio = inicio_time
                obj.hora_fim = fim_time
                obj.total_minutos = total_min
                obj.save(update_fields=['hora_inicio','hora_fim','total_minutos'])
    except Exception as e:
        return JsonResponse({'erro': f'Erro ao adicionar: {e}'}, status=400)
    perfil = getattr(u, 'perfil', None)
    mat = getattr(perfil, 'matricula', '') if perfil else ''
    # Formatar hh:mm
    inicio_out = obj.hora_inicio.strftime('%H:%M') if obj.hora_inicio else ''
    fim_out = obj.hora_fim.strftime('%H:%M') if obj.hora_fim else ''
    tot_min = obj.total_minutos or 0
    hh = tot_min // 60; mm = tot_min % 60
    total_fmt = (f"{hh}h{mm:02d}m" if tot_min else '')
    return JsonResponse({'sucesso': True, 'id': obj.id, 'nome': (u.get_full_name() or u.username), 'matricula': mat or u.username, 'tipo': tipo, 'inicio': inicio_out, 'fim': fim_out, 'total_minutos': tot_min, 'total_fmt': total_fmt})


@login_required
def livro_cecom_del_pessoa(request, pk, pid):
    if request.method != 'POST':
        return JsonResponse({'erro':'Método não permitido'}, status=405)
    plantao = get_object_or_404(PlantaoCecomPrincipal, pk=pk)
    if plantao.usuario_id != request.user.id and plantao.aux_cecom_id != request.user.id:
        return JsonResponse({'erro':'Sem acesso'}, status=403)
    livro = get_object_or_404(LivroPlantaoCecom, plantao=plantao)
    try:
        obj = livro.pessoas.get(id=pid)
        obj.delete()
        return JsonResponse({'sucesso': True, 'id': pid})
    except LivroPlantaoCecomPessoa.DoesNotExist:
        return JsonResponse({'erro': 'Registro não encontrado'}, status=404)


@login_required
def despachar_ocorrencia(request):
    """
    Formulário para despachar nova ocorrência para viatura.
    """
    if request.method == "POST":
        form = DespachoOcorrenciaForm(request.POST)
        if form.is_valid():
            despacho = form.save(commit=False)
            despacho.despachado_por = request.user
            despacho.save()
            # Enviar notificação aos integrantes da viatura ativa
            try:
                _notificar_despacho_para_viatura(despacho)
            except Exception:
                # Não interromper o fluxo caso FCM não esteja configurado
                pass
            
            messages.success(request, f"Ocorrência despachada para {despacho.viatura}")
            return redirect("cecom:painel")
    else:
        form = DespachoOcorrenciaForm()
    
    return render(request, "cecom/despachar.html", {"form": form})


def _notificar_despacho_para_viatura(despacho: DespachoOcorrencia) -> int:
    """Envia push de 'Nova Ocorrência' para os usuários do plantão ativo da viatura.

    - Busca PlantaoCECOM ativo com a viatura do despacho e coleta participantes (atuais) + iniciador.
    - Obtém tokens de PushDevice habilitados desses usuários.
    - Envia via FCM (common.views.enviar_push). Em caso de erro de configuração, ignora silenciosamente.
    - Marca `notificado_em` no despacho.

    Retorna o número de entregas relatadas como sucesso pelo FCM (quando possível).
    """
    if not despacho or not getattr(despacho, 'viatura_id', None):
        return 0
    # Plantão ativo vinculado à viatura
    pl = (
        PlantaoCECOM.objects
        .filter(ativo=True, viatura_id=despacho.viatura_id)
        .order_by('-inicio')
        .first()
    )
    if not pl:
        return 0
    # Usuários-alvo: participantes atuais + quem iniciou (se ainda presente)
    participantes_qs = pl.participantes.filter(saida_em__isnull=True).select_related('usuario')
    users = [p.usuario for p in participantes_qs if getattr(p, 'usuario', None)]
    if pl.iniciado_por and pl.iniciado_por not in users:
        users.append(pl.iniciado_por)
    if not users:
        return 0
    user_ids = [u.id for u in users if getattr(u, 'id', None)]
    tokens = list(
        PushDevice.objects.filter(user_id__in=user_ids, enabled=True)
        .values_list('token', flat=True)
    )
    if not tokens:
        # Mesmo sem tokens, marca como notificado para evitar reenvio em loop
        if not despacho.notificado_em:
            despacho.notificado_em = timezone.now()
            despacho.save(update_fields=['notificado_em'])
        return 0
    title_extra = ''
    if getattr(despacho, 'cod_natureza', ''):
        title_extra = f" / {despacho.cod_natureza}"
    title = f"CECOM - Nova Ocorrência (VTR {getattr(despacho.viatura, 'prefixo', '')}{title_extra})"
    resumo = (despacho.endereco or '').strip()
    body = resumo[:120] or (despacho.descricao[:120] if despacho.descricao else 'Ocorrência despachada')
    data = {
        'kind': 'despacho',
        'despacho_id': str(despacho.pk),
        'viatura_id': str(despacho.viatura_id),
        'viatura': getattr(despacho.viatura, 'prefixo', ''),
        'endereco': despacho.endereco,
        'status': despacho.status,
        'cod_natureza': getattr(despacho, 'cod_natureza', ''),
        'natureza': getattr(despacho, 'natureza', ''),
    }
    sent = 0
    try:
        sent = enviar_push(tokens, title=title, body=body, data=data)
    except Exception:
        sent = 0
    # Marca como notificado (independente do count reportado)
    if not despacho.notificado_em:
        despacho.notificado_em = timezone.now()
        despacho.save(update_fields=['notificado_em'])
    return sent


@login_required
def despachos_lista(request):
    """
    Lista todos os despachos ativos (não arquivados) com paginação.
    """
    # Normalização: converter qualquer registro legado ACEITO para EM_ANDAMENTO
    from django.db import transaction
    try:
        with transaction.atomic():
            DespachoOcorrencia.objects.filter(status="ACEITO").update(status="EM_ANDAMENTO")
    except Exception:
        pass
    despachos = DespachoOcorrencia.objects.select_related("viatura", "despachado_por").filter(
        arquivado=False
    ).order_by("-despachado_em")
    
    paginator = Paginator(despachos, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    return render(request, "cecom/despachos.html", {"page_obj": page_obj})


@login_required
def despachos_arquivados(request):
    """
    Lista todos os despachos arquivados com paginação de 15 itens.
    """
    despachos_arquivados = DespachoOcorrencia.objects.select_related(
        "viatura", "despachado_por", "respondido_por"
    ).filter(
        arquivado=True
    ).order_by("-arquivado_em", "-despachado_em")
    
    # Filtros opcionais
    status_filtro = request.GET.get('status')
    periodo_filtro = request.GET.get('periodo')
    
    if status_filtro:
        despachos_arquivados = despachos_arquivados.filter(status=status_filtro)
    
    if periodo_filtro:
        from datetime import timedelta
        hoje = timezone.now().date()
        
        if periodo_filtro == 'hoje':
            despachos_arquivados = despachos_arquivados.filter(arquivado_em__date=hoje)
        elif periodo_filtro == 'semana':
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            despachos_arquivados = despachos_arquivados.filter(arquivado_em__date__gte=inicio_semana)
        elif periodo_filtro == 'mes':
            inicio_mes = hoje.replace(day=1)
            despachos_arquivados = despachos_arquivados.filter(arquivado_em__date__gte=inicio_mes)
    
    paginator = Paginator(despachos_arquivados, 15)  # 15 por página conforme solicitado
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    return render(request, "cecom/despachos_arquivados.html", {
        "page_obj": page_obj,
        "status_filtro": status_filtro,
        "periodo_filtro": periodo_filtro
    })


@login_required
def despachos_excluir(request, pk=None):
    """
    Excluir despachos arquivados.
    Apenas o usuário 'moises' tem permissão.
    Se pk é fornecido, exclui um despacho específico.
    Se pk é None, exclui TODOS os despachos arquivados.
    """
    # Verificar permissão
    if request.user.username != "moises":
        messages.error(request, "Você não tem permissão para excluir despachos.")
        return redirect("cecom:despachos_arquivados")
    
    if request.method != "POST":
        messages.error(request, "Método não permitido.")
        return redirect("cecom:despachos_arquivados")
    
    try:
        if pk:
            # Excluir despacho específico
            despacho = get_object_or_404(DespachoOcorrencia, pk=pk, arquivado=True)
            despacho.delete()
            messages.success(request, f"Despacho #{pk} excluído com sucesso.")
        else:
            # Excluir TODOS os despachos arquivados
            count = DespachoOcorrencia.objects.filter(arquivado=True).count()
            DespachoOcorrencia.objects.filter(arquivado=True).delete()
            messages.success(request, f"Todos os {count} despachos arquivados foram excluídos com sucesso.")
    except Exception as e:
        messages.error(request, f"Erro ao excluir despacho(s): {str(e)}")
    
    return redirect("cecom:despachos_arquivados")


@login_required
def despacho_atualizar_status(request, pk):
    """
    Atualizar status de um despacho.
    """
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido"}, status=405)
        
    despacho = get_object_or_404(DespachoOcorrencia, pk=pk)
    novo_status = request.POST.get("status")
    
    if novo_status in dict(DespachoOcorrencia.STATUS_CHOICES):
        # Regra: ao aceitar vai direto para EM_ANDAMENTO
        if novo_status == "ACEITO":
            if not despacho.aceito_em:
                despacho.aceito_em = timezone.now()
            despacho.status = "EM_ANDAMENTO"
        else:
            despacho.status = novo_status
            if novo_status == "FINALIZADO" and not despacho.finalizado_em:
                despacho.finalizado_em = timezone.now()
        despacho.save()
        return JsonResponse({"sucesso": True, "status": despacho.get_status_display(), "codigo_status": despacho.status})
    
    return JsonResponse({"erro": "Status inválido"}, status=400)


@login_required
def despacho_finalizar(request, pk):
    """
    Finalizar um despacho com observações opcionais.
    """
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido"}, status=405)
    
    despacho = get_object_or_404(DespachoOcorrencia, pk=pk)
    observacoes = request.POST.get("observacoes", "")
    
    despacho.finalizar(observacoes)
    
    return JsonResponse({
        "sucesso": True, 
        "mensagem": "Despacho finalizado com sucesso",
        "status": despacho.get_status_display()
    })


def verificar_relatorio_livro(request, token: str):
    """Página de verificação pública do relatório do Livro CECOM via token do QR.

    Exibe status OK quando o token existe, com metadados e hash para conferência.
    """
    try:
        rel = LivroPlantaoCecomRelatorio.objects.select_related('plantao').get(verificacao_token=token)
        status = 'OK'
        dt = timezone.localtime(rel.criado_em)
        plantao = rel.plantao
        aux = getattr(plantao, 'aux_cecom', None)
        ctx = {
            'status': status,
            'token': token,
            'plantao_id': plantao.id,
            'criado_em': dt,
            'operador_nome': (aux.get_full_name() or aux.username) if aux else '-',
            'operador_matricula': getattr(getattr(aux, 'perfil', None), 'matricula', '') if aux else '',
        }
        return render(request, 'cecom/verify_relatorio.html', ctx)
    except LivroPlantaoCecomRelatorio.DoesNotExist:
        return render(request, 'cecom/verify_relatorio.html', {
            'status': 'NÃO ENCONTRADO', 'token': token, 'plantao_id': None, 'criado_em': None,
            'operador_nome': '-', 'operador_matricula': ''
        }, status=404)


@login_required
def despacho_arquivar(request, pk):
    """
    Arquivar um despacho finalizado.
    """
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido"}, status=405)
    
    despacho = get_object_or_404(DespachoOcorrencia, pk=pk)
    
    if not despacho.pode_ser_arquivado:
        return JsonResponse({
            "sucesso": False,
            "erro": "Este despacho não pode ser arquivado no momento"
        })
    
    despacho.arquivar()
    
    return JsonResponse({
        "sucesso": True,
        "mensagem": "Despacho arquivado com sucesso"
    })


@login_required
def painel_viaturas(request):
    """
    Mantido por compatibilidade; redireciona para o novo painel.
    """
    return redirect("cecom:painel")


@login_required
def ativos_json(request):
    """
    API JSON com talões ativos para atualizações em tempo real.
    """
    data = []
    for t in _taloes_abertos():
        vtr = getattr(t, "viatura", None)
        cod = getattr(t, "codigo_ocorrencia", None)
        
        # Informações da equipe
        equipe_info = []
        if hasattr(t, 'encarregado') and t.encarregado:
            equipe_info.append(f"Enc: {t.encarregado.get_full_name() or t.encarregado.username}")
        if hasattr(t, 'motorista') and t.motorista:
            equipe_info.append(f"Mot: {t.motorista.get_full_name() or t.motorista.username}")
            
        data.append({
            "talao_id": t.pk,
            "status": t.status,
            "iniciado_em": t.iniciado_em.isoformat() if t.iniciado_em else None,
            "km_inicial": t.km_inicial,
            "km_final": t.km_final,
            "viatura_id": getattr(t, "viatura_id", None),
            "viatura_prefixo": getattr(vtr, "prefixo", None),
            "viatura_placa": getattr(vtr, "placa", None),
            "codigo": getattr(cod, "sigla", None),
            "descricao": getattr(cod, "descricao", None),
            "local_bairro": getattr(t, "local_bairro", None),
            "local_rua": getattr(t, "local_rua", None),
            "equipe": " | ".join(equipe_info) if equipe_info else "N/I",
        })
    
    # Contar apenas despachos pendentes (não respondidos) para alertas
    despachos_pendentes_count = DespachoOcorrencia.objects.filter(
        status='PENDENTE',
        respondido_em__isnull=True,
        arquivado=False
    ).count()
    
    # Contar total de despachos recentes para estatísticas
    despachos_count = DespachoOcorrencia.objects.filter(
        despachado_em__gte=timezone.now() - timezone.timedelta(hours=24),
        arquivado=False
    ).count()
    
    # Contar alertas de pânico abertos
    from panic.models import DisparoPanico
    panico_abertos_count = DisparoPanico.objects.filter(
        status__in=['ABERTA', 'EM_ATENDIMENTO']
    ).count()
    
    # Plantoes ativos (para detectar início e vincular avarias)
    hoje = timezone.localdate()
    pl_ativos = PlantaoCECOM.objects.select_related('viatura').filter(ativo=True, viatura__isnull=False)
    pl_list = [
        {
            'id': p.id,
            'viatura_id': p.viatura_id,
            'viatura_prefixo': getattr(p.viatura, 'prefixo', ''),
            'inicio': timezone.localtime(p.inicio).isoformat() if p.inicio else None,
        }
        for p in pl_ativos
    ]
    # Avarias por viatura para os plantoes ativos (estado persistente)
    avarias_by_viatura: dict[int, list[str]] = {}
    try:
        from viaturas.models import ViaturaAvariaEstado
        v_ids = [p['viatura_id'] for p in pl_list]
        estados = {e.viatura_id: e.get_labels() for e in ViaturaAvariaEstado.objects.filter(viatura_id__in=v_ids)}
        avarias_by_viatura.update({vid: (labels or []) for vid, labels in estados.items()})
    except Exception:
        pass

    return JsonResponse({
        "agora": timezone.localtime().isoformat(), 
        "ativos": data,
        "despachos_count": despachos_count,
        "despachos_pendentes_count": despachos_pendentes_count,
        "panico_abertos_count": panico_abertos_count,
        "plantoes": pl_list,
        "avarias": [
            {
                'viatura_id': vid,
                'viatura_prefixo': getattr(next((p for p in pl_ativos if p.viatura_id == vid), None), 'viatura', None).prefixo if next((p for p in pl_ativos if p.viatura_id == vid), None) else '',
                'itens': itens
            }
            for vid, itens in avarias_by_viatura.items()
        ]
    })


# ---------------- Localização em tempo real das Viaturas ----------------

@login_required
def mapa_viaturas(request):
    """Página com mapa e posições das viaturas ativas."""
    return render(request, 'cecom/mapa_viaturas.html', {})


@login_required
@csrf_exempt
def localizacao_post(request):
    """Recebe ping de localização do app.

    Regras:
    - Usuário deve ter plantão ativo (iniciado ou participante) e estar vinculado a uma viatura
      via PlantaoCECOM.viatura.
    - Atualiza/Cria ViaturaLocalizacao daquela viatura.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST.dict()

    lat = body.get('latitude')
    lng = body.get('longitude')
    precisao = body.get('precisao') or body.get('accuracy')
    vel = body.get('velocidade') or body.get('speed')
    dirg = body.get('direcao') or body.get('heading')

    if lat is None or lng is None:
        return JsonResponse({'erro': 'latitude e longitude são obrigatórias'}, status=400)

    # Verificar plantão ativo do usuário (iniciado ou participante)
    plantao = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
    if not plantao or not plantao.viatura_id or not plantao.ativo:
        return JsonResponse({'erro': 'Sem plantão ativo ou viatura vinculada'}, status=403)

    # Atualizar/criar localização
    try:
        obj, _ = ViaturaLocalizacao.objects.get_or_create(viatura_id=plantao.viatura_id, defaults={
            'latitude': lat,
            'longitude': lng,
        })
        # Atribuições convertendo quando possível
        obj.latitude = lat
        obj.longitude = lng
        obj.precisao_m = float(precisao) if precisao not in (None, '') else None
        obj.velocidade_kmh = float(vel) if vel not in (None, '') else None
        obj.direcao_graus = float(dirg) if dirg not in (None, '') else None
        obj.origem_usuario = request.user
        obj.origem_plantao = plantao
        obj.save()

        # Registrar ponto histórico (throttling: a cada 15s ou se deslocamento > ~15m)
        should_add = True
        last_pt = ViaturaLocalizacaoPonto.objects.filter(viatura_id=plantao.viatura_id).order_by('-capturado_em').first()
        if last_pt:
            dt_delta = timezone.now() - last_pt.capturado_em
            # Distância aproximada usando fórmula simplificada (graus -> metros) válido para pequenas diferenças
            try:
                from math import cos, radians, sqrt
                lat1 = float(last_pt.latitude); lon1 = float(last_pt.longitude)
                lat2 = float(lat); lon2 = float(lng)
                # Conversões aproximadas
                dx = (lon2 - lon1) * 111320 * cos(radians((lat1+lat2)/2))
                dy = (lat2 - lat1) * 110540
                dist_m = sqrt(dx*dx + dy*dy)
            except Exception:
                dist_m = 0
            if dt_delta.total_seconds() < 15 and dist_m < 15:
                should_add = False
        if should_add:
            ViaturaLocalizacaoPonto.objects.create(
                viatura_id=plantao.viatura_id,
                plantao=plantao,
                latitude=lat,
                longitude=lng,
                origem_usuario=request.user,
                precisao_m=obj.precisao_m,
            )
            # Manter apenas últimos 400 pontos por viatura (limpeza simples)
            qs_ids = list(ViaturaLocalizacaoPonto.objects.filter(viatura_id=plantao.viatura_id).order_by('-capturado_em').values_list('id', flat=True)[0:400])
            ViaturaLocalizacaoPonto.objects.filter(viatura_id=plantao.viatura_id).exclude(id__in=qs_ids).delete()

        return JsonResponse({'sucesso': True, 'atualizado_em': timezone.localtime(obj.atualizado_em).isoformat()})
    except Exception as e:
        return JsonResponse({'erro': f'Falha ao salvar localização: {e}'}, status=500)


@login_required
def localizacoes_ativas(request):
    """JSON com últimas localizações de viaturas com plantão ativo.

    Inclui prefixo, id da viatura e timestamp de atualização.
    """
    # Viaturas com plantão ativo
    ativos = PlantaoCECOM.objects.select_related('viatura').filter(ativo=True, viatura__isnull=False)
    v_ids = [p.viatura_id for p in ativos]

    locs = (
        ViaturaLocalizacao.objects
        .select_related('viatura')
        .filter(viatura_id__in=v_ids)
    )

    # Opcional: participantes/equipe pelo PlantaoCECOM
    equipe_map = {}
    for p in ativos.prefetch_related('participantes__usuario__perfil'):
        equipe = []
        for part in p.participantes.filter(saida_em__isnull=True).select_related('usuario__perfil'):
            u = part.usuario
            perfil = getattr(u, 'perfil', None)
            equipe.append({
                'nome': (u.get_full_name() or u.username).strip(),
                'matricula': getattr(perfil, 'matricula', '') if perfil else ''
            })
        equipe_map[p.viatura_id] = equipe

    data = []
    # Limites para trilha: últimos 30 minutos ou 120 pontos (o que vier primeiro)
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=30)
    for l in locs:
        v = l.viatura
        pontos_qs = ViaturaLocalizacaoPonto.objects.filter(viatura_id=v.id, capturado_em__gte=cutoff).order_by('-capturado_em')[:120]
        # Ordenar cronologicamente ascendente para polyline
        pts = [
            [float(p.latitude), float(p.longitude)]
            for p in reversed(list(pontos_qs))
        ]
        data.append({
            'viatura_id': v.id,
            'prefixo': getattr(v, 'prefixo', ''),
            'latitude': float(l.latitude),
            'longitude': float(l.longitude),
            'precisao_m': l.precisao_m,
            'velocidade_kmh': l.velocidade_kmh,
            'direcao_graus': l.direcao_graus,
            'atualizado_em': timezone.localtime(l.atualizado_em).isoformat(),
            'equipe': equipe_map.get(v.id, []),
            'trilha': pts,
            'tem_localizacao': True,
        })

    # Adicionar viaturas ativas que não possuem registro atual de localização
    localizadas_ids = {d['viatura_id'] for d in data}
    for p in ativos:
        if p.viatura_id and p.viatura_id not in localizadas_ids:
            v = p.viatura
            data.append({
                'viatura_id': v.id,
                'prefixo': getattr(v, 'prefixo', ''),
                'latitude': None,
                'longitude': None,
                'precisao_m': None,
                'velocidade_kmh': None,
                'direcao_graus': None,
                'atualizado_em': None,
                'equipe': equipe_map.get(v.id, []),
                'trilha': [],
                'tem_localizacao': False,
            })

    # Identificar viatura do usuário (assumindo primeiro plantão ativo do usuário com viatura)
    viatura_usuario_id = None
    try:
        user_pl = PlantaoCECOM.objects.filter(ativo=True, participantes__usuario=request.user, viatura__isnull=False).first()
        if user_pl and user_pl.viatura_id:
            viatura_usuario_id = user_pl.viatura_id
    except Exception:
        pass

    return JsonResponse({
        'agora': timezone.localtime().isoformat(),
        'viaturas': data,
        'viatura_usuario_id': viatura_usuario_id,
    })
