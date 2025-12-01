"""Módulo principal de views separado para mitigar IndentationError intermitente.
Este arquivo contém toda a lógica original antes de ser isolada.
"""
import base64
import datetime
import re
import uuid
import os
import subprocess
import tempfile
from datetime import timedelta
from io import BytesIO
import hashlib
import secrets

from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .forms import (
    EnvolvidoForm, ApreensaoForm, AnexoApreensaoForm,
    VeiculoEnvolvidoForm, AnexoVeiculoForm, EquipeApoioForm,
    BOForm
)
from .filters import BOFilter
from .models import (
    BO, Envolvido, Anexo, Apreensao, AnexoApreensao,
    VeiculoEnvolvido, AnexoVeiculo, EquipeApoio, CadastroEnvolvido
)
from .services import proximo_numero_bo
from common.models import DocumentoAssinavel
from django.conf import settings  # garantir disponível para logger
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as _rl_canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderPM

# ================= Helpers Internos =================

def _usuario_pode_ver_bo_sem_marca_dagua(bo, user):
    """Verifica se usuário pode ver BO completo sem marca d'água consultiva.
    
    Retorna True apenas para:
    - comandante, subcomandante, administrativo (grupo comando)
    - moises
    - superuser
    
    Retorna False para integrantes do BO (encarregado/motorista/auxiliares/cecom)
    que devem ver versão com marca d'água "APENAS CONSULTIVO".
    """
    if not user.is_authenticated:
        return False
    
        rc = subprocess.run([wk_path, *options, tmp_html_path, tmp_pdf_path], capture_output=True, text=True)
    if user.is_superuser:
        return True
    
    # Usuários do grupo comando
    username_lower = user.username.lower()
    if username_lower in ['comandante', 'subcomandante', 'administrativo', 'moises']:
        return True
    
    # Todos os outros (incluindo integrantes) veem com marca d'água
    return False


def _usuario_e_integrante_bo(bo, user):
    """Verifica se usuário é integrante do BO (encarregado/motorista/auxiliares/cecom)."""
    if not user.is_authenticated:
        return False
    
    return user.id in [
        bo.encarregado_id,
        bo.motorista_id,
        bo.auxiliar1_id,
        bo.auxiliar2_id,
        bo.cecom_id
    ]


def _aplicar_marca_dagua_pdf(pdf_bytes):
    """Temporariamente retorna o PDF original sem marca d'água.

    Observação: a função original foi corrompida; evitamos quebrar o fluxo
    até restaurar a implementação correta de marca d'água.
    """
    return pdf_bytes


def _find_wkhtmltopdf_path():
    """Tenta encontrar o binário wkhtmltopdf em vários locais conhecidos.
    Retorna caminho ou None.
    """
    # 1) Settings
    path_cfg = getattr(settings, 'WKHTMLTOPDF_CMD', '') or ''
    if path_cfg and os.path.exists(path_cfg):
        return path_cfg
    # 2) Caminhos comuns Windows
    common_paths = [
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    # 3) PATH
    try:
        import shutil
        found = shutil.which('wkhtmltopdf')
        if found:
            return found
    except Exception:
        pass
    return None


def _gerar_pdf_bo_bytes(bo, request):
    """Gera PDF idêntico ao HTML final armazenado em bo.documento_html.

    Ordem de tentativas:
      1. wkhtmltopdf (pdfkit) – melhor fidelidade (renderização web real)
      2. WeasyPrint
      3. xhtml2pdf (pisa)
      4. Subprocess (tenta novamente 1 e 2 dentro do venv)
    Lança Exception se todas falharem.
    """
    if not bo.documento_html:
        raise ValueError("BO sem documento_html para geração de PDF")

    # Garantir HTML completo: se já contém <html> manter, senão embrulhar.
    html_body = bo.documento_html
    if '<html' not in html_body.lower():
        html_body = (
            "<!doctype html><html lang='pt-br'><head><meta charset='utf-8'>"
            "<style>html,body{font-size:16px}</style>"
            "</head><body>" + html_body + "</body></html>"
        )

    base_url = request.build_absolute_uri('/')
    # Ajustar referências a /static/ para caminhos de arquivo locais quando possível (wkhtmltopdf network error)
    try:
        static_root = getattr(settings, 'STATIC_ROOT', '')
        if static_root and os.path.isdir(static_root):
            def _static_src_repl(match):
                rel = match.group(1)
                local_path = os.path.join(static_root, rel.replace('/', os.sep))
                if os.path.exists(local_path):
                    # mantém aspas de abertura/fechamento corretamente
                    return f"src='file:///{local_path.replace(os.sep,'/')}'"
                return match.group(0)
            def _static_href_repl(match):
                rel = match.group(1)
                local_path = os.path.join(static_root, rel.replace('/', os.sep))
                if os.path.exists(local_path):
                    return f"href='file:///{local_path.replace(os.sep,'/')}'"
                return match.group(0)
            # Substituir src="/static/..." e href="/static/..."
            html_body_local = re.sub(r"src=['\"]/static/(.+?)['\"]", _static_src_repl, html_body)
            html_body_local = re.sub(r"href=['\"]/static/(.+?)['\"]", _static_href_repl, html_body_local)
            if html_body_local:
                html_body = html_body_local
    except Exception as _adj_e:
        _log_bo_pdf(f"Ajuste static falhou: {_adj_e}")
    # Injetar <base href> caso não exista para resolver links relativos
    if '<head' in html_body.lower() and '<base ' not in html_body.lower():
        html_body = re.sub(r'<head(.*?)>', lambda m: f"<head{m.group(1)}><base href='{base_url}'>", html_body, count=1, flags=re.I)

    # 1) wkhtmltopdf (pdfkit + fallback direto)
    wk_bin_detected = _find_wkhtmltopdf_path()
    if wk_bin_detected:
        # Log versão do binário
        try:
            ver_proc = subprocess.run([wk_bin_detected, '-V'], capture_output=True, text=True, timeout=10)
            _log_bo_pdf(f"Detectado wkhtmltopdf: {wk_bin_detected} version={ver_proc.stdout.strip() or ver_proc.stderr.strip()}")
        except Exception as e_ver:
            _log_bo_pdf(f"Falha ao obter versão wkhtmltopdf: {e_ver}")
        # pdfkit primeiro
        try:
            import pdfkit  # type: ignore
            options = {
                'enable-local-file-access': '',
                'encoding': 'UTF-8',
                'page-size': 'A4',
                'margin-top': '10mm', 'margin-bottom': '12mm', 'margin-left': '10mm', 'margin-right': '10mm',
                # Evitar alterações de mídia; seguir estilos padrão
                # 'print-media-type': '',
                # Deixar smart shrinking habilitado para melhor ajuste do layout existente
                # 'disable-smart-shrinking': '',
                'zoom': '1.0',
                'dpi': '96',
                'load-error-handling': 'ignore',
                # Remover viewport/minimum-font-size para não forçar escalas
                # 'viewport-size': '1280x1024',
                # 'minimum-font-size': '12',
            }
            config = pdfkit.configuration(wkhtmltopdf=wk_bin_detected)
            pdf_bytes = pdfkit.from_string(html_body, False, options=options, configuration=config)
            if pdf_bytes:
                _log_bo_pdf(f"pdfkit OK ({len(pdf_bytes)} bytes)")
                return pdf_bytes
        except Exception as e_pdfkit:
            _log_bo_pdf(f"pdfkit falhou usando {wk_bin_detected}: {e_pdfkit}")
        # Execução direta
        try:
            with tempfile.TemporaryDirectory() as td:
                html_f = os.path.join(td, 'doc.html'); pdf_f = os.path.join(td, 'out.pdf')
                with open(html_f,'w',encoding='utf-8') as f: f.write(html_body)
                cmd = [
                    wk_bin_detected,
                    '--enable-local-file-access',
                    '--encoding', 'utf-8',
                    '--page-size','A4',
                    '--margin-top','10mm','--margin-bottom','12mm','--margin-left','10mm','--margin-right','10mm',
                    '--zoom','1.0',
                    '--dpi','96',
                    '--load-error-handling','ignore',
                    # sem viewport/minimum-font-size para manter o layout original do BO
                    html_f, pdf_f
                ]
                # Timeout reduzido para 60s em produção; se travar/demorar muito, aborta e tenta fallback
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0 and os.path.exists(pdf_f):
                    with open(pdf_f,'rb') as pf: pdf_bytes = pf.read()
                    if pdf_bytes:
                        _log_bo_pdf(f"wkhtmltopdf direto OK ({len(pdf_bytes)} bytes)")
                        return pdf_bytes
                stderr_tail = (proc.stderr or '')[-300:]
                stdout_tail = (proc.stdout or '')[-120:]
                _log_bo_pdf(f"wkhtmltopdf direto falhou rc={proc.returncode} stderr={stderr_tail} stdout={stdout_tail}")
        except subprocess.TimeoutExpired:
            _log_bo_pdf(f"wkhtmltopdf direto TIMEOUT (60s) - PDF muito complexo ou sistema lento")
        except Exception as e_dir:
            _log_bo_pdf(f"wkhtmltopdf direto exception: {e_dir}")
    else:
        _log_bo_pdf("wkhtmltopdf não encontrado (configure WKHTMLTOPDF_CMD ou instale o binário)")

    # 2) WeasyPrint (pula se desabilitado)
    if not getattr(settings, 'PDF_DISABLE_WEASYPRINT', False):
        try:
            from weasyprint import HTML  # type: ignore
            return HTML(string=html_body, base_url=base_url).write_pdf()
        except Exception as e_wp:
            _log_bo_pdf(f"WeasyPrint falhou: {e_wp}")
    else:
        _log_bo_pdf("WeasyPrint desabilitado por configuração (PDF_DISABLE_WEASYPRINT)")

    # 3) xhtml2pdf
    try:
        from xhtml2pdf import pisa  # type: ignore
        result = BytesIO()
        status = pisa.CreatePDF(html_body, dest=result, encoding='utf-8')
        if status.err:
            raise RuntimeError(status.err)
        return result.getvalue()
    except Exception as e_pisa:
        _log_bo_pdf(f"xhtml2pdf falhou: {e_pisa}")

    # 4) Subprocess (pdfkit ou weasyprint no venv)
    try:
        from django.conf import settings as _s
        base_dir = getattr(_s, 'BASE_DIR', os.getcwd())
        # Detectar Python do venv em Windows e Linux
        candidates = [
            # Windows venvs
            os.path.join(base_dir, '.venv', 'Scripts', 'python.exe'),
            os.path.join(base_dir, 'venv', 'Scripts', 'python.exe'),
            # Linux/macOS venvs
            os.path.join(base_dir, '.venv', 'bin', 'python'),
            os.path.join(base_dir, 'venv', 'bin', 'python'),
        ]
        venv_python = next((p for p in candidates if os.path.exists(p)), None)
        if not venv_python:
            # Tentar localizar via variável de ambiente VIRTUAL_ENV
            venv_env = os.environ.get('VIRTUAL_ENV')
            if venv_env:
                cand2 = [
                    os.path.join(venv_env, 'Scripts', 'python.exe'),
                    os.path.join(venv_env, 'bin', 'python'),
                ]
                venv_python = next((p for p in cand2 if os.path.exists(p)), None)
            if not venv_python:
                raise RuntimeError(f"python venv não encontrado; candidates={candidates} VIRTUAL_ENV={venv_env or ''}")
        with tempfile.TemporaryDirectory() as td:
            html_f = os.path.join(td, 'doc.html')
            pdf_f = os.path.join(td, 'out.pdf')
            with open(html_f,'w',encoding='utf-8') as f: f.write(html_body)
            # Passar explicitamente caminho do wkhtmltopdf se detectado para dentro do subprocess
            wk_path = _find_wkhtmltopdf_path() or ''
            script = (
                "import sys,os; html,pdf,wk=sys.argv[1:4]; data=open(html,encoding='utf-8').read(); ok=False;\n"
                "# Tentativa pdfkit com caminho explícito\n"
                "try:\n import pdfkit; cfg = pdfkit.configuration(wkhtmltopdf=wk or None); pdfkit.from_string(data,pdf,configuration=cfg); ok=True\nexcept Exception as e: pass\n"
                "if not ok:\n try:\n  import weasyprint; weasyprint.HTML(string=data).write_pdf(pdf); ok=True\n except Exception as e: pass\n"
                "sys.exit(0 if ok else 2)"
            )
            script_path = os.path.join(td,'gen.py')
            with open(script_path,'w',encoding='utf-8') as sf: sf.write(script)
            proc = subprocess.run([venv_python, script_path, html_f, pdf_f, wk_path], capture_output=True, text=True, timeout=90)
            if proc.returncode != 0 or not os.path.exists(pdf_f):
                raise RuntimeError(f"subprocess rc={proc.returncode} err={proc.stderr[-180:]} out={proc.stdout[-80:]} wkhtmltopdf={wk_path or 'NA'} venv_python={venv_python}")
            with open(pdf_f,'rb') as pdfd: return pdfd.read()
    except Exception as e_sub:
        _log_bo_pdf(f"Subprocess falhou: {e_sub}")
        raise RuntimeError(f"Falha total geração PDF: {e_sub}")

def _log_bo_pdf(msg: str):
    """Escreve log de debug da geração de PDF (ignora falhas silenciosamente)."""
    try:
        media_root = getattr(settings, 'MEDIA_ROOT', 'media')
        log_dir = os.path.join(media_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, 'bo_pdf_debug.log')
        with open(path, 'a', encoding='utf-8', errors='ignore') as f:
            f.write(f"{timezone.now():%Y-%m-%d %H:%M:%S} | {msg}\n")
    except Exception:
        # última tentativa: print no console dev
        try:
            print('[BO_PDF]', msg)
        except Exception:
            pass

# ================= DOCUMENTO BO =================
@login_required
def visualizar_documento_bo(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    
    # Verificar permissão de acesso
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, request.user)
    e_integrante = _usuario_e_integrante_bo(bo, request.user)
    
    # Apenas comando/moises ou integrantes podem ver
    if not pode_ver_completo and not e_integrante:
        return HttpResponseForbidden('Você não tem permissão para visualizar este documento.')
    
    # Passar flag de modo consultivo para o template
    context = {
        'bo': bo,
        'modo_consultivo': e_integrante and not pode_ver_completo
    }
    
    return render(request, 'bogcmi/visualizar_documento_bo.html', context)

@login_required
def baixar_documento_bo(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    if not bo.documento_html:
        return HttpResponse('Documento não gerado.', content_type='text/plain')
    response = HttpResponse(bo.documento_html, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename=BO_{bo.numero or bo.pk}.html'
    response['Content-Length'] = len(bo.documento_html.encode('utf-8'))
    response['Content-Type'] = 'text/html; charset=utf-8'
    return response

@login_required
def servir_documento_assinado(request, doc_id):
    """Serve documento assinado com controle de acesso e marca d'água consultiva.
    
    Esta view intercepta o acesso a documentos assinados e aplica marca d'água
    para integrantes do BO que não sejam do comando.
    """
    from common.models import DocumentoAssinavel
    
    # Buscar documento assinado
    documento = get_object_or_404(DocumentoAssinavel, pk=doc_id)
    
    # Buscar BO relacionado pelo número extraído do nome do arquivo
    try:
        bo_numero = documento.bo_numero
        if not bo_numero:
            _log_bo_pdf(f"Não foi possível extrair número do BO do documento {doc_id}")
            return HttpResponseForbidden('Número do BO não encontrado.')
        bo = BO.objects.get(numero=bo_numero)
    except BO.DoesNotExist:
        _log_bo_pdf(f"BO {bo_numero} não encontrado para documento {doc_id}")
        return HttpResponseForbidden('BO não encontrado.')
    
    # Verificar permissão de acesso
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, request.user)
    e_integrante = _usuario_e_integrante_bo(bo, request.user)
    
    _log_bo_pdf(f"Documento assinado #{doc_id} - User: {request.user.username} - Completo: {pode_ver_completo} - Integrante: {e_integrante}")
    
    # Apenas comando/moises ou integrantes podem ver
    if not pode_ver_completo and not e_integrante:
        _log_bo_pdf(f"Acesso negado ao documento assinado para user {request.user.username}")
        return HttpResponseForbidden('Você não tem permissão para visualizar este documento.')
    
    # Ler arquivo PDF assinado
    arquivo = documento.arquivo_assinado if documento.arquivo_assinado else documento.arquivo
    if not arquivo:
        return HttpResponse('Documento não encontrado.', status=404)
    
    try:
        # Ler bytes do PDF
        arquivo.seek(0)
        pdf_bytes = arquivo.read()
        
        # Aplicar marca d'água se for integrante mas não comando/moises
        if e_integrante and not pode_ver_completo:
            _log_bo_pdf(f"Aplicando marca d'água no documento assinado para user {request.user.username}")
            pdf_bytes = _aplicar_marca_dagua_pdf(pdf_bytes)
            filename_suffix = '_CONSULTIVO'
        else:
            _log_bo_pdf(f"Documento assinado sem marca d'água para user {request.user.username}")
            filename_suffix = ''
        
        # Retornar PDF
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"BO_{bo.numero or bo.pk}_ASSINADO{filename_suffix}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'no-store'
        return response
        
    except Exception as e:
        _log_bo_pdf(f"Erro ao servir documento assinado: {e}")
        return HttpResponse('Erro ao processar documento.', status=500)

@login_required
def baixar_documento_bo_pdf(request, pk):
    """Força o download do PDF fiel ao HTML salvo do BO.
    Usa o mesmo pipeline de despacho para garantir identidade visual.
    Aplica marca d'água 'APENAS CONSULTIVO' para integrantes do BO.
    """
    bo = get_object_or_404(BO, pk=pk)
    
    # Verificar permissão de acesso
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, request.user)
    e_integrante = _usuario_e_integrante_bo(bo, request.user)
    
    _log_bo_pdf(f"Download PDF BO#{pk} - User: {request.user.username} - Completo: {pode_ver_completo} - Integrante: {e_integrante}")
    
    # Apenas comando/moises ou integrantes podem baixar
    if not pode_ver_completo and not e_integrante:
        _log_bo_pdf(f"Acesso negado para user {request.user.username}")
        return HttpResponseForbidden('Você não tem permissão para baixar este documento.')
    
    if not bo.documento_html:
        return HttpResponse('Documento não gerado.', content_type='text/plain', status=404)
    try:
        pdf_bytes = _gerar_pdf_bo_bytes(bo, request)
        
        # Aplicar marca d'água se for integrante mas não comando/moises
        if e_integrante and not pode_ver_completo:
            _log_bo_pdf(f"Aplicando marca d'água para user {request.user.username}")
            pdf_bytes = _aplicar_marca_dagua_pdf(pdf_bytes)
        else:
            _log_bo_pdf(f"Sem marca d'água para user {request.user.username} (comando/moises)")
        
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename_suffix = '_CONSULTIVO' if (e_integrante and not pode_ver_completo) else ''
        resp['Content-Disposition'] = f"attachment; filename=BO_{bo.numero or bo.pk}{filename_suffix}.pdf"
        resp['Cache-Control'] = 'no-store'
        return resp
    except Exception as e:
        # fallback mínimo (texto plano dentro de PDF simples) só para não ficar sem nada
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            buf = BytesIO(); from reportlab.lib.units import mm
            c = canvas.Canvas(buf, pagesize=A4)
            c.setTitle(f"BO {bo.numero or bo.pk}")
            text = re.sub(r'<[^>]+>', ' ', bo.documento_html)
            text = re.sub(r'\s+', ' ', text)
            tw = c.beginText(15*mm, 280*mm)
            tw.setFont('Helvetica', 9)
            width, height = A4
            max_chars = 110
            while text:
                line = text[:max_chars]; text = text[max_chars:]
                tw.textLine(line.strip())
                if tw.getY() < 15*mm:
                    c.drawText(tw); c.showPage(); tw = c.beginText(15*mm, 280*mm); tw.setFont('Helvetica', 9)
            c.drawText(tw); c.showPage(); c.save()
            pdf_fallback = buf.getvalue(); buf.close()
            resp = HttpResponse(pdf_fallback, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=BO_{bo.numero or bo.pk}_fallback.pdf"
            resp['X-PDF-Fallback'] = 'reportlab-min'
            return resp
        except Exception as e2:
            return HttpResponse(f'Falha ao gerar PDF: {e}; fallback: {e2}', status=500)

# ================= ENVOLVIDO OFFLINE =================
@login_required
def envolvido_form_offline(request):
    bo_id = request.GET.get('bo')
    bo = BO.objects.filter(id=bo_id).first() if bo_id else None
    return render(request, 'bogcmi/envolvido_form_offline.html', {'bo': bo})

@csrf_exempt
@login_required
def envolvido_import_offline(request):
    if request.method != 'POST':
        return JsonResponse({'error':'Método não permitido'}, status=405)
    bo_id = request.POST.get('bo')
    if not bo_id:
        return JsonResponse({'error':'BO ausente'}, status=400)
    bo = BO.objects.filter(id=bo_id).first()
    if not bo:
        return JsonResponse({'error':'BO não encontrado'}, status=404)
    raw = request.POST.get('payload') or '[]'
    try:
        import json
        data = json.loads(raw)
    except Exception as e:
        return JsonResponse({'error':'JSON inválido','detail':str(e)}, status=400)
    if not isinstance(data, list):
        data = [data]
    importados = 0; ignorados = 0
    def parse_data(dt_raw):
        if not dt_raw:
            return None
        if isinstance(dt_raw, datetime.date):
            return dt_raw
        txt = str(dt_raw).strip()
        from datetime import datetime as _dt
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                return _dt.strptime(txt, fmt).date()
            except Exception:
                continue
        return None
    for item in data:
        try:
            nome = (item.get('nome') or '').strip()
            cond = (item.get('condicao') or '').strip()
            if not nome or not cond:
                ignorados += 1; continue
            envolvido = Envolvido(
                bo=bo,
                nome=nome,
                nome_social=item.get('nome_social','') or '',
                telefone=item.get('telefone','') or '',
                condicao=cond,
                outra_condicao=item.get('outra_condicao','') or '',
                cep=item.get('cep','') or '',
                endereco=item.get('endereco','') or '',
                numero=item.get('numero','') or '',
                ponto_referencia=item.get('ponto_referencia','') or '',
                bairro=item.get('bairro','') or '',
                uf=(item.get('uf') or 'SP')[:2],
                cidade=item.get('cidade','') or '',
                data_nascimento=parse_data(item.get('data_nascimento')),
                estado_civil=item.get('estado_civil','') or '',
                pais_natural=item.get('pais_natural','') or '',
                uf_natural=(item.get('uf_natural') or 'SP')[:2],
                cidade_natural=item.get('cidade_natural','') or '',
                rg=item.get('rg','') or '',
                cpf=item.get('cpf','') or '',
                outro_documento=item.get('outro_documento','') or '',
                nome_pai=item.get('nome_pai','') or '',
                nome_mae=item.get('nome_mae','') or '',
                genero=item.get('genero','') or '',
                cutis=item.get('cutis','') or '',
                profissao=item.get('profissao','') or '',
                vulgo=item.get('vulgo','') or '',
                sinais=item.get('sinais','') or '',
                dados_adicionais=item.get('dados_adicionais','') or '',
                providencia=item.get('providencia','') or '',
            )
            b64 = item.get('assinatura_base64')
            if b64 and b64.startswith('data:image'):
                try:
                    header, enc = b64.split(',',1)
                    binary = base64.b64decode(enc)
                    envolvido.assinatura = ContentFile(binary, name=f"assin_{uuid.uuid4().hex}.png")
                except Exception:
                    pass
            envolvido.save()
            importados += 1
        except Exception:
            ignorados += 1
    return JsonResponse({'importados':importados,'ignorados':ignorados,'total':len(data)})

# ================= ENVOLVIDO CRUD =================
@login_required
def envolvido_form(request, pk=None):
    envolvido = Envolvido.objects.get(pk=pk) if pk else None
    if request.method == 'POST':
        form = EnvolvidoForm(request.POST, request.FILES, instance=envolvido)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.bo:
                bo_param = request.GET.get('bo')
                obj.bo = get_object_or_404(BO, pk=bo_param) if bo_param else get_or_create_bo_em_edicao(request.user)
            obj.save()
            # Sincroniza/atualiza o CadastroEnvolvido por CPF (para auto-preenchimento futuro)
            try:
                cpf_norm = ''.join([c for c in (obj.cpf or '') if c.isdigit()])
                if cpf_norm:
                    cad, _created = CadastroEnvolvido.objects.get_or_create(cpf_normalizado=cpf_norm, defaults={
                        'cpf': obj.cpf or cpf_norm,
                        'nome': obj.nome,
                    })
                    # Atualiza campos principais a cada salvamento
                    update_map = {
                        'nome': obj.nome,
                        'nome_social': obj.nome_social,
                        'telefone': obj.telefone,
                        'cep': obj.cep,
                        'endereco': obj.endereco,
                        'numero': obj.numero,
                        'ponto_referencia': obj.ponto_referencia,
                        'bairro': obj.bairro,
                        'uf': obj.uf,
                        'cidade': obj.cidade,
                        'data_nascimento': obj.data_nascimento,
                        'estado_civil': obj.estado_civil,
                        'pais_natural': obj.pais_natural,
                        'uf_natural': obj.uf_natural,
                        'cidade_natural': obj.cidade_natural,
                        'rg': obj.rg,
                        'cpf': obj.cpf or cpf_norm,
                        'outro_documento': obj.outro_documento,
                        'cnh': obj.cnh,
                        'categoria_cnh': obj.categoria_cnh,
                        'data_validacao_cnh': obj.data_validacao_cnh,
                        'cutis': obj.cutis,
                        'genero': obj.genero,
                        'profissao': obj.profissao,
                        'trabalho': obj.trabalho,
                        'vulgo': obj.vulgo,
                        'nome_pai': obj.nome_pai,
                        'nome_mae': obj.nome_mae,
                        'sinais': obj.sinais,
                        'dados_adicionais': obj.dados_adicionais,
                    }
                    for k, v in update_map.items():
                        setattr(cad, k, v)
                    cad.save()
                    # Vincula o Envolvido ao cadastro base (facilita consultas)
                    if obj.cadastro_id != cad.id:
                        obj.cadastro = cad
                        obj.save(update_fields=['cadastro'])
            except Exception:
                pass
            return redirect(f"{reverse('bogcmi:envolvido_list')}?bo={obj.bo_id}")
        else:
            try:
                from types import SimpleNamespace
                data_ns = SimpleNamespace(**{k: v for k, v in request.POST.items()})
            except Exception:
                data_ns = envolvido
            return render(request, 'bogcmi/envolvido_form.html', {'form': form, 'envolvido': data_ns})
    form = EnvolvidoForm(instance=envolvido)
    return render(request, 'bogcmi/envolvido_form.html', {'form': form, 'envolvido': envolvido})

# ================= API: Cadastro Envolvido por CPF =================
@login_required
def api_cadastro_envolvido_lookup(request):
    cpf = (request.GET.get('cpf') or '').strip()
    cpf_norm = ''.join([c for c in cpf if c.isdigit()])
    if not cpf_norm:
        return JsonResponse({'found': False, 'error': 'CPF ausente'}, status=400)
    # 1) Tenta no cadastro persistente
    cad = CadastroEnvolvido.objects.filter(cpf_normalizado=cpf_norm).first()
    # 2) Fallback: último Envolvido com mesmo CPF (formatações diferentes)
    if not cad:
        env = Envolvido.objects.filter(cpf__regex=r"\d").order_by('-id')
        for e in env[:200]:  # varredura limitada
            try:
                if ''.join([c for c in (e.cpf or '') if c.isdigit()]) == cpf_norm:
                    cad = CadastroEnvolvido(
                        cpf=e.cpf, cpf_normalizado=cpf_norm, nome=e.nome,
                        nome_social=e.nome_social, telefone=e.telefone, cep=e.cep,
                        endereco=e.endereco, numero=e.numero, ponto_referencia=e.ponto_referencia,
                        bairro=e.bairro, uf=e.uf, cidade=e.cidade, data_nascimento=e.data_nascimento,
                        estado_civil=e.estado_civil, pais_natural=e.pais_natural, uf_natural=e.uf_natural,
                        cidade_natural=e.cidade_natural, rg=e.rg, outro_documento=e.outro_documento,
                        cnh=e.cnh, categoria_cnh=e.categoria_cnh, data_validacao_cnh=e.data_validacao_cnh,
                        cutis=e.cutis, genero=e.genero, profissao=e.profissao, trabalho=e.trabalho,
                        vulgo=e.vulgo, nome_pai=e.nome_pai, nome_mae=e.nome_mae, sinais=e.sinais,
                        dados_adicionais=e.dados_adicionais,
                    )
                    break
            except Exception:
                continue
    if not cad:
        return JsonResponse({'found': False})
    def _fmt_date(d):
        try:
            return d.strftime('%Y-%m-%d') if d else ''
        except Exception:
            return ''
    payload = {
        'found': True,
        'nome': cad.nome,
        'nome_social': cad.nome_social,
        'telefone': cad.telefone,
        'cep': cad.cep,
        'endereco': cad.endereco,
        'numero': cad.numero,
        'ponto_referencia': cad.ponto_referencia,
        'bairro': cad.bairro,
        'uf': cad.uf,
        'cidade': cad.cidade,
        'data_nascimento': _fmt_date(cad.data_nascimento),
        'estado_civil': cad.estado_civil,
        'pais_natural': cad.pais_natural,
        'uf_natural': cad.uf_natural,
        'cidade_natural': cad.cidade_natural,
        'rg': cad.rg,
        'cpf': cad.cpf or cpf,
        'outro_documento': cad.outro_documento,
        'cnh': cad.cnh,
        'categoria_cnh': cad.categoria_cnh,
        'data_validacao_cnh': _fmt_date(cad.data_validacao_cnh),
        'cutis': cad.cutis,
        'genero': cad.genero,
        'profissao': cad.profissao,
        'trabalho': cad.trabalho,
        'vulgo': cad.vulgo,
        'nome_pai': cad.nome_pai,
        'nome_mae': cad.nome_mae,
        'sinais': cad.sinais,
        'dados_adicionais': cad.dados_adicionais,
    }
    return JsonResponse(payload)

@login_required
def envolvido_list(request):
    bo_id = request.GET.get('bo')
    bo = get_object_or_404(BO, pk=bo_id) if bo_id else BO.objects.filter(status='EDICAO', encarregado=request.user).first()
    envolvidos = Envolvido.objects.filter(bo=bo).order_by('-id') if bo else []
    return render(request, 'bogcmi/envolvido_list.html', {'envolvidos': envolvidos, 'bo': bo})

# ================= LAYOUT / BO PRINCIPAL =================
@login_required
def novo_layout(request):
    from users.models import Perfil
    perfis = Perfil.objects.select_related('user').order_by('matricula')
    perfis_ctx = [{'id': p.user.id, 'matricula': p.matricula, 'nome': p.user.get_full_name() or p.user.username} for p in perfis]
    from viaturas.models import Viatura
    from taloes.models import CodigoOcorrencia
    viaturas = Viatura.objects.filter(ativo=True).order_by('prefixo')
    viaturas_ctx = [{'id': v.id, 'prefixo': v.prefixo} for v in viaturas]
    codigos = CodigoOcorrencia.objects.order_by('sigla')
    codigos_ctx = [{'id': c.id, 'sigla': c.sigla, 'descricao': c.descricao} for c in codigos]
    tipos_solicitacao = ['Selecione...','Outras','Via CECOM','Despacho com a Ocorrência','Ordem de Serviço']
    bo = None
    force_novo = request.GET.get('novo') == '1'
    talao_param = request.GET.get('talao')
    # Se veio de um talão específico, sempre criar um novo e vincular
    created_new = False
    if talao_param:
        try:
            from taloes.models import Talao, CodigoOcorrencia as _Cod
            talao_obj = Talao.objects.filter(pk=talao_param).first()
        except Exception:
            talao_obj = None
        numero = proximo_numero_bo()
        bo = BO.objects.create(encarregado=request.user, status='EDICAO', numero=numero, emissao=timezone.now(), talao=talao_obj)
        # Pré-preencher campos do BO a partir do Talão/Plantão
        try:
            changed = False
            if talao_obj:
                # Viatura
                if talao_obj.viatura_id and not bo.viatura_id:
                    bo.viatura_id = talao_obj.viatura_id; changed = True
                # Ocorrência
                if talao_obj.codigo_ocorrencia_id:
                    try:
                        cod = _Cod.objects.get(id=talao_obj.codigo_ocorrencia_id)
                        bo.cod_natureza = cod.sigla or bo.cod_natureza
                        bo.natureza = f"{cod.sigla} - {cod.descricao}".strip(" -") or bo.natureza
                        changed = True
                    except Exception:
                        pass
                # Local
                if talao_obj.local_bairro and not bo.bairro:
                    bo.bairro = talao_obj.local_bairro; changed = True
                if talao_obj.local_rua and not bo.rua:
                    bo.rua = talao_obj.local_rua; changed = True
                # KM
                if talao_obj.km_inicial is not None and bo.km_inicio is None:
                    bo.km_inicio = talao_obj.km_inicial; changed = True
                if talao_obj.km_final is not None and bo.km_final is None:
                    bo.km_final = talao_obj.km_final; changed = True
                # Horários (usar início/fim do Talão, quando disponíveis)
                try:
                    if getattr(talao_obj, 'iniciado_em', None) and not bo.horario_inicial:
                        bo.horario_inicial = timezone.localtime(talao_obj.iniciado_em).time() if timezone.is_aware(talao_obj.iniciado_em) else talao_obj.iniciado_em.time()
                        changed = True
                except Exception:
                    pass
                try:
                    if getattr(talao_obj, 'encerrado_em', None) and not bo.horario_final:
                        bo.horario_final = timezone.localtime(talao_obj.encerrado_em).time() if timezone.is_aware(talao_obj.encerrado_em) else talao_obj.encerrado_em.time()
                        changed = True
                except Exception:
                    pass
                # Equipe do talão (se informada)
                if talao_obj.encarregado_id and bo.encarregado_id != talao_obj.encarregado_id:
                    bo.encarregado_id = talao_obj.encarregado_id; changed = True
                if talao_obj.motorista_id and not bo.motorista_id:
                    bo.motorista_id = talao_obj.motorista_id; changed = True
                if talao_obj.auxiliar1_id and not bo.auxiliar1_id:
                    bo.auxiliar1_id = talao_obj.auxiliar1_id; changed = True
                if talao_obj.auxiliar2_id and not bo.auxiliar2_id:
                    bo.auxiliar2_id = talao_obj.auxiliar2_id; changed = True

                # Fallback: se faltarem papéis, tenta inferir do Plantão ativo da mesma viatura
                try:
                    from cecom.models import PlantaoCECOM, PlantaoParticipante
                    plantao = PlantaoCECOM.objects.filter(ativo=True, viatura_id=talao_obj.viatura_id).order_by('-inicio').first()
                    if plantao:
                        # Mapear função -> campo
                        func_map = {
                            'ENC': 'encarregado_id',
                            'MOT': 'motorista_id',
                            'AUX1': 'auxiliar1_id',
                            'AUX2': 'auxiliar2_id',
                        }
                        parts = plantao.participantes.select_related('usuario').filter(saida_em__isnull=True)
                        for p in parts:
                            attr = func_map.get(p.funcao)
                            if not attr:
                                continue
                            if getattr(bo, attr) is None:
                                setattr(bo, attr, p.usuario_id)
                                changed = True
                except Exception:
                    pass

            if changed:
                bo.save()
        except Exception:
            # Em caso de falha no prefill, segue com BO criado sem bloquear fluxo
            pass
        created_new = True
    else:
        if not force_novo:
            bo = BO.objects.filter(status='EDICAO', encarregado=request.user).order_by('-emissao').first()
        if not bo:
            numero = proximo_numero_bo()
            bo = BO.objects.create(encarregado=request.user, status='EDICAO', numero=numero, emissao=timezone.now())
            created_new = True
    # Se foi explicitamente solicitado novo (novo=1) ou veio de talão, redireciona para rota padronizada de edição
    if created_new and (force_novo or talao_param):
        # Propaga sinal de criação para página de edição resetar formulário automaticamente
        from django.urls import reverse as _rev
        # Mantém referência do talão para que o front evite reset e preserve pré-preenchidos
        extra = f"&talao={talao_param}" if talao_param else ""
        return redirect(f"{_rev('bogcmi:editar', args=[bo.pk])}?novo=1{extra}")
    ctx = {'viaturas': viaturas_ctx,'codigos_ocorrencia': codigos_ctx,'tipos_solicitacao': tipos_solicitacao,'perfis': perfis_ctx,'bo': bo}
    return render(request, 'bogcmi/novo.html', ctx)

@login_required
def duplicar_bo(request, pk=None):
    bo_orig = get_object_or_404(BO, pk=pk) if pk else BO.objects.filter(encarregado=request.user).order_by('-emissao').first()
    if not bo_orig:
        return redirect('bogcmi:novo')
    numero_novo = proximo_numero_bo()
    campos_copiar = ['natureza','cod_natureza','solicitante','rua','numero_endereco','bairro','cidade','uf','referencia','viatura_id','motorista_id','auxiliar1_id','auxiliar2_id','cecom_id','km_inicio','km_final','horario_inicial','horario_final','duracao']
    dados = {c: getattr(bo_orig, c) for c in campos_copiar}
    novo = BO.objects.create(encarregado=request.user, status='EDICAO', numero=numero_novo, emissao=timezone.now(), **dados)
    return redirect(f"{reverse('bogcmi:editar', args=[novo.id])}?duplicado=1")

@csrf_exempt
@require_POST
@login_required
def criar_bo_automatico(request):
    user = request.user
    ref = request.META.get('HTTP_REFERER', '')
    if '/bogcmi/novo' not in ref:
        bo = BO.objects.filter(status='EDICAO', encarregado=user).first()
        if not bo:
            return JsonResponse({'success': False})
        return JsonResponse({'success': True, 'id': bo.id, 'numero_bogcm': bo.numero})
    bo = BO.objects.filter(status='EDICAO', encarregado=user).first()
    if not bo:
        numero = proximo_numero_bo()
        bo = BO.objects.create(encarregado=user, status='EDICAO', numero=numero, emissao=timezone.now())
    return JsonResponse({'success': True, 'id': bo.id, 'numero_bogcm': bo.numero})

def pode_editar(bo, user):
    if bo.status == 'EDICAO':
        return True
    if bo.status == 'FINALIZADO':
        return timezone.now() <= (bo.edit_deadline or timezone.now())
    return user.has_perm('bogcmi.override_edicao')

def get_or_create_bo_em_edicao(user):
    bo = BO.objects.filter(status='EDICAO', encarregado=user).order_by('-emissao').first()
    if bo:
        return bo
    numero = proximo_numero_bo()
    return BO.objects.create(encarregado=user, status='EDICAO', numero=numero, emissao=timezone.now())

@login_required
def bo_list(request):
    qs = BO.objects.select_related('viatura','encarregado','motorista','cecom','auxiliar1','auxiliar2')
    order = request.GET.get('order')
    if order == 'cod':
        qs = qs.order_by('cod_natureza','-emissao')
    elif order == '-cod':
        qs = qs.order_by('-cod_natureza','-emissao')
    else:
        qs = qs.order_by('-emissao')
    f = BOFilter(request.GET, queryset=qs)
    page = Paginator(f.qs, 15).get_page(request.GET.get('page'))
    try:
        from users.models import Perfil
        perfis = Perfil.objects.select_related('user').order_by('matricula')
    except Exception:
        perfis = []
    try:
        from viaturas.models import Viatura
        viaturas = Viatura.objects.filter(ativo=True).order_by('prefixo')
    except Exception:
        viaturas = []
    # Códigos para o select de filtro
    try:
        from taloes.models import CodigoOcorrencia
        codigos = CodigoOcorrencia.objects.all().order_by('sigla')
    except Exception:
        codigos = []
    # Mapear documentos assinados (BOGCMI) por número para facilitar exibição de link direto
    from common.models import DocumentoAssinavel
    numeros = [b.numero for b in page if b.numero]
    docs = DocumentoAssinavel.objects.filter(tipo='BOGCMI', status='ASSINADO')
    doc_map = {}
    for d in docs:
        num = d.bo_numero
        if num and num in numeros:
            doc_map[num] = d
    return render(request, 'bogcmi/list.html', {'filter': f,'page': page,'perfis': perfis,'viaturas': viaturas,'doc_map': doc_map,'codigos': codigos})

@login_required
def bo_table(request):
    qs = BO.objects.select_related('viatura','encarregado','motorista','cecom','auxiliar1','auxiliar2')
    order = request.GET.get('order')
    if order == 'cod':
        qs = qs.order_by('cod_natureza','-emissao')
    elif order == '-cod':
        qs = qs.order_by('-cod_natureza','-emissao')
    else:
        qs = qs.order_by('-emissao')
    f = BOFilter(request.GET, queryset=qs)
    page = Paginator(f.qs, 15).get_page(request.GET.get('page'))
    from common.models import DocumentoAssinavel
    numeros = [b.numero for b in page if b.numero]
    docs = DocumentoAssinavel.objects.filter(tipo='BOGCMI', status='ASSINADO')
    doc_map = {}
    for d in docs:
        num = d.bo_numero
        if num and num in numeros:
            doc_map[num] = d
    # codigos não é necessário aqui pois o select está no filterbar (fora da partial)
    return render(request, 'bogcmi/_table.html', {'page': page,'doc_map': doc_map})

@login_required
def bo_novo(request):
    if request.method == 'POST':
        form = BOForm(request.POST)
        if form.is_valid():
            bo = form.save(commit=False)
            bo.status = 'EDICAO'
            bo.save()
            return redirect('bogcmi:editar', pk=bo.pk)
    else:
        form = BOForm()
    return render(request, 'bogcmi/form.html', {'form': form, 'titulo': 'Novo BO'})

@login_required
def bo_editar(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    if bo.status != 'EDICAO':
        bo.status = 'EDICAO'
        bo.save(update_fields=['status'])
    # Fallback de pré-preenchimento quando vindo de Talão e algum campo ainda estiver vazio
    try:
        talao_qs = request.GET.get('talao')
        if talao_qs and bo.talao_id:
            ta = bo.talao
            changed = False
            if bo.km_inicio is None and ta and ta.km_inicial is not None:
                bo.km_inicio = ta.km_inicial; changed = True
            if bo.km_final is None and ta and ta.km_final is not None:
                bo.km_final = ta.km_final; changed = True
            # Horários derivados do Talão (se ainda não definidos no BO)
            try:
                if (bo.horario_inicial is None) and ta and getattr(ta, 'iniciado_em', None):
                    bo.horario_inicial = timezone.localtime(ta.iniciado_em).time() if timezone.is_aware(ta.iniciado_em) else ta.iniciado_em.time()
                    changed = True
            except Exception:
                pass
            try:
                if (bo.horario_final is None) and ta and getattr(ta, 'encerrado_em', None):
                    bo.horario_final = timezone.localtime(ta.encerrado_em).time() if timezone.is_aware(ta.encerrado_em) else ta.encerrado_em.time()
                    changed = True
            except Exception:
                pass
            if changed:
                # Salva apenas os campos que efetivamente foram preenchidos
                fields = []
                if bo.km_inicio is not None and 'km_inicio' not in fields:
                    fields.append('km_inicio')
                if bo.km_final is not None and 'km_final' not in fields:
                    fields.append('km_final')
                if bo.horario_inicial is not None and 'horario_inicial' not in fields:
                    fields.append('horario_inicial')
                if bo.horario_final is not None and 'horario_final' not in fields:
                    fields.append('horario_final')
                bo.save(update_fields=fields or None)
    except Exception:
        pass
    if not pode_editar(bo, request.user):
        return HttpResponseForbidden('Prazo encerrado ou sem permissão')
    envolvidos = Envolvido.objects.filter(bo=bo)
    apreensoes = Apreensao.objects.filter(bo=bo)
    veiculos = VeiculoEnvolvido.objects.filter(bo=bo)
    equipes = EquipeApoio.objects.filter(bo=bo)
    anexos = Anexo.objects.filter(bo=bo, envolvido__isnull=True)
    from viaturas.models import Viatura
    from taloes.models import CodigoOcorrencia
    from users.models import Perfil
    viaturas = Viatura.objects.filter(ativo=True).order_by('prefixo')
    perfis = Perfil.objects.select_related('user').order_by('matricula')
    codigos_ocorrencia = CodigoOcorrencia.objects.all().order_by('sigla')
    tipos_solicitacao = ["Atendimento", "Apoio", "Ronda", "Fiscalização", "Outros"]
    
    # Verificar se o usuário logado é o encarregado do BO
    usuario_e_encarregado = (bo.encarregado == request.user)
    
    return render(request, 'bogcmi/novo.html', {
        'bo': bo,
        'envolvidos': envolvidos,
        'apreensoes': apreensoes,
        'veiculos': veiculos,
        'equipes': equipes,
        'anexos': anexos,
        'viaturas': viaturas,
        'perfis': [{'id': p.user.id, 'matricula': p.matricula, 'nome': p.user.get_full_name() or p.user.username} for p in perfis],
        'codigos_ocorrencia': [{'id': c.id, 'sigla': c.sigla, 'descricao': c.descricao} for c in codigos_ocorrencia],
        'tipos_solicitacao': tipos_solicitacao,
        'titulo': f'Editar BO #{bo.numero or bo.pk}',
        'usuario_e_encarregado': usuario_e_encarregado,
    })

@login_required
def bo_finalizar(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    
    # Verificar se o usuário é o encarregado do BO
    if bo.encarregado != request.user:
        from django.contrib import messages
        messages.error(request, "Apenas o Encarregado pode realizar essa ação.")
        return redirect('bogcmi:editar', pk=bo.pk)
    
    if not bo.numero:
        bo.numero = proximo_numero_bo()
    agora = timezone.now()
    bo.finalizado_em = agora
    bo.edit_deadline = agora + timedelta(minutes=30)
    bo.status = 'FINALIZADO'
    bo.save()
    return redirect('bogcmi:editar', pk=bo.pk)

@login_required
def bo_despachar_cmt(request, pk):
    """Altera status para DESPACHO_CMT e cria DocumentoAssinavel (tipo BOGCMI) pendente para assinatura do comando."""
    bo = get_object_or_404(BO, pk=pk)
    
    # Verificar se o usuário é o encarregado do BO
    if bo.encarregado != request.user:
        from django.contrib import messages
        messages.error(request, "Apenas o Encarregado pode realizar essa ação.")
        return redirect('bogcmi:lista')
    
    if bo.status not in ('FINALIZADO','DESPACHO_CMT'):
        return HttpResponseForbidden('BO precisa estar FINALIZADO para despacho.')
    # Garante documento_html idêntico ao Visualizar Documento
    if not bo.documento_html:
        bo.documento_html = _montar_documento_bo_html(request, bo)
    bo.status = 'DESPACHO_CMT'
    bo.save(update_fields=['status','documento_html'])
    # Gerar PDF fiel; se falhar não cria documento pendente (evita PDF "zuado")
    try:
        pdf_bytes = _gerar_pdf_bo_bytes(bo, request)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        _log_bo_pdf(f"ABORT despacho bo_id={bo.id}: {e}\n{trace}")
        from django.contrib import messages
        messages.error(request, f'Falha ao gerar PDF do BO para despacho: {e}. O documento foi salvo mas não pôde ser despachado. Verifique o log bo_pdf_debug.log.')
        return redirect('bogcmi:editar', pk=bo.pk)
    from django.core.files.base import ContentFile
    doc_exist = DocumentoAssinavel.objects.filter(tipo='BOGCMI', usuario_origem=bo.encarregado, arquivo__icontains=f"{bo.pk}_").first()
    # Simples: sempre criar novo registro para manter histórico
    doc = DocumentoAssinavel.objects.create(
        tipo='BOGCMI',
        usuario_origem=bo.encarregado,
        status='PENDENTE',
    )
    # Nome do arquivo agora acompanha o número real do BO (ex.: 2025-10-06_164343_BOGCM_64-2025.pdf)
    import re as _re
    numero_clean = (bo.numero or '').strip()
    if numero_clean:
        # sanitizar: manter dígitos, letras, -, _
        numero_clean = _re.sub(r'[^0-9A-Za-z_-]+', '', numero_clean.replace(' ', '').replace('/', '-'))
    else:
        numero_clean = f"ID{bo.pk}"
    # Novo padrão: documentos/origem/<ANO>/<timestamp>_<TIPO>_<numero>_<docid>_<hash8>.pdf
    import hashlib
    base_ts = timezone.now()
    hash8 = hashlib.sha256((f"{numero_clean}-{doc.id}-{base_ts.timestamp()}" ).encode()).hexdigest()[:8]
    nome_pdf = f"{base_ts:%Y%m%d_%H%M%S}_BOGCMI_{numero_clean}_{doc.id}_{hash8}.pdf"
    caminho = f"{base_ts:%Y}/{nome_pdf}"
    # Tentar salvar o PDF e registrar logs detalhados (ajuda em prod/AWS)
    try:
        _log_bo_pdf(f"Despacho BO#{bo.id} numero={numero_clean} doc_id={doc.id} caminho_relativo={caminho}")
        doc.arquivo.save(caminho, ContentFile(pdf_bytes), save=True)
        # Registrar informações do storage e caminho físico quando possível
        try:
            storage = doc.arquivo.storage
            base_loc = getattr(storage, 'location', '')
            file_path = ''
            if base_loc:
                file_path = os.path.join(base_loc, doc.arquivo.name)
            _log_bo_pdf(f"PDF salvo: name={doc.arquivo.name} storage_location={base_loc} file_path={file_path} size={len(pdf_bytes)}")
        except Exception as e_info:
            _log_bo_pdf(f"PDF salvo, mas falha ao obter info de storage: {e_info}")
    except Exception as e_save:
        from django.contrib import messages
        _log_bo_pdf(f"ERRO ao salvar PDF despacho BO#{bo.id}: {e_save}")
        messages.error(request, f"Falha ao salvar PDF despachado: {e_save}")
        return redirect('bogcmi:editar', pk=bo.pk)
    from django.contrib import messages
    messages.success(request, 'Documento despachado para assinatura do Comando.')
    # Permanecer na página da lista (ou voltar para a página que originou a ação) em vez de abrir edição
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('bogcmi:lista')

@login_required
def bo_excluir(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    autorizado = (bo.status == 'EDICAO' and bo.encarregado_id == request.user.id) or request.user.is_superuser or request.user.has_perm('bogcmi.delete_bo')
    if not autorizado:
        return HttpResponseForbidden('Sem permissão para excluir este BO')
    bo.delete()
    return redirect('bogcmi:lista')

@csrf_exempt
@require_POST
@login_required
def salvar_bo(request, pk):
    bo = get_object_or_404(BO, pk=pk)
    if not pode_editar(bo, request.user):
        return HttpResponseForbidden('Sem permissao para editar')
    data = request.POST.dict()
    bo.solicitante = data.get('solicitante', bo.solicitante)
    
    # Adicionar telefone_solicitante se existir no modelo
    if hasattr(bo, 'telefone_solicitante'):
        bo.telefone_solicitante = data.get('telefone_solicitante', bo.telefone_solicitante)
    
    bo.rua = data.get('rua', bo.rua)
    bo.numero_endereco = data.get('numero', bo.numero_endereco)
    bo.bairro = data.get('bairro', bo.bairro)
    bo.cidade = data.get('cidade', bo.cidade)
    bo.uf = data.get('uf', bo.uf)
    bo.referencia = data.get('referencia', bo.referencia)
    km_inicio_raw = data.get('km_inicio') or data.get('km-inicio')
    km_final_raw = data.get('km_final') or data.get('km-final')
    horario_inicial_raw = data.get('horario_inicial') or data.get('horario-inicial')
    horario_final_raw = data.get('horario_final') or data.get('horario-final')
    try:
        if km_inicio_raw is not None:
            bo.km_inicio = int(km_inicio_raw) if km_inicio_raw != '' else None
    except (ValueError, TypeError):
        bo.km_inicio = None
    try:
        if km_final_raw is not None:
            bo.km_final = int(km_final_raw) if km_final_raw != '' else None
    except (ValueError, TypeError):
        bo.km_final = None
    if horario_inicial_raw is not None:
        bo.horario_inicial = horario_inicial_raw or None
    if horario_final_raw is not None:
        bo.horario_final = horario_final_raw or None
    if data.get('duracao'):
        bo.duracao = data.get('duracao')
    elif bo.horario_inicial and bo.horario_final and not bo.duracao:
        try:
            h1, m1 = map(int, str(bo.horario_inicial).split(':')[:2])
            h2, m2 = map(int, str(bo.horario_final).split(':')[:2])
            t1 = h1*60+m1; t2 = h2*60+m2
            if t2 < t1: t2 += 1440
            dif = t2 - t1
            bo.duracao = f"{dif//60:02d}:{dif%60:02d}"
        except Exception:
            pass
    viatura_id = data.get('viatura') or data.get('viatura_id') or None
    if viatura_id:
        bo.viatura_id = viatura_id
    
    # Atualizar GCMs Envolvidos
    motorista_id = data.get('motorista') or data.get('motorista_id') or None
    encarregado_id = data.get('encarregado') or data.get('encarregado_id') or None
    cecom_id = data.get('cecom') or data.get('cecom_id') or None
    auxiliar1_id = data.get('auxiliar1') or data.get('auxiliar1_id') or None
    auxiliar2_id = data.get('auxiliar2') or data.get('auxiliar2_id') or None
    
    if motorista_id:
        bo.motorista_id = motorista_id
    elif motorista_id == '':
        bo.motorista_id = None
        
    if encarregado_id:
        bo.encarregado_id = encarregado_id
        
    if cecom_id:
        bo.cecom_id = cecom_id
    elif cecom_id == '':
        bo.cecom_id = None
        
    if auxiliar1_id:
        bo.auxiliar1_id = auxiliar1_id
    elif auxiliar1_id == '':
        bo.auxiliar1_id = None
        
    if auxiliar2_id:
        bo.auxiliar2_id = auxiliar2_id
    elif auxiliar2_id == '':
        bo.auxiliar2_id = None
    
    codigo_id = data.get('codigo_ocorrencia')
    if codigo_id:
        try:
            from taloes.models import CodigoOcorrencia
            cod = CodigoOcorrencia.objects.get(id=codigo_id)
            bo.cod_natureza = cod.sigla
            bo.natureza = f"{cod.sigla} - {cod.descricao}"
        except Exception:
            pass
    else:
        if data.get('cod_natureza') and data.get('natureza'):
            bo.cod_natureza = data.get('cod_natureza').strip()
            bo.natureza = data.get('natureza').strip()
        elif (not bo.natureza) and data.get('natureza'):
            bo.natureza = data.get('natureza').strip()
    if (not bo.cod_natureza) and bo.natureza and ' - ' in bo.natureza:
        bo.cod_natureza = bo.natureza.split(' - ', 1)[0].strip()
    # Campos de Finalização (salvamento parcial, sem finalizar)
    if data.get('numero_bopc') is not None:
        bo.numero_bopc = data.get('numero_bopc')
    if data.get('numero_tco') is not None:
        bo.numero_tco = data.get('numero_tco')
    if data.get('autoridade_policial') is not None:
        bo.autoridade_policial = data.get('autoridade_policial')
    if data.get('escrivao') is not None:
        bo.escrivao = data.get('escrivao')
    if data.get('algemas') is not None:
        bo.algemas = data.get('algemas')
    if data.get('grande_vulto') is not None:
        bo.grande_vulto = data.get('grande_vulto')
    # Aceita tanto 'finalizada_em' (nome do input) quanto 'local_finalizacao'
    if data.get('finalizada_em') is not None:
        bo.local_finalizacao = data.get('finalizada_em')
    if data.get('local_finalizacao') is not None:
        bo.local_finalizacao = data.get('local_finalizacao')
    if data.get('flagrante') is not None:
        bo.flagrante = data.get('flagrante')

    bo.providencias = data.get('historico', bo.providencias)
    bo.save()
    
    # Retornar dados atualizados incluindo GCMs
    response_data = {
        'success': True,
        'cod_natureza': bo.cod_natureza,
        'natureza': bo.natureza,
        'km_inicio': bo.km_inicio,
        'km_final': bo.km_final,
        'horario_inicial': bo.horario_inicial,
        'horario_final': bo.horario_final,
        'duracao': bo.duracao,
        'viatura_id': bo.viatura_id,
        'motorista_id': bo.motorista_id,
        'encarregado_id': bo.encarregado_id,
        'cecom_id': bo.cecom_id,
        'auxiliar1_id': bo.auxiliar1_id,
        'auxiliar2_id': bo.auxiliar2_id,
        'numero_bopc': bo.numero_bopc,
        'numero_tco': bo.numero_tco,
        'autoridade_policial': bo.autoridade_policial,
        'escrivao': bo.escrivao,
        'algemas': bo.algemas,
        'grande_vulto': bo.grande_vulto,
        'local_finalizacao': bo.local_finalizacao,
        'flagrante': bo.flagrante,
    }
    
    return JsonResponse(response_data)

@login_required
def envolvido_excluir(request, pk):
    envolvido = get_object_or_404(Envolvido, pk=pk)
    bo_id = getattr(envolvido, 'bo_id', None)
    envolvido.delete()
    if bo_id:
        return redirect(f"{reverse('bogcmi:envolvido_list')}?bo={bo_id}")
    return redirect('bogcmi:envolvido_list')

# ================= APREENSAO =================
@login_required
def apreensao_form(request):
    bo_param = request.GET.get('bo')
    bo = get_object_or_404(BO, pk=bo_param) if bo_param else get_or_create_bo_em_edicao(request.user)
    if request.method == 'POST':
        form = ApreensaoForm(request.POST)
        if form.is_valid():
            ap = form.save(commit=False)
            ap.bo = bo
            ap.save()
            return redirect(f"{reverse('bogcmi:apreensao_lista')}?bo={bo.id}")
    else:
        form = ApreensaoForm()
    return render(request, 'bogcmi/apreensao_form.html', {'form': form})

@login_required
def apreensao_lista(request):
    bo_id = request.GET.get('bo')
    bo = get_object_or_404(BO, pk=bo_id) if bo_id else BO.objects.filter(status='EDICAO', encarregado=request.user).first()
    apreensoes = Apreensao.objects.filter(bo=bo) if bo else []
    return render(request, 'bogcmi/apreensao_lista.html', {'apreensoes': apreensoes, 'bo': bo})

@login_required
def apreensao_excluir(request, pk):
    apreensao = get_object_or_404(Apreensao, pk=pk)
    bo_id = apreensao.bo_id
    apreensao.delete()
    return redirect(f"{reverse('bogcmi:apreensao_lista')}?bo={bo_id}")

@login_required
def apreensao_anexo_form(request, pk):
    apreensao = get_object_or_404(Apreensao, pk=pk)
    if request.method == 'POST':
        form = AnexoApreensaoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.apreensao = apreensao
            anexo.save()
            return redirect(f"{reverse('bogcmi:apreensao_lista')}?bo={apreensao.bo_id}")
    else:
        form = AnexoApreensaoForm()
    return render(request, 'bogcmi/apreensao_anexo_form.html', {'form': form, 'apreensao': apreensao})

@login_required
def apreensao_anexo_excluir(request, pk):
    anexo = get_object_or_404(AnexoApreensao, pk=pk)
    apreensao_id = anexo.apreensao.id
    anexo.delete()
    return redirect('bogcmi:apreensao_lista')

# ================= VEICULO =================
@login_required
def veiculo_form(request, pk=None):
    veiculo = get_object_or_404(VeiculoEnvolvido, pk=pk) if pk else None
    if request.method == 'POST':
        form = VeiculoEnvolvidoForm(request.POST, instance=veiculo)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                bo_param = request.GET.get('bo')
                obj.bo = get_object_or_404(BO, pk=bo_param) if bo_param else get_or_create_bo_em_edicao(request.user)
            obj.save()
            return redirect(f"{reverse('bogcmi:veiculo_lista')}?bo={obj.bo_id}")
    else:
        form = VeiculoEnvolvidoForm(instance=veiculo)
    return render(request, 'bogcmi/veiculo_form.html', {'form': form, 'veiculo': veiculo})

@login_required
def veiculo_lista(request):
    bo_id = request.GET.get('bo')
    bo = get_object_or_404(BO, pk=bo_id) if bo_id else BO.objects.filter(status='EDICAO', encarregado=request.user).first()
    veiculos = VeiculoEnvolvido.objects.filter(bo=bo).order_by('-id') if bo else []
    return render(request, 'bogcmi/veiculo_lista.html', {'veiculos': veiculos, 'bo': bo})

@login_required
def veiculo_excluir(request, pk):
    veiculo = get_object_or_404(VeiculoEnvolvido, pk=pk)
    bo_id = veiculo.bo_id
    veiculo.delete()
    return redirect(f"{reverse('bogcmi:veiculo_lista')}?bo={bo_id}")

@login_required
def veiculo_anexo_form(request, pk):
    veiculo = get_object_or_404(VeiculoEnvolvido, pk=pk)
    if request.method == 'POST':
        form = AnexoVeiculoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save(commit=False)
            anexo.veiculo = veiculo
            anexo.save()
            return redirect(f"{reverse('bogcmi:veiculo_lista')}?bo={veiculo.bo_id}")
    else:
        form = AnexoVeiculoForm()
    return render(request, 'bogcmi/veiculo_anexo_form.html', {'form': form, 'veiculo': veiculo})

@login_required
def veiculo_anexo_excluir(request, pk):
    anexo = get_object_or_404(AnexoVeiculo, pk=pk)
    anexo.delete()
    return redirect('bogcmi:veiculo_lista')

# ================= EQUIPE APOIO =================
@login_required
def equipe_form(request, pk=None):
    equipe = get_object_or_404(EquipeApoio, pk=pk) if pk else None
    if request.method == 'POST':
        form = EquipeApoioForm(request.POST, instance=equipe)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.pk:
                bo_param = request.GET.get('bo')
                obj.bo = get_object_or_404(BO, pk=bo_param) if bo_param else get_or_create_bo_em_edicao(request.user)
            obj.save()
            return redirect(f"{reverse('bogcmi:equipe_lista')}?bo={obj.bo_id}")
    else:
        form = EquipeApoioForm(instance=equipe)
    return render(request, 'bogcmi/equipe_form.html', {'form': form, 'equipe': equipe})

@login_required
def equipe_lista(request):
    bo = BO.objects.filter(status='EDICAO', encarregado=request.user).first()
    equipes = EquipeApoio.objects.filter(bo=bo).order_by('-id') if bo else []
    return render(request, 'bogcmi/equipe_lista.html', {'equipes': equipes})

@login_required
def equipe_excluir(request, pk):
    equipe = get_object_or_404(EquipeApoio, pk=pk)
    bo_id = equipe.bo_id
    equipe.delete()
    return redirect(f"{reverse('bogcmi:equipe_lista')}?bo={bo_id}")

# ================= ANEXOS =================
@login_required
def anexo_form(request):
    from .models import Anexo
    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')
        if descricao and arquivo:
            bo_param = request.GET.get('bo')
            bo = get_object_or_404(BO, pk=bo_param) if bo_param else get_or_create_bo_em_edicao(request.user)
            Anexo.objects.create(descricao=descricao, arquivo=arquivo, bo=bo)
            return redirect(f"{reverse('bogcmi:anexo_lista')}?bo={bo.id}")
    return render(request, 'bogcmi/anexo_form.html')

@login_required
def anexo_lista(request):
    from .models import Anexo
    bo_id = request.GET.get('bo')
    bo = get_object_or_404(BO, pk=bo_id) if bo_id else BO.objects.filter(status='EDICAO', encarregado=request.user).first()
    anexos = Anexo.objects.filter(bo=bo, envolvido__isnull=True).order_by('-id') if bo else []
    return render(request, 'bogcmi/anexo_lista.html', {'anexos': anexos, 'bo': bo})

@login_required
def anexo_excluir(request, pk):
    from .models import Anexo
    anexo = Anexo.objects.get(pk=pk)
    bo_id = anexo.bo_id
    anexo.delete()
    if bo_id:
        return redirect(f"{reverse('bogcmi:anexo_lista')}?bo={bo_id}")
    return redirect('bogcmi:anexo_lista')

@login_required
def autosave_finalizacao(request):
    if request.method == 'POST':
        request.session['finalizacao_data'] = request.POST
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
@login_required
def finalizar_bo(request):
    if request.method == 'POST':
        user = request.user
        
        # Verificar se o encarregado tem assinatura cadastrada
        perfil = getattr(user, 'perfil', None)
        tem_assinatura = False
        if perfil:
            tem_assinatura = bool(getattr(perfil, 'assinatura_img', None) or getattr(perfil, 'assinatura_digital', None))
        if not tem_assinatura:
            return JsonResponse({'success': False, 'error': 'Cadastre sua assinatura no "Meu Perfil" antes de finalizar o BO.'}, status=400)
        
        data = request.POST.dict()
        bo_id = data.get('bo_id')
        bo = get_object_or_404(BO, pk=bo_id) if bo_id else BO.objects.filter(status='EDICAO', encarregado=user).order_by('-emissao').first()
        if not bo:
            return JsonResponse({'error': 'BO não encontrado'}, status=404)
        # Validação de campos obrigatórios (Código de Ocorrência, Rua, Cidade)
        missing = []
        # Código de Ocorrência pode vir como id (codigo_ocorrencia) ou como sigla (cod_natureza) já definida
        has_codigo = bool((data.get('codigo_ocorrencia') or '').strip() or (data.get('cod_natureza') or '').strip() or (bo.cod_natureza or '').strip())
        if not has_codigo:
            missing.append('codigo_ocorrencia')
        rua_eff = (data.get('rua') or bo.rua or '').strip()
        if not rua_eff:
            missing.append('rua')
        cidade_in = (data.get('cidade') or '').strip()
        cidade_eff = cidade_in or (bo.cidade or '').strip() or 'Ibiúna'
        if not cidade_eff:
            missing.append('cidade')
        if missing:
            return JsonResponse({'success': False, 'error': 'Preencha os campos obrigatórios: Código de Ocorrência, Rua e Cidade.', 'fields': missing}, status=400)
        bo.numero_bopc = data.get('numero_bopc','')
        bo.numero_tco = data.get('numero_tco','')
        bo.autoridade_policial = data.get('autoridade_policial','')
        bo.escrivao = data.get('escrivao','')
        bo.algemas = data.get('algemas','')
        bo.grande_vulto = data.get('grande_vulto','')
        bo.finalizado_em = timezone.now()
        bo.local_finalizacao = data.get('finalizada_em','')
        bo.flagrante = data.get('flagrante','')
        bo.solicitante = data.get('solicitante', bo.solicitante)
        # Aplicar rua e cidade efetivas após validação
        bo.rua = rua_eff
        bo.numero_endereco = data.get('numero', bo.numero_endereco)
        bo.bairro = data.get('bairro', bo.bairro)
        bo.cidade = cidade_eff
        bo.uf = data.get('uf', bo.uf)
        bo.referencia = data.get('referencia', bo.referencia)
        try:
            bo.km_inicio = int(data.get('km_inicio')) if data.get('km_inicio') else bo.km_inicio
        except Exception:
            pass
        try:
            bo.km_final = int(data.get('km_final')) if data.get('km_final') else bo.km_final
        except Exception:
            pass
        bo.horario_inicial = data.get('horario_inicial') or bo.horario_inicial
        bo.horario_final = data.get('horario_final') or bo.horario_final
        incoming_dur = data.get('duracao')
        if incoming_dur:
            bo.duracao = incoming_dur
        if (not bo.duracao) and bo.horario_inicial and bo.horario_final:
            try:
                h1, m1 = map(int, str(bo.horario_inicial).split(':')[:2])
                h2, m2 = map(int, str(bo.horario_final).split(':')[:2])
                t1 = h1*60+m1; t2 = h2*60+m2
                if t2 < t1: t2 += 1440
                dif = t2 - t1
                bo.duracao = f"{dif//60:02d}:{dif%60:02d}"
            except Exception:
                pass
        viatura_id = data.get('viatura') or None
        if viatura_id:
            bo.viatura_id = viatura_id
        motorista_id = data.get('motorista') or None
        if motorista_id:
            bo.motorista_id = motorista_id
        aux1_id = data.get('auxiliar1') or None
        if aux1_id:
            bo.auxiliar1_id = aux1_id
        aux2_id = data.get('auxiliar2') or None
        if aux2_id:
            bo.auxiliar2_id = aux2_id
        cecom_id = data.get('cecom') or None
        if cecom_id:
            bo.cecom_id = cecom_id
        codigo_id = data.get('codigo_ocorrencia')
        if codigo_id:
            try:
                from taloes.models import CodigoOcorrencia
                cod = CodigoOcorrencia.objects.get(id=codigo_id)
                bo.cod_natureza = cod.sigla
                bo.natureza = f"{cod.sigla} - {cod.descricao}"
            except Exception:
                pass
        else:
            if data.get('cod_natureza') and data.get('natureza'):
                bo.cod_natureza = data.get('cod_natureza').strip()
                bo.natureza = data.get('natureza').strip()
            elif (not bo.natureza) and data.get('natureza'):
                bo.natureza = data.get('natureza').strip()
        if (not bo.cod_natureza) and bo.natureza and ' - ' in bo.natureza:
            bo.cod_natureza = bo.natureza.split(' - ', 1)[0].strip()
        bo.providencias = data.get('historico', bo.providencias)
        bo.status = 'FINALIZADO'
        bo.save()
        bo.documento_html = _montar_documento_bo_html(request, bo)
        bo.save()
    return JsonResponse({'success': True, 'cod_natureza': bo.cod_natureza, 'natureza': bo.natureza})

def validar_documento_bo(request, pk, token):
    bo = get_object_or_404(BO, pk=pk)
    status_validacao = False
    motivo = ''
    if not bo.validacao_token:
        motivo = 'Documento sem token registrado.'
    elif bo.validacao_token != token:
        motivo = 'Token inválido.'
    else:
        # Recalcula hash
        if not bo.validacao_hash:
            motivo = 'Hash ausente.'
        else:
            try:
                resumo = f"BO:{bo.numero}|ID:{bo.id}|ENC:{bo.encarregado_id}|TS:{int(bo.finalizado_em.timestamp()) if bo.finalizado_em else ''}"
                calc = hashlib.sha256(resumo.encode()).hexdigest()
                if calc == bo.validacao_hash:
                    status_validacao = True
                else:
                    motivo = 'Hash divergente.'
            except Exception as e:
                motivo = f'Erro ao validar: {e}'
    if request.headers.get('accept','').startswith('application/json'):
        return JsonResponse({'ok': status_validacao,'motivo': motivo,'bo': bo.numero,'finalizado_em': bo.finalizado_em})
    return render(request, 'bogcmi/validacao_resultado.html', {'ok': status_validacao,'motivo': motivo,'bo': bo})

# ================= VEÍCULO OFFLINE =================
@login_required
def veiculo_form_offline(request):
    bo_id = request.GET.get('bo')
    bo = BO.objects.filter(id=bo_id).first() if bo_id else None
    return render(request, 'bogcmi/veiculo_form_offline.html', {'bo': bo})

@csrf_exempt
@login_required
def veiculo_import_offline(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    bo_id = request.POST.get('bo')
    if not bo_id:
        return JsonResponse({'error': 'BO ausente'}, status=400)
    bo = BO.objects.filter(id=bo_id).first()
    if not bo:
        return JsonResponse({'error': 'BO não encontrado'}, status=404)
    raw = request.POST.get('payload') or '[]'
    try:
        import json
        data = json.loads(raw)
    except Exception as e:
        return JsonResponse({'error': 'JSON inválido', 'detail': str(e)}, status=400)
    if not isinstance(data, list):
        data = [data]
    campos_permitidos = {'marca','modelo','placa','renavam','numero_chassi','numero_motor','placa_cidade','placa_estado','cor','ano_modelo','ano_fabricacao','semaforo','tipo_pista','tipo_acidente','tempo','iluminacao','proprietario','cpf','cnpj','cnh','categoria_cnh','validade_cnh','situacao_veiculo','observacao_situacao','danos_identificados','apreensao_ait','apreensao_crr','apreensao_responsavel_guincho','apreensao_destino'}
    importados=0; ignorados=0
    from datetime import datetime as _dt
    for item in data:
        try:
            marca = (item.get('marca') or '').strip()
            modelo = (item.get('modelo') or '').strip()
            if not marca or not modelo:
                ignorados += 1; continue
            veic = VeiculoEnvolvido(bo=bo)
            for k,v in item.items():
                if k not in campos_permitidos:
                    continue
                if k == 'validade_cnh' and v:
                    try:
                        v_dt=None
                        for fmt in ('%Y-%m-%d','%d/%m/%Y'):
                            try:
                                v_dt=_dt.strptime(str(v), fmt).date(); break
                            except Exception: continue
                        setattr(veic, k, v_dt)
                        continue
                    except Exception:
                        setattr(veic, k, None)
                        continue
                setattr(veic, k, v)
            if veic.danos_identificados:
                veic.danos_identificados = ','.join([p.strip() for p in veic.danos_identificados.split(',') if p.strip()])
            veic.save(); importados += 1
        except Exception:
            ignorados += 1
    return JsonResponse({'importados': importados, 'ignorados': ignorados, 'total': len(data)})

__all__ = [n for n in globals().keys() if not n.startswith('_')]

def _gerar_qr_code_para_bo(request, bo):
    try:
        import qrcode
    except Exception:
        return None
    # Gera token/hash se ausentes
    mudou=False
    if not bo.validacao_token:
        bo.validacao_token = secrets.token_hex(16)
        mudou=True
    resumo = f"BO:{bo.numero}|ID:{bo.id}|ENC:{bo.encarregado_id}|TS:{int(bo.finalizado_em.timestamp()) if bo.finalizado_em else ''}"
    novo_hash = hashlib.sha256(resumo.encode()).hexdigest()
    if bo.validacao_hash != novo_hash:
        bo.validacao_hash = novo_hash
        mudou=True
    if mudou:
        bo.save(update_fields=['validacao_token','validacao_hash'])
    # URL de validação (preferir SITE_BASE_URL se definido; senão request)
    from django.conf import settings as _s
    base = getattr(_s, 'SITE_BASE_URL', '') or ''
    if not base:
        base = request.build_absolute_uri('/')[:-1]
    url_validacao = f"{base}/bogcmi/validar/{bo.id}/{bo.validacao_token}/"
    img = qrcode.make(url_validacao)
    buf = BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"

# ================= HTML Helper Unificado =================
def _montar_documento_bo_html(request, bo) -> str:
    """Gera o HTML final do documento do BO (idêntico ao 'Ver Documento').

    - Carrega todos os relacionamentos necessários
    - Injeta logo/assinatura como base64 quando possível
    - Usa o template 'bogcmi/documento_bo.html'
    - Aplica CSS base e pequenos ajustes visuais
    """
    # Coleções relacionadas
    envolvidos = Envolvido.objects.filter(bo=bo)
    anexos_envolvidos = Anexo.objects.filter(envolvido__bo=bo)
    apreensoes = Apreensao.objects.filter(bo=bo)
    anexos_apreensao = AnexoApreensao.objects.filter(apreensao__bo=bo)
    veiculos = VeiculoEnvolvido.objects.filter(bo=bo)
    anexos_veiculos = AnexoVeiculo.objects.filter(veiculo__bo=bo)
    equipes = EquipeApoio.objects.filter(bo=bo)
    historico = bo.providencias
    anexos_gerais = Anexo.objects.filter(envolvido__isnull=True, bo=bo)

    # Utilitários para base64
    from django.conf import settings as _s
    import base64 as _b64, mimetypes
    def _file_to_b64(path):
        try:
            with open(path,'rb') as f:
                data=f.read()
            mt = mimetypes.guess_type(path)[0] or 'image/png'
            return f"data:{mt};base64,{_b64.b64encode(data).decode()}"
        except Exception:
            return ''

    # Logo base64 (tenta STATIC_ROOT, STATICFILES_DIRS e app/static)
    logo_b64 = ''
    possible_logo_paths = []
    static_root = getattr(_s,'STATIC_ROOT', '') or ''
    if static_root:
        possible_logo_paths.append(os.path.join(static_root,'img','logo_gcm.png'))
    for extra in getattr(_s,'STATICFILES_DIRS', []):
        possible_logo_paths.append(os.path.join(extra,'img','logo_gcm.png'))
    possible_logo_paths.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..','static','img','logo_gcm.png')))
    for pth in possible_logo_paths:
        if os.path.exists(pth):
            logo_b64 = _file_to_b64(pth)
            break

    # Assinatura base64 do encarregado (upload ou digital)
    assinatura_b64 = ''
    perf = getattr(bo.encarregado,'perfil', None)
    if perf:
        if getattr(perf,'assinatura_img', None) and getattr(perf.assinatura_img,'path',None) and os.path.exists(perf.assinatura_img.path):
            assinatura_b64 = _file_to_b64(perf.assinatura_img.path)
        elif getattr(perf,'assinatura_digital', None) and str(perf.assinatura_digital).startswith('data:image'):
            assinatura_b64 = perf.assinatura_digital

    # Gerar diagrama do veículo (imagem base64) a partir dos dados, quando houver
    def _gerar_diagrama_veiculo_base64():
        try:
            # Desenho simples do carro visto de cima com marcações
            d = Drawing(500, 200)
            # Corpo do carro
            d.add(Rect(50, 20, 400, 160, strokeColor=colors.black, fillColor=None, strokeWidth=2))
            # Portas
            d.add(Line(150, 20, 150, 180, strokeColor=colors.gray))
            d.add(Line(350, 20, 350, 180, strokeColor=colors.gray))
            # Texto título
            d.add(String(180, 185, 'Diagrama (Automóvel)', fontSize=12))
            # Marcar danos se houver texto em veículos.danos_identificados
            danos_txt = ''
            try:
                v = veiculos[0]
                danos_txt = (v.danos_identificados or '').strip()
            except Exception:
                pass
            if danos_txt:
                d.add(String(60, 5, f"Danos: {danos_txt[:80]}", fontSize=10))
            img_bytes = renderPM.drawToString(d, fmt='PNG')
            return f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
        except Exception as e:
            _log_bo_pdf(f"Falha ao gerar diagrama veiculo: {e}")
            return ''

    diagrama_base64 = _gerar_diagrama_veiculo_base64()

    # Renderização principal
    html_fragment = render_to_string('bogcmi/documento_bo.html', {
        'bo': bo,
        'envolvidos': envolvidos,
        'anexos_envolvidos': anexos_envolvidos,
        'apreensoes': apreensoes,
        'anexos_apreensao': anexos_apreensao,
        'veiculos': veiculos,
        'anexos_veiculos': anexos_veiculos,
        'equipes': equipes,
        'historico': historico,
        'anexos_gerais': anexos_gerais,
        'km_utilizada': (bo.km_final - bo.km_inicio) if (bo.km_inicio is not None and bo.km_final is not None and isinstance(bo.km_inicio, int) and isinstance(bo.km_final, int) and (bo.km_final - bo.km_inicio) >= 0) else None,
        'qr_code_base64': _gerar_qr_code_para_bo(request, bo),
        'diagrama_veiculo_base64': diagrama_base64,
    })

    # Não injetar CSS customizado aqui para preservar layout original do template
    core_css = ""

    # Substituições: logo/assinatura em base64 para cumprir renderizadores de PDF
    if logo_b64:
        def _rep_logo(match):
            tag = match.group(0)
            tag = re.sub(r'src\s*=\s*"[^"]+"', f'src="{logo_b64}"', tag)
            return tag
        html_fragment = re.sub(r'<img[^>]*logo_gcm\.png[^>]*>', _rep_logo, html_fragment, flags=re.I)
    if assinatura_b64:
        html_fragment = re.sub(r"(<div class=\"assinatura-imagem\">)\s*<img[^>]+>", f"\\1<img src=\"{assinatura_b64}\" alt=\"Assinatura\">", html_fragment, flags=re.I)

    # Não remover tags já renderizadas; render_to_string já processou o template.
    
    # Inserir diagrama no HTML se não estiver presente no template
    if diagrama_base64:
        if 'Diagrama (Automóvel)' not in html_fragment:
            bloco = f"<div class=\"section page-break-avoid\"><div class=\"section-title\">Diagrama (Automóvel)</div><img src=\"{diagrama_base64}\" alt=\"Diagrama do veículo\" style=\"max-width:100%;height:auto\"></div>"
            # Incluir antes do histórico, se existir
            html_fragment = re.sub(r'(</div>\s*<div[^>]*>\s*Histórico)', bloco + r'\1', html_fragment, flags=re.I) or (html_fragment + bloco)
    
    return core_css + html_fragment
