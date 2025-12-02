from __future__ import annotations
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponseForbidden, HttpRequest, JsonResponse, HttpResponse, FileResponse
from .models import DocumentoAssinavel, PushDevice
from django.utils import timezone
from django.core.files.base import File, ContentFile
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from PIL import Image
from reportlab.lib.utils import ImageReader
import importlib, shutil, subprocess, sys, os, tempfile, re, hashlib
from typing import Iterable, Optional, Union, List, Dict


def _is_comando(user) -> bool:
    """Verifica se o usuário tem permissão para acessar o sistema de comando"""
    if not user.is_authenticated:
        return False
    return (
        user.is_superuser or 
        user.username in ['comandante', 'subcomandante', 'administrativo']
    )


def comando_required(view):
    return user_passes_test(_is_comando)(view)


def healthz(request: HttpRequest):
    """Endpoint simples de saúde do backend para checagem do app mobile.

    Retorna 200 OK com JSON curto e informações mínimas.

    Inclui cabeçalhos CORS liberando leitura via fetch a partir do WebView
    (capacitor://localhost ou http://localhost) sem necessidade de ajustes
    globais de CORS no projeto.
    """
    resp = JsonResponse({
        'ok': True,
        'app': 'gcm',
        'time': timezone.now().isoformat(timespec='seconds'),
    })
    # CORS básico apenas para este endpoint (GET simples)
    resp['Access-Control-Allow-Origin'] = '*'
    resp['Cache-Control'] = 'no-store'
    return resp


@login_required
@comando_required
def documentos_pendentes(request: HttpRequest):
    """Lista TODOS os documentos pendentes (Ronda, BOGCM e Livro CECOM)."""
    q = (request.GET.get('q') or '').strip()
    qs = DocumentoAssinavel.objects.filter(
        (
            Q(status='PENDENTE') &
            Q(tipo__in=['PLANTAO', 'BOGCMI'])
        )
        |
        (
            Q(status='PENDENTE_ADM') &
            Q(tipo='LIVRO_CECOM')
        )
    )
    if q:
        qs = qs.filter(
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q)
        )
    qs = qs.select_related('usuario_origem').order_by('-created_at')
    pend_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status__in=['PENDENTE'], tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status__in=['PENDENTE'], tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status__in=['PENDENTE_ADM'], tipo='LIVRO_CECOM').count(),
    }
    paginator = Paginator(qs, 15)
    return render(request, 'common/documentos_pendentes.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'pend_counts': pend_counts,
    })


@login_required
@comando_required
def documentos_pendentes_ronda(request: HttpRequest):
    """Lista apenas Relatório de Plantão (Ronda) pendentes."""
    q = (request.GET.get('q') or '').strip()
    qs = DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='PLANTAO')
    if q:
        qs = qs.filter(
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q)
        )
    paginator = Paginator(qs.select_related('usuario_origem').order_by('-created_at'), 15)
    pend_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM').count(),
    }
    return render(request, 'common/documentos_pendentes_ronda.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'pend_counts': pend_counts,
    })


@login_required
@comando_required
def documentos_pendentes_bogcm(request: HttpRequest):
    """Lista apenas BOGCM pendentes."""
    q = (request.GET.get('q') or '').strip()
    qs = DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='BOGCMI')
    if q:
        qs = qs.filter(
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q)
        )
    paginator = Paginator(qs.select_related('usuario_origem').order_by('-created_at'), 15)
    pend_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM').count(),
    }
    return render(request, 'common/documentos_pendentes_bogcm.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'pend_counts': pend_counts,
    })

@login_required
@comando_required
def documentos_pendentes_livro(request: HttpRequest):
    q = (request.GET.get('q') or '').strip()
    qs = DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM')
    if q:
        qs = qs.filter(
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q)
        )
    paginator = Paginator(qs.select_related('usuario_origem').order_by('-created_at'), 15)
    pend_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='PENDENTE', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM').count(),
    }
    return render(request, 'common/documentos_pendentes_livro.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'pend_counts': pend_counts,
    })


@login_required
@comando_required
def documentos_assinados(request: HttpRequest):
    """Lista geral (tudo) ainda disponível se quiser visão completa."""
    q = (request.GET.get('q') or '').strip()
    # Incluir assinados do Livro (ASSINADO_ADM) também no 'Todos'
    docs = DocumentoAssinavel.objects.filter(Q(status='ASSINADO') | Q(status='ASSINADO_ADM'))
    if q:
        # Busca abrangente: ID, usuário, arquivo (origem/assinado), tipo, status e data criada (dd/mm[/aaaa])
        filters = (
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q) |
            Q(arquivo_assinado__icontains=q) |
            Q(tipo__icontains=q) |
            Q(status__icontains=q)
        )
        if q.isdigit():
            try:
                filters |= Q(pk=int(q))
            except Exception:
                pass
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", q)
        if m:
            from datetime import date
            dia = int(m.group(1)); mes = int(m.group(2)); ano = m.group(3)
            try:
                if ano:
                    d0 = date(int(ano), mes, dia)
                    filters |= Q(created_at__date=d0)
                else:
                    filters |= Q(created_at__day=dia, created_at__month=mes)
            except Exception:
                pass
        docs = docs.filter(filters)
    docs = docs.select_related('usuario_origem','comando_usuario').order_by('-created_at')
    assin_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='ASSINADO_ADM', tipo='LIVRO_CECOM').count(),
    }
    paginator = Paginator(docs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'common/documentos_assinados.html', {
        'page_obj': page_obj,
        'q': q,
        'assin_counts': assin_counts,
        'assin_total': docs.count(),
        'filtro_tipo': 'todos',
    })


@login_required
@comando_required
def documentos_assinados_ronda(request: HttpRequest):
    """Lista apenas documentos de Ronda assinados."""
    q = (request.GET.get('q') or '').strip()
    docs = DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='PLANTAO')
    if q:
        filters = (
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q) |
            Q(arquivo_assinado__icontains=q) |
            Q(tipo__icontains=q) |
            Q(status__icontains=q)
        )
        if q.isdigit():
            try:
                filters |= Q(pk=int(q))
            except Exception:
                pass
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", q)
        if m:
            from datetime import date
            dia = int(m.group(1)); mes = int(m.group(2)); ano = m.group(3)
            try:
                if ano:
                    d0 = date(int(ano), mes, dia)
                    filters |= Q(created_at__date=d0)
                else:
                    filters |= Q(created_at__day=dia, created_at__month=mes)
            except Exception:
                pass
        docs = docs.filter(filters)
    docs = docs.select_related('usuario_origem','comando_usuario').order_by('-created_at')
    assin_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='ASSINADO_ADM', tipo='LIVRO_CECOM').count(),
    }
    paginator = Paginator(docs, 15)
    return render(request, 'common/documentos_assinados.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'assin_counts': assin_counts,
        'filtro_tipo': 'ronda',
    })


@login_required
@comando_required
def documentos_assinados_bogcm(request: HttpRequest):
    """Lista apenas documentos BOGCM assinados."""
    q = (request.GET.get('q') or '').strip()
    docs = DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='BOGCMI')
    if q:
        filters = (
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q) |
            Q(arquivo_assinado__icontains=q) |
            Q(tipo__icontains=q) |
            Q(status__icontains=q)
        )
        if q.isdigit():
            try:
                filters |= Q(pk=int(q))
            except Exception:
                pass
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", q)
        if m:
            from datetime import date
            dia = int(m.group(1)); mes = int(m.group(2)); ano = m.group(3)
            try:
                if ano:
                    d0 = date(int(ano), mes, dia)
                    filters |= Q(created_at__date=d0)
                else:
                    filters |= Q(created_at__day=dia, created_at__month=mes)
            except Exception:
                pass
        docs = docs.filter(filters)
    docs = docs.select_related('usuario_origem','comando_usuario').order_by('-created_at')
    assin_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='ASSINADO_ADM', tipo='LIVRO_CECOM').count(),
    }
    paginator = Paginator(docs, 15)
    return render(request, 'common/documentos_assinados.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'assin_counts': assin_counts,
        'filtro_tipo': 'bogcm',
    })

@login_required
@comando_required
def documentos_assinados_livro(request: HttpRequest):
    q = (request.GET.get('q') or '').strip()
    docs = DocumentoAssinavel.objects.filter(status='ASSINADO_ADM', tipo='LIVRO_CECOM')
    if q:
        filters = (
            Q(usuario_origem__username__icontains=q) |
            Q(usuario_origem__first_name__icontains=q) |
            Q(usuario_origem__last_name__icontains=q) |
            Q(arquivo__icontains=q) |
            Q(arquivo_assinado__icontains=q) |
            Q(tipo__icontains=q) |
            Q(status__icontains=q)
        )
        if q.isdigit():
            try:
                filters |= Q(pk=int(q))
            except Exception:
                pass
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", q)
        if m:
            from datetime import date
            dia = int(m.group(1)); mes = int(m.group(2)); ano = m.group(3)
            try:
                if ano:
                    d0 = date(int(ano), mes, dia)
                    filters |= Q(created_at__date=d0)
                else:
                    filters |= Q(created_at__day=dia, created_at__month=mes)
            except Exception:
                pass
        docs = docs.filter(filters)
    docs = docs.select_related('usuario_origem','comando_usuario').order_by('-created_at')
    assin_counts = {
        'ronda': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='PLANTAO').count(),
        'bogcm': DocumentoAssinavel.objects.filter(status='ASSINADO', tipo='BOGCMI').count(),
        'livro': DocumentoAssinavel.objects.filter(status='ASSINADO_ADM', tipo='LIVRO_CECOM').count(),
    }
    paginator = Paginator(docs, 15)
    return render(request, 'common/documentos_assinados.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'q': q,
        'assin_counts': assin_counts,
        'filtro_tipo': 'livro',
    })


@login_required
@comando_required
def diagnostico_pdfs(request: HttpRequest):
    """Mostra status dos motores de geração de PDF (pdfkit/wkhtmltopdf, WeasyPrint, xhtml2pdf, ReportLab, PyPDF2/pypdf).

    Coleta:
      - Import ok/falha e mensagem
      - Versão
      - Caminhos de binários relevantes (wkhtmltopdf)
    """
    def check_import(mod_name):
        try:
            m = importlib.import_module(mod_name)
            ver = getattr(m, '__version__', '?')
            return True, ver, ''
        except Exception as e:  # pragma: no cover
            return False, '', str(e)
    results = {}
    # pdfkit + wkhtmltopdf
    ok, ver, err = check_import('pdfkit')
    wkhtmltopdf_path = ''
    if ok:
        try:
            from django.conf import settings as _s
            conf = getattr(_s, 'WKHTMLTOPDF_CMD', '')
            if conf and os.path.exists(conf):
                wkhtmltopdf_path = conf
            else:
                # tenta achar no PATH
                wkhtmltopdf_path = shutil.which('wkhtmltopdf') or ''
        except Exception:
            pass
    results['pdfkit'] = {'ok': ok, 'version': ver, 'error': err, 'wkhtmltopdf': wkhtmltopdf_path}
    # weasyprint
    ok, ver, err = check_import('weasyprint')
    results['weasyprint'] = {'ok': ok, 'version': ver, 'error': err}
    # xhtml2pdf
    ok, ver, err = check_import('xhtml2pdf')
    results['xhtml2pdf'] = {'ok': ok, 'version': ver, 'error': err}
    # reportlab
    ok, ver, err = check_import('reportlab')
    results['reportlab'] = {'ok': ok, 'version': ver, 'error': err}
    # PyPDF2/pypdf
    py_pdf = {}
    for lib in ('PyPDF2','pypdf'):
        ok, ver, err = check_import(lib)
        py_pdf[lib] = {'ok': ok, 'version': ver, 'error': err}
    results['pdf_readers'] = py_pdf
    # pequeno teste gerando PDF com reportlab (sanity)
    test_pdf_size = None
    try:
        buff = BytesIO(); c = canvas.Canvas(buff); c.drawString(50,800,'Teste PDF OK'); c.showPage(); c.save(); test_pdf_size=len(buff.getvalue())
    except Exception as e:
        test_pdf_size = f'erro: {e}'
    # Ambiente
    env_info = {
        'python_exec': sys.executable,
        'platform': sys.platform,
        'wkhtmltopdf_in_path': bool(shutil.which('wkhtmltopdf')),
    }
    return render(request, 'common/diagnostico_pdfs.html', {'results': results, 'env': env_info, 'test_pdf_size': test_pdf_size})


def _obter_assinatura_comando(user):
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return None
    # Preferir desenho base64
    assin = getattr(perfil, 'assinatura_digital', None)
    if assin:
        try:
            import base64
            if assin.startswith('data:image'):
                assin = assin.split(',',1)[1]
            data = base64.b64decode(assin)
            img = Image.open(BytesIO(data))
            return img
        except Exception:
            pass
    # Depois arquivo
    for attr in ('assinatura_img','assinatura'):
        f = getattr(perfil, attr, None)
        if f and getattr(f,'path',None):
            try:
                return Image.open(f.path)
            except Exception:
                continue
    return None


def _nome_primeiro_ultimo(nome_raw: str) -> str:
    """Recebe nome completo (ou username) e retorna apenas Primeiro e Último nome.

    Se houver somente uma palavra, retorna como está. Ignora espaços extras.
    """
    if not nome_raw:
        return ''
    partes = [p for p in nome_raw.strip().split() if p]
    if not partes:
        return ''
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[-1]}"

def _append_assinatura(pdf_original_path: str, assinatura_img: Image.Image, nome_comando: str, titulo_assinatura: str = 'Despacho / Assinatura do Comando', bo_num: str | None = None, data_emissao_dt=None, matricula: str | None = None, cargo: str | None = None, classe: str | None = None, qr_code_base64: str | None = None) -> bytes:
    """Anexa página de assinatura ao PDF preservando conteúdo original.

    Estratégia:
      1. Tenta mesclar via PyPDF2 (mais fiel, mantém texto pesquisável).
      2. Se falhar, rasteriza páginas originais em imagens e recompõe + página de assinatura.
      3. Se ainda assim falhar, retorna somente página de assinatura (último recurso).
    """
    # Página de assinatura isolada
    assinatura_buff = BytesIO()
    c = canvas.Canvas(assinatura_buff, pagesize=A4)
    w,h = A4
    if assinatura_img and assinatura_img.mode not in ('RGB','RGBA'):
        assinatura_img = assinatura_img.convert('RGBA')
    if assinatura_img:
        # Normalizar tamanho para padronizar com o documento do BO (assinatura do encarregado): max 240x70
        max_w, max_h = 240, 70
        assinatura_img.thumbnail((max_w, max_h), Image.LANCZOS)
        img_buf = BytesIO()
        assinatura_img.save(img_buf, format='PNG')
        img_buf.seek(0)
        # Cartão estilo "bloco" do BO (apenas uma borda clara, sem fundo azul)
        # Cores aproximadas do template: borda #e5e7eb (229,231,235)
        border_r = 229/255.0; border_g = 231/255.0; border_b = 235/255.0
        inner_margin = 14
        card_width = w - 100  # margem lateral de 50
        card_height = 210     # altura similar ao bloco de assinatura do BO
        # Posicionar pouco acima do centro
        card_bottom = (h/2) - (card_height/2) + 50
        card_left = 50
        # Desenhar cartão
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(border_r, border_g, border_b)
        c.setLineWidth(1)
        c.roundRect(card_left, card_bottom, card_width, card_height, 8, stroke=1, fill=1)

        inner_x = card_left + inner_margin
        inner_y = card_bottom + inner_margin
        inner_w = card_width - inner_margin*2
        inner_h = card_height - inner_margin*2

        # Título no topo interno, alinhado à esquerda como um h4
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(inner_x + 6, inner_y + inner_h - 24, titulo_assinatura)

        # Área de assinatura centralizada (um pouco mais baixa)
        assinatura_y = inner_y + inner_h/2 - 8
        # Desenhar imagem de assinatura
        center_x = card_left + card_width/2
        c.drawImage(ImageReader(img_buf), center_x - (assinatura_img.width/2), assinatura_y, width=assinatura_img.width, height=assinatura_img.height, mask='auto')

        # Linha horizontal sob a assinatura (largura 240px)
        linha_w = 240
        linha_x1 = (card_left + card_width/2) - (linha_w/2)
        linha_x2 = linha_x1 + linha_w
        linha_y = assinatura_y - 10
        c.setStrokeColorRGB(0.07, 0.08, 0.12)
        c.setLineWidth(1.0)
        c.line(linha_x1, linha_y, linha_x2, linha_y)

        # Nome, matrícula (abaixo do nome) e cargo/classe centralizados
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica', 10)
        c.drawCentredString(center_x, linha_y - 16, nome_comando)
        next_y = linha_y - 30
        if matricula:
            c.setFont('Helvetica', 9)
            c.drawCentredString(center_x, next_y, f"Mat: {matricula}")
            next_y -= 14
        info_cargo = []
        if cargo:
            info_cargo.append(cargo)
        if classe:
            info_cargo.append(classe)
        if info_cargo:
            c.setFont('Helvetica', 9)
            c.drawCentredString(center_x, next_y, ' - '.join(info_cargo))

        # QR Code à direita dentro do cartão, tamanho ~90px com moldura clara e legenda
        if qr_code_base64:
            try:
                import base64
                qr_data = base64.b64decode(qr_code_base64.split(',')[-1])
                qr_img = Image.open(BytesIO(qr_data))
                qr_img.thumbnail((90, 90), Image.LANCZOS)
                qr_buf = BytesIO(); qr_img.save(qr_buf, format='PNG'); qr_buf.seek(0)
                qr_x = inner_x + inner_w - qr_img.width - 8
                qr_y = inner_y + (inner_h - qr_img.height)/2
                c.setFillColorRGB(1, 1, 1)
                c.setStrokeColorRGB(border_r, border_g, border_b)
                c.setLineWidth(0.8)
                c.roundRect(qr_x-4, qr_y-4, qr_img.width+8, qr_img.height+8, 6, stroke=1, fill=1)
                c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_img.width, height=qr_img.height, mask='auto')
                c.setFillColorRGB(0.22, 0.25, 0.31)
                c.setFont('Helvetica', 6)
                c.drawCentredString(qr_x + qr_img.width/2, qr_y-12, 'Verificação Online')
            except Exception:
                pass
    else:
        c.setFillColorRGB(0, 0, 0)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(50, h-80, titulo_assinatura)
        c.setFont('Helvetica', 12)
        c.drawString(50, h-110, '(Sem assinatura cadastrada)')
    c.showPage(); c.save()

    assinatura_pdf_bytes = assinatura_buff.getvalue()

    def _dbg(msg: str):
        try:
            media_root = getattr(settings, 'MEDIA_ROOT', 'media')
            log_dir = os.path.join(media_root, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'assinatura_debug.log'), 'a', encoding='utf-8') as f:
                f.write(f"{timezone.now():%Y-%m-%d %H:%M:%S} | {msg}\n")
        except Exception:
            print(msg)

    import os
    try:
        stat_info = os.stat(pdf_original_path)
        _dbg(f"Orig path={pdf_original_path} size={stat_info.st_size} bytes")
    except FileNotFoundError:
        _dbg(f"Arquivo não encontrado: {pdf_original_path}")
    except Exception as e:
        _dbg(f"Falha stat arquivo original: {e}")

    # Verificar bytes iniciais
    try:
        with open(pdf_original_path,'rb') as ftest:
            head = ftest.read(8)
            _dbg(f"Magic bytes: {head!r}")
    except Exception as e:
        _dbg(f"Falha lendo magic bytes: {e}")

    # Nova estratégia determinística: ler original -> montar writer -> anexar assinatura
    # Diagnóstico avançado de import (captura caminho do Python e sys.path)
    import sys, traceback, importlib
    try:
        _dbg(f"Python exec: {sys.executable}")
        _dbg("sys.path (primeiros 5): " + ' | '.join(sys.path[:5]))
    except Exception:  # pragma: no cover - não deve falhar, mas não quebra fluxo
        pass

    # Testar explicitamente cada biblioteca e registrar motivo da falha
    PdfReader = PdfWriter = None
    import_errors: dict[str,str] = {}
    for lib in ('PyPDF2','pypdf'):
        try:
            mod = importlib.import_module(lib)
            # Algumas versões expõem PdfReader em caminhos diferentes; usar getattr seguro
            reader = getattr(mod, 'PdfReader', None)
            writer = getattr(mod, 'PdfWriter', None)
            if reader and writer:
                PdfReader, PdfWriter = reader, writer
                _dbg(f"Import OK {lib} version={getattr(mod,'__version__','?')}")
                break
            else:
                import_errors[lib] = 'Classes PdfReader/PdfWriter não encontradas'
        except Exception as e:  # Registrar mensagem compacta e tipo
            import_errors[lib] = f"{e.__class__.__name__}: {e}"
            # Capturar 1ª linha do traceback para facilitar debug sem poluir log
            tb_line = traceback.format_exc().strip().splitlines()[-1]
            _dbg(f"Import FAIL {lib}: {tb_line}")

    if PdfReader is None or PdfWriter is None:
        # Fail-fast: não gerar PDF truncado silenciosamente
        msg = "Biblioteca PDF não encontrada (PyPDF2/pypdf). Servidor provavelmente fora do virtualenv."
        _dbg(msg + " Motivos: " + ' ; '.join(f"{k}=>{v}" for k,v in import_errors.items()))
        raise RuntimeError(msg)
    try:
        import shutil, tempfile
        # Copiar para arquivo temporário (evita lock ou escrita incompleta)
        temp_dir = tempfile.gettempdir()
        temp_copy = os.path.join(temp_dir, f"orig_merge_{os.path.basename(pdf_original_path)}")
        try:
            shutil.copy2(pdf_original_path, temp_copy)
            _dbg(f"Copia temporária criada: {temp_copy}")
        except Exception as e:
            _dbg(f"Falha ao criar cópia temporária: {e}")

        with open(temp_copy if os.path.exists(temp_copy) else pdf_original_path,'rb') as fsrc:
            orig_reader = PdfReader(fsrc, strict=False)
            num_orig = len(orig_reader.pages)
            _dbg(f"Mesclagem determinística: paginas_orig={num_orig}")
            if num_orig == 0:
                _dbg("Nenhuma página no PDF original - abortando")
                raise ValueError("PDF original sem páginas")
            assinatura_reader = PdfReader(BytesIO(assinatura_pdf_bytes), strict=False)
            writer = PdfWriter()
            for i,p in enumerate(orig_reader.pages):
                try:
                    writer.add_page(p)
                except Exception as e:
                    _dbg(f"Falha add página original {i}: {e}")
                    raise
            for j,p in enumerate(assinatura_reader.pages):
                writer.add_page(p)
            out_buf = BytesIO(); writer.write(out_buf)
            merged_bytes = out_buf.getvalue()
            final_reader = PdfReader(BytesIO(merged_bytes), strict=False)
            total = len(final_reader.pages)
            _dbg(f"Sucesso mesclagem final: total_paginas={total}")
            esperado = num_orig + len(assinatura_reader.pages)
            if total != esperado:
                _dbg(f"ERRO: total_paginas({total}) != esperado({esperado}) — abortando para evitar PDF truncado")
                raise RuntimeError("Falha na validação do merge (contagem de páginas)")
            # Reabrir para sobrepor numeração de páginas no rodapé
            try:
                from reportlab.pdfgen import canvas as _c
                from reportlab.lib.pagesizes import A4 as _A4
                from PyPDF2 import PdfReader as _R, PdfWriter as _W
                temp_pdf = BytesIO(merged_bytes)
                base_reader = _R(temp_pdf)
                final_writer = _W()
                num_total = len(base_reader.pages)
                # Preparar textos fixos de rodapé (BO + Data/Hora) se fornecidos
                bo_text = f"BO Nº {bo_num}" if bo_num else None
                if data_emissao_dt:
                    try:
                        data_emissao_fmt = timezone.localtime(data_emissao_dt).strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        data_emissao_fmt = timezone.now().strftime('%d/%m/%Y %H:%M')
                else:
                    data_emissao_fmt = None
                data_text = f"Data/Hora: {data_emissao_fmt}" if data_emissao_fmt else None
                for idx in range(num_total):
                    page = base_reader.pages[idx]
                    # Hash da página (antes do overlay): SHA-256 dos bytes da página isolada
                    try:
                        _tmp_buf = BytesIO(); _tmp_w = _W(); _tmp_w.add_page(page)
                        _tmp_w.write(_tmp_buf)
                        page_hash8 = hashlib.sha256(_tmp_buf.getvalue()).hexdigest()[:12].upper()
                    except Exception:
                        page_hash8 = None
                    packet = BytesIO(); can = _c.Canvas(packet, pagesize=_A4)
                    can.setFont('Helvetica',7)
                    y_footer = 18
                    # Página X / Y (sempre à direita)
                    can.drawRightString(_A4[0]-36, y_footer, f"Página {idx+1} / {num_total}")
                    # BO Nº + Hash (à esquerda)
                    left_parts = []
                    if bo_text:
                        left_parts.append(bo_text)
                    if page_hash8:
                        left_parts.append(f"H:{page_hash8}")
                    if left_parts:
                        can.drawString(36, y_footer, '   '.join(left_parts))
                    # Data/Hora (centralizado se existir)
                    if data_text:
                        can.drawCentredString(_A4[0]/2, y_footer, data_text)
                    can.save(); packet.seek(0)
                    overlay = _R(packet)
                    try:
                        page.merge_page(overlay.pages[0])
                    except Exception:
                        pass
                    final_writer.add_page(page)
                out_final = BytesIO(); final_writer.write(out_final)
                merged_bytes = out_final.getvalue()
            except Exception as e:
                _dbg(f"Falha ao aplicar numeração de páginas: {e}")
            return merged_bytes
    except Exception as e:
        _dbg(f"ERRO FATAL mesclagem: {e}")
        raise


@login_required
@comando_required
def assinar_documento(request: HttpRequest, pk: int):
    if request.method != 'POST':
        return HttpResponseForbidden()
    doc = get_object_or_404(DocumentoAssinavel, pk=pk)

    from django.contrib import messages
    estados_finais = {'ASSINADO', 'ASSINADO_ADM'}
    if doc.status in estados_finais:
        messages.warning(request, f'Documento #{pk} já foi assinado anteriormente.')
        return redirect('common:documentos_assinados')
    estados_pendentes_validos = {'PENDENTE', 'PENDENTE_ADM'}
    if doc.status not in estados_pendentes_validos:
        messages.error(request, f'Documento #{pk} não está disponível para assinatura.')
        return redirect('common:documentos_pendentes')

    assinatura_img = _obter_assinatura_comando(request.user)
    pdf_path = doc.arquivo.path
    try:
        titulo_assin = 'Despacho / Assinatura da Administração' if doc.tipo == 'LIVRO_CECOM' else 'Despacho / Assinatura do Comando/Sub Comando'
        # Padronizar título curto conforme solicitado (CMT/SUBCMT) para BOGCMI/BOGCM
        if doc.tipo in ('BOGCMI','BOGCM'):
            titulo_assin = 'Despacho CMT/SUBCMT'
        bo_num = None
        data_emissao_dt = getattr(doc, 'created_at', None)
        if doc.tipo in ['BOGCMI', 'BOGCM']:
            try:
                base = os.path.basename(doc.arquivo.name)
                # aceitar tanto _BOGCM_ quanto _BOGCMI_ nos nomes gerados
                m_new = re.search(r'_BOGCMI?_(\d+-\d{4})', base)
                if m_new:
                    bo_num = m_new.group(1)
                else:
                    m_old = re.search(r'_BOGCMI?_(\d+)\.pdf$', base)
                    if m_old:
                        bo_num = m_old.group(1)
            except Exception:
                pass
        nome_full = request.user.get_full_name() or request.user.username
        nome_assin = _nome_primeiro_ultimo(nome_full)
        perfil_cmd = getattr(request.user, 'perfil', None)
        matricula = getattr(perfil_cmd, 'matricula', None) if perfil_cmd else None
        cargo = getattr(perfil_cmd, 'cargo', None) if perfil_cmd else None
        classe_legivel = getattr(perfil_cmd, 'classe_legivel', None) if perfil_cmd else None
        qr_code_val = None
        if doc.tipo == 'BOGCMI':
            try:
                from bogcmi.models import BO
                base = os.path.basename(doc.arquivo.name)
                # aceitar tanto _BOGCM_ quanto _BOGCMI_
                m_new = re.search(r'_BOGCMI?_(\d+-\d{4})', base)
                bo_obj = None
                if m_new:
                    bo_obj = BO.objects.filter(numero=m_new.group(1)).first()
                if bo_obj:
                    from bogcmi.views_core import _gerar_qr_code_para_bo
                    qr_code_val = _gerar_qr_code_para_bo(request, bo_obj)
            except Exception:
                pass
        novo_pdf = _append_assinatura(
            pdf_path,
            assinatura_img,
            nome_assin,
            titulo_assinatura=titulo_assin,
            bo_num=bo_num,
            data_emissao_dt=data_emissao_dt,
            matricula=matricula,
            cargo=cargo,
            classe=classe_legivel,
            qr_code_base64=qr_code_val
        )
    except Exception as e:
        messages.error(request, f'Falha ao anexar assinatura: {e}')
        return redirect('common:documentos_pendentes')

    # Novo padrão de salvamento: ano subpasta + timestamp + BOGCMI + numero + id + _SIGN_ + hash
    year = timezone.now().year
    numero_for_name = bo_num or 'DOC'
    ts = timezone.now()
    hash8 = hashlib.sha256(f"ASSIN-{doc.id}-{numero_for_name}-{ts.timestamp()}".encode()).hexdigest()[:8]
    signed_filename = f"{ts:%Y%m%d_%H%M%S}_BOGCMI_{numero_for_name}_{doc.id}_SIGN_{hash8}.pdf"
    caminho = f"{year}/{signed_filename}"
    doc.arquivo_assinado.save(caminho, ContentFile(novo_pdf), save=False)

    if doc.tipo == 'LIVRO_CECOM':
        doc.status = 'ASSINADO_ADM'
    else:
        doc.status = 'ASSINADO'
    doc.comando_assinou = True
    doc.comando_assinou_em = timezone.now()
    doc.comando_usuario = request.user
    doc.save(update_fields=['arquivo_assinado', 'status', 'comando_assinou', 'comando_assinou_em', 'comando_usuario'])

    if doc.tipo == 'BOGCMI':
        try:
            from bogcmi.models import BO
            bo = None
            if bo_num and '-' in bo_num:
                bo = BO.objects.filter(numero=bo_num).first()
            elif bo_num and bo_num.isdigit():
                bo = BO.objects.filter(id=bo_num).first()
            if bo and bo.status != 'ARQUIVADO':
                bo.status = 'ARQUIVADO'
                bo.save(update_fields=['status'])
            else:
                # informa se não foi possível localizar BO correspondente (ajuda no debug)
                if not bo:
                    try:
                        from django.contrib import messages as _msgs
                        _msgs.info(request, 'BO não localizado a partir do nome do arquivo; status não alterado.')
                    except Exception:
                        pass
        except Exception:
            pass
    messages.success(request, f'Documento #{pk} assinado com sucesso!')
    return redirect('common:documentos_assinados')


@login_required
@comando_required
def assinar_documentos_lote(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponseForbidden()
    from django.contrib import messages
    ids = request.POST.getlist('ids')
    # redirecionamento preferencial: volta para a página que chamou (aba pendente)
    redirect_fallback = request.META.get('HTTP_REFERER') or 'common:documentos_pendentes'
    if not ids:
        messages.warning(request, 'Nenhum documento selecionado para assinatura.')
        return redirect(redirect_fallback)
    ok = 0; fail = 0
    # Processar em ordem; em caso de erro num, continua nos demais
    for sid in ids:
        try:
            pk = int(sid)
        except Exception:
            fail += 1
            continue
        try:
            # Replicar fluxo de assinar_documento com try/except por item
            doc = DocumentoAssinavel.objects.get(pk=pk)
            estados_finais = {'ASSINADO', 'ASSINADO_ADM'}
            if doc.status in estados_finais:
                # já assinado, conta como ok idempotente
                ok += 1
                continue
            if doc.status not in {'PENDENTE', 'PENDENTE_ADM'}:
                fail += 1
                continue
            assinatura_img = _obter_assinatura_comando(request.user)
            pdf_path = doc.arquivo.path
            titulo_assin = 'Despacho / Assinatura da Administração' if doc.tipo == 'LIVRO_CECOM' else 'Despacho / Assinatura do Comando/Sub Comando'
            if doc.tipo in ('BOGCMI','BOGCM'):
                titulo_assin = 'Despacho CMT/SUBCMT'
            bo_num = None
            data_emissao_dt = getattr(doc, 'created_at', None)
            if doc.tipo in ['BOGCMI', 'BOGCM']:
                try:
                    base = os.path.basename(doc.arquivo.name)
                    m_new = re.search(r'_BOGCMI?_(\d+-\d{4})', base)
                    if m_new:
                        bo_num = m_new.group(1)
                    else:
                        m_old = re.search(r'_BOGCMI?_(\d+)\.pdf$', base)
                        if m_old:
                            bo_num = m_old.group(1)
                except Exception:
                    pass
            nome_full = request.user.get_full_name() or request.user.username
            nome_assin = _nome_primeiro_ultimo(nome_full)
            perfil_cmd = getattr(request.user, 'perfil', None)
            matricula = getattr(perfil_cmd, 'matricula', None) if perfil_cmd else None
            cargo = getattr(perfil_cmd, 'cargo', None) if perfil_cmd else None
            classe_legivel = getattr(perfil_cmd, 'classe_legivel', None) if perfil_cmd else None
            qr_code_val = None
            if doc.tipo == 'BOGCMI':
                try:
                    from bogcmi.models import BO
                    base = os.path.basename(doc.arquivo.name)
                    m_new = re.search(r'_BOGCMI?_(\d+-\d{4})', base)
                    bo_obj = None
                    if m_new:
                        bo_obj = BO.objects.filter(numero=m_new.group(1)).first()
                    if bo_obj:
                        from bogcmi.views_core import _gerar_qr_code_para_bo
                        qr_code_val = _gerar_qr_code_para_bo(request, bo_obj)
                except Exception:
                    pass
            novo_pdf = _append_assinatura(
                pdf_path,
                assinatura_img,
                nome_assin,
                titulo_assinatura=titulo_assin,
                bo_num=bo_num,
                data_emissao_dt=data_emissao_dt,
                matricula=matricula,
                cargo=cargo,
                classe=classe_legivel,
                qr_code_base64=qr_code_val
            )
            year = timezone.now().year
            numero_for_name = bo_num or 'DOC'
            ts = timezone.now()
            hash8 = hashlib.sha256(f"ASSIN-{doc.id}-{numero_for_name}-{ts.timestamp()}".encode()).hexdigest()[:8]
            signed_filename = f"{ts:%Y%m%d_%H%M%S}_BOGCMI_{numero_for_name}_{doc.id}_SIGN_{hash8}.pdf"
            caminho = f"{year}/{signed_filename}"
            doc.arquivo_assinado.save(caminho, ContentFile(novo_pdf), save=False)
            if doc.tipo == 'LIVRO_CECOM':
                doc.status = 'ASSINADO_ADM'
            else:
                doc.status = 'ASSINADO'
            doc.comando_assinou = True
            doc.comando_assinou_em = timezone.now()
            doc.comando_usuario = request.user
            doc.save(update_fields=['arquivo_assinado', 'status', 'comando_assinou', 'comando_assinou_em', 'comando_usuario'])
            if doc.tipo == 'BOGCMI':
                try:
                    from bogcmi.models import BO
                    bo = None
                    if bo_num and '-' in bo_num:
                        bo = BO.objects.filter(numero=bo_num).first()
                    elif bo_num and bo_num.isdigit():
                        bo = BO.objects.filter(id=bo_num).first()
                    if bo and bo.status != 'ARQUIVADO':
                        bo.status = 'ARQUIVADO'
                        bo.save(update_fields=['status'])
                except Exception:
                    pass
            ok += 1
        except Exception:
            fail += 1
            continue
    if ok and not fail:
        messages.success(request, f'{ok} documento(s) assinados com sucesso.')
    elif ok and fail:
        messages.warning(request, f'{ok} assinado(s), {fail} falhou(aram). Verifique os arquivos problemáticos.')
    else:
        messages.error(request, 'Falha ao assinar os documentos selecionados.')
    # Preferir voltar para a aba pendente original (HTTP_REFERER); se for None, cair no "pendentes"
    try:
        from django.shortcuts import redirect as _redir
        if isinstance(redirect_fallback, str) and redirect_fallback.startswith('http'):
            return _redir(redirect_fallback)
    except Exception:
        pass
    return redirect('common:documentos_pendentes')


@login_required
@comando_required
def recusar_documento(request: HttpRequest, pk: int):
    if request.method != 'POST':
        return HttpResponseForbidden()
    doc = get_object_or_404(DocumentoAssinavel, pk=pk)
    from django.contrib import messages
    if doc.tipo != 'BOGCMI' or doc.status != 'PENDENTE':
        messages.error(request, 'Documento não pode ser recusado.')
        return redirect('common:documentos_pendentes_bogcm')

    import re, os
    base = os.path.basename(doc.arquivo.name)
    from bogcmi.models import BO
    bo = None
    # Novo padrão: ..._BOGCM_<seq-ano>_...pdf
    # Novo padrão pode vir com BOGCMI (preferencial). Aceitar BOGCMI ou BOGCM.
    m_new = re.search(r'_BOGCMI?_(\d+-\d{4})', base)
    if m_new:
        numero = m_new.group(1)
        bo = BO.objects.filter(numero=numero).first()
    else:
        # Legado: ..._BOGCM_<pk>.pdf
        m_old = re.search(r'_BOGCM_(\d+)\.pdf$', base)
        if m_old:
            bo = BO.objects.filter(pk=m_old.group(1)).first()

    # Observação (opcional): salvar no documento
    obs = (request.POST.get('observacao') or '').strip()
    if obs:
        try:
            doc.observacao = obs[:255]
            doc.save(update_fields=['observacao'])
        except Exception:
            pass

    if bo:
        # Volta para FINALIZADO (editável) limpando deadline; opção solicitada: editar novamente.
        bo.status = 'FINALIZADO'
        bo.edit_deadline = None
        bo.save(update_fields=['status','edit_deadline'])
        # Enviar push ao encarregado para ciência e correção
        try:
            from .models import PushDevice
            tokens = list(PushDevice.objects.filter(user=bo.encarregado, enabled=True).values_list('token', flat=True))
            if tokens:
                numero = getattr(bo, 'numero', '') or doc.bo_numero or str(bo.id)
                titulo = 'BOGCM devolvido para correção'
                corpo = f'BO {numero}: ' + (doc.observacao or 'Comando solicitou correção.')
                try:
                    url = reverse('bogcmi:editar', args=[bo.id])
                except Exception:
                    url = '/bogcmi/%d/editar/' % bo.id
                enviar_push(tokens, title=titulo, body=corpo, data={
                    'kind': 'ack',
                    'type': 'bogcmi_recusa',
                    'bo_id': str(bo.id),
                    'url': url,
                })
        except Exception:
            pass

        # Criar notificação persistente para o encarregado (centro de Notificações)
        try:
            if getattr(bo, 'encarregado', None):
                from core.models import UserNotification
                try:
                    notif_url = reverse('bogcmi:editar', args=[bo.id])
                except Exception:
                    notif_url = '/bogcmi/%d/editar/' % bo.id
                numero_label = getattr(bo, 'numero', '') or doc.bo_numero or str(bo.id)
                titulo_n = 'BOGCM devolvido para correção'
                mensagem = f"BO {numero_label}: " + (doc.observacao or 'Comando solicitou correção.')
                UserNotification.objects.create(
                    user=bo.encarregado,
                    kind='BO_RECUSA',
                    title=titulo_n,
                    message=mensagem,
                    link_url=notif_url,
                )
        except Exception:
            pass

    # Remover documento pendente (não ficará mais na fila do Comando)
    try:
        doc.delete()
        messages.success(request, f'Documento #{pk} recusado. BO retornou ao status FINALIZADO para nova edição.')
    except Exception as e:
        messages.error(request, f'Falha ao recusar documento: {e}')
    return redirect('common:documentos_pendentes_bogcm')


@login_required
@comando_required
def excluir_documento(request: HttpRequest, pk: int):
    """Exclui um DocumentoAssinavel (pendente ou assinado) – somente superadmin 'moises'.

    Regras:
      - Apenas método POST.
      - Apenas usuário cujo username == 'moises' (hardcode conforme requisito) ou superuser com username 'moises'.
      - Remove também arquivos físicos (arquivo e arquivo_assinado) se existirem.
    """
    if request.method != 'POST':
        return HttpResponseForbidden()
    if request.user.username != 'moises':
        return HttpResponseForbidden('Somente superadmin moises pode excluir documentos.')
    from django.contrib import messages
    doc = get_object_or_404(DocumentoAssinavel, pk=pk)
    # Guardar tipo/status para decidir redirect
    tipo = doc.tipo
    status = doc.status
    try:
        # Apagar arquivos físicos
        for f in (doc.arquivo, doc.arquivo_assinado):
            try:
                if f and getattr(f, 'path', None) and os.path.exists(f.path):
                    os.remove(f.path)
            except Exception:
                pass
        doc.delete()
        messages.success(request, f'Documento #{pk} excluído.')
    except Exception as e:
        messages.error(request, f'Falha ao excluir documento: {e}')
    # Redirecionar conforme origem (pendente vs assinado + tipo)
    if status == 'PENDENTE':
        if tipo == 'BOGCMI':
            return redirect('common:documentos_pendentes_bogcm')
        elif tipo == 'PLANTAO':
            return redirect('common:documentos_pendentes_ronda')
        return redirect('common:documentos_pendentes')
    else:
        if tipo == 'BOGCMI':
            return redirect('common:documentos_assinados_bogcm')
        elif tipo == 'PLANTAO':
            return redirect('common:documentos_assinados_ronda')
        return redirect('common:documentos_assinados')


# --- Push Notifications (FCM) ---

def _get_firebase_app():
    """Lazy-inicializa o firebase_admin usando credenciais em settings.FIREBASE_CREDENTIALS_JSON.

    Evita quebrar manage.py check caso a lib não esteja instalada no ambiente de desenvolvimento local.
    """
    try:
        import firebase_admin
        from firebase_admin import credentials
    except Exception as e:  # pragma: no cover
        import logging, sys
        logging.getLogger(__name__).error(
            f"[PUSH] Falha ao importar firebase_admin: {e} | PYTHON={sys.executable}")
        raise RuntimeError(
            "Falha ao importar firebase-admin (veja log para detalhe). Verifique instalação no venv ativo.") from e
    if not firebase_admin._apps:
        creds_json = getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None)
        if not creds_json:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON não configurado no settings.")
        cred = credentials.Certificate(creds_json)
        firebase_admin.initialize_app(cred)
    return True


def enviar_push(tokens: Iterable[str], title: str, body: str, data: Optional[dict] = None, return_details: bool = False) -> Union[int, Dict[str, object]]:
    """Envia notificação push via FCM para uma lista de tokens.

    - tokens: lista de registration tokens (strings)
    - title/body: texto da notificação
    - data: payload adicional (strings)
    - return_details: quando True, retorna dict com detalhes de falhas/remoções; caso contrário, retorna apenas número de sucessos.
    """
    _get_firebase_app()
    from firebase_admin import messaging
    data = {k: str(v) for k, v in (data or {}).items()}
    # Normaliza: remove vazios e deduplica preservando ordem
    seen: set[str] = set()
    tokens = [t for t in tokens if t and (t not in seen and not seen.add(t))]
    if not tokens:
        return {'success': 0, 'failures': 0, 'disabled': 0, 'errors': []} if return_details else 0

    def _should_disable(exc: Exception) -> bool:
        """Heurística para desativar tokens inválidos/obsoletos.

        As mensagens do Firebase podem variar; cobrimos os textos mais comuns
        retornados pelo SDK Admin (HTTP v1) e pelo endpoint legado.
        """
        s = (str(exc) or '').lower()
        patterns = (
            'not registered',
            'unregistered',
            'no matching registration token',
            'invalid registration',
            'mismatch sender',
            'invalid-argument',
            'requested entity was not found',       # HTTP v1
            'registration-token-not-registered',    # código canônico
            'invalid registration token',
        )
        return any(p in s for p in patterns)

    errors: List[Dict[str, str]] = []
    disabled_count = 0
    success = 0
    # Primeiro, tenta envio em lote (usa endpoint /batch do Google APIs)
    try:
        for i in range(0, len(tokens), 500):
            chunk = tokens[i:i+500]
            # Se houver título/corpo envia notification + data.
            # Caso contrário envia data-only (service recebe em qualquer estado e monta notificação própria).
            if title or body:
                message_params = {
                    'data': data,
                    'tokens': chunk,
                    'notification': messaging.Notification(title=title, body=body),
                    'android': messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            channel_id='default',
                            sound='default',
                            color='#2E7D32'
                        )
                    )
                }
            else:
                message_params = {
                    'data': data,
                    'tokens': chunk,
                    'android': messaging.AndroidConfig(priority='high')
                }

            # Log simples para auditoria (não critica se falhar)
            try:
                import logging
                logging.getLogger(__name__).info(
                    f"[PUSH] tipo={'notification' if (title or body) else 'data-only'} qtd_tokens={len(chunk)} keys_data={list(data.keys())[:6]}"
                )
            except Exception:
                pass
            
            message = messaging.MulticastMessage(**message_params)
            resp = messaging.send_multicast(message)
            success += resp.success_count
            # Detalhes de falhas por token
            if getattr(resp, 'responses', None):
                for idx, r in enumerate(resp.responses):
                    if not r.success:
                        t = chunk[idx]
                        exc = getattr(r, 'exception', Exception('unknown error'))
                        token_label = t[:24] + '…' if len(t) > 24 else t
                        errors.append({'token': token_label, 'error': str(exc)[:240]})
                        if _should_disable(exc):
                            try:
                                with transaction.atomic():
                                    PushDevice.objects.filter(token=t).update(enabled=False)
                                disabled_count += 1
                            except Exception:
                                pass
        return {'success': success, 'failures': max(0, len(errors)), 'disabled': disabled_count, 'errors': errors} if return_details else success
    except Exception:
        # Fallback: algumas redes/proxies quebram o endpoint /batch.
        # Envia individualmente para evitar o /batch.
        for t in list(tokens):
            try:
                if title or body:
                    msg_params = {
                        'token': t,
                        'data': data,
                        'notification': messaging.Notification(title=title, body=body),
                        'android': messaging.AndroidConfig(
                            priority='high',
                            notification=messaging.AndroidNotification(
                                channel_id='default',
                                sound='default',
                                color='#2E7D32'
                            )
                        )
                    }
                else:
                    msg_params = {
                        'token': t,
                        'data': data,
                        'android': messaging.AndroidConfig(priority='high')
                    }

                try:
                    import logging
                    logging.getLogger(__name__).info(
                        f"[PUSH:FALLBACK] tipo={'notification' if (title or body) else 'data-only'} token_pref={t[:12]}"
                    )
                except Exception:
                    pass
                
                msg = messaging.Message(**msg_params)
                messaging.send(msg)
                success += 1
            except Exception as e:
                token_label = t[:24] + '…' if len(t) > 24 else t
                errors.append({'token': token_label, 'error': str(e)[:240]})
                if _should_disable(e):
                    try:
                        with transaction.atomic():
                            PushDevice.objects.filter(token=t).update(enabled=False)
                        disabled_count += 1
                    except Exception:
                        pass
                continue
        return {'success': success, 'failures': max(0, len(errors)), 'disabled': disabled_count, 'errors': errors} if return_details else success


@csrf_exempt
def register_device(request: HttpRequest):
    """Registra/atualiza um dispositivo push (permite acesso anônimo para apps móveis).

    Espera JSON/POST com: token (string), platform (android/ios/web), app_version, device_info, app_id.
    """
    if request.method != 'POST':
        return HttpResponseForbidden()
    # Log básico em arquivo para diagnóstico
    def _log(msg: str):
        try:
            media_root = getattr(settings, 'MEDIA_ROOT', 'media')
            log_dir = os.path.join(media_root, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'push_register.log'), 'a', encoding='utf-8') as f:
                f.write(f"{timezone.now():%Y-%m-%d %H:%M:%S} | {msg}\n")
        except Exception:
            pass

    try:
        raw = request.body.decode('utf-8') if request.body else ''
    except Exception:
        raw = ''
    # Aceita POST form ou JSON. Se vier JSON, extrai campos corretamente.
    token = request.POST.get('token') or ''
    platform = (request.POST.get('platform') or '').lower()
    app_version = request.POST.get('app_version') or ''
    device_info = request.POST.get('device_info') or ''
    if not token and raw.startswith('{'):
        try:
            import json as _json
            j = _json.loads(raw)
            token = j.get('token') or token
            platform = (j.get('platform') or platform or 'android').lower()
            app_version = j.get('app_version') or j.get('version') or app_version
            # app_id/device_type ajudam a distinguir apps distintos compartilhando usuário
            device_info = j.get('device_info') or j.get('app_id') or j.get('device_type') or device_info
        except Exception:
            pass
    if not device_info:
        device_info = request.META.get('HTTP_USER_AGENT', '')[:255]
    if not platform:
        platform = 'android'
    # Sanitiza token se por engano veio JSON inteiro (erro de cliente antigo)
    if token and token.strip().startswith('{') and '"token"' in token:
        try:
            import json as _json
            parsed = _json.loads(token)
            real = parsed.get('token')
            if real:
                token = real
        except Exception:
            pass
    _log(f"register_device: user={getattr(request.user,'id',None)} method={request.method} ip={request.META.get('REMOTE_ADDR')} ua_len={len(device_info or '')} has_csrf={'csrftoken' in (request.META.get('HTTP_COOKIE') or '')} body_len={len(raw)} post_keys={[k for k in request.POST.keys()]} token_pref={(token or '')[:12]} platform={platform} app_version={app_version}")
    if not token:
        _log("register_device: token ausente")
        return JsonResponse({'ok': False, 'error': 'token ausente'}, status=400)
    # upsert por token único; se usuário não autenticado, salva com user=None
    user = request.user if request.user.is_authenticated else None
    dev, created = PushDevice.objects.update_or_create(
        token=token,
        defaults={
            'user': user,
            'platform': platform if platform in dict(PushDevice.PLATFORM_CHOICES) else 'android',
            'app_version': app_version,
            'device_info': device_info[:255],
            'enabled': True,
        }
    )
    _log(f"register_device: saved id={getattr(dev,'id',None)} created={created} user={getattr(dev.user,'id',None)}")
    try:
        count = PushDevice.objects.filter(user=user, enabled=True).count() if user else None
    except Exception:
        count = None
    return JsonResponse({'ok': True, 'created': created, 'devices_count': count})


@login_required
@comando_required
def push_test(request: HttpRequest):
    """Envia uma notificação de teste para os dispositivos do usuário atual (ou query ?user_id=)."""
    user_id = request.GET.get('user_id') or request.user.id
    try:
        from django.contrib.auth import get_user_model
        U = get_user_model();
        user = U.objects.get(pk=user_id)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'usuário inválido'}, status=400)
    tokens = list(PushDevice.objects.filter(user=user, enabled=True).values_list('token', flat=True))
    if not tokens:
        return JsonResponse({'ok': False, 'error': 'sem dispositivos'}, status=404)
    try:
        sent = enviar_push(tokens, title='GCM - Teste', body='Notificação de teste enviada com sucesso.', data={'kind': 'test'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True, 'sent': sent})


@login_required
def push_diag(request: HttpRequest):
    """Diagnóstico de ambiente de push (dev): verifica import do firebase_admin, credencial e venv.

    Retorna JSON com:
    - sys_executable: caminho do Python em uso pelo servidor
    - firebase_admin: {ok, version or error}
    - credentials_path: settings.FIREBASE_CREDENTIALS_JSON e existe?
    - devices_count: qtd de dispositivos registrados para o usuário atual
    """
    import sys, os
    resp: dict[str, object] = {
        'sys_executable': sys.executable,
        'credentials_path': getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None),
        'credentials_exists': False,
        'firebase_admin': {
            'ok': False,
            'version': None,
            'error': None,
        },
        'devices_count': 0,
    }
    try:
        from .models import PushDevice
        resp['devices_count'] = PushDevice.objects.filter(user=request.user, enabled=True).count()
    except Exception:
        pass
    try:
        import firebase_admin  # type: ignore
        resp['firebase_admin'] = {
            'ok': True,
            'version': getattr(firebase_admin, '__version__', 'unknown'),
            'error': None,
        }
    except Exception as e:  # pragma: no cover
        resp['firebase_admin'] = {
            'ok': False,
            'version': None,
            'error': str(e),
        }
    cp = resp['credentials_path']
    if isinstance(cp, str):
        resp['credentials_exists'] = os.path.exists(cp)
    return JsonResponse(resp)


@login_required
def servir_documento(request: HttpRequest, pk: int):
    """Serve documento para visualização no mobile (sem target=_blank)."""
    documento = get_object_or_404(DocumentoAssinavel, pk=pk)
    
    # Verificar se usuário tem acesso (simplificado - pode ajustar regras)
    # Por enquanto, qualquer usuário logado pode ver documentos pendentes/assinados
    
    # Determinar qual arquivo servir
    arquivo = documento.arquivo_assinado if documento.arquivo_assinado else documento.arquivo
    
    if not arquivo:
        return HttpResponse('Arquivo não encontrado.', status=404)
    
    # Retornar arquivo como FileResponse
    response = FileResponse(arquivo.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{arquivo.name}"'
    return response
