"""Views para gerar e servir PDFs com tokens (sem login obrigatório)."""

from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from common.models import DocumentoAssinavel, TokenAcessoPdf
from .models import BO


def _usuario_pode_ver_bo_sem_marca_dagua(bo, user):
    """Verifica se usuário pode ver BO completo sem marca d'água consultiva."""
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    username_lower = user.username.lower()
    if username_lower in ['comandante', 'subcomandante', 'administrativo', 'moises']:
        return True
    
    return False


def _usuario_e_integrante_bo(bo, user):
    """Verifica se usuário é integrante do BO."""
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
    """Aplicar marca d'água consultiva ao PDF."""
    # Por enquanto retorna original - implementação real em outro momento
    return pdf_bytes


def _log_bo_pdf(msg):
    """Log para debug de PDFs."""
    print(f"[PDF Token] {msg}")


@login_required
def gerar_token_acesso_pdf(request, doc_id):
    """Gera um token temporário para acesso a um PDF específico.
    
    Endpoint que a app mobile chama para obter um token antes de
    tentar acessar o PDF. O token é válido por 15 minutos.
    
    Returns:
        JSON: {"token": "...", "url": "/bogcmi/pdf-token/<token>/<doc_id>/"}
    """
    # Verificar se documento existe
    documento = get_object_or_404(DocumentoAssinavel, pk=doc_id)
    
    # Buscar BO relacionado
    try:
        bo_numero = documento.bo_numero
        if not bo_numero:
            return JsonResponse({"erro": "Número do BO não encontrado"}, status=400)
        bo = BO.objects.get(numero=bo_numero)
    except BO.DoesNotExist:
        return JsonResponse({"erro": "BO não encontrado"}, status=400)
    
    # Verificar permissão
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, request.user)
    e_integrante = _usuario_e_integrante_bo(bo, request.user)
    
    if not pode_ver_completo and not e_integrante:
        return JsonResponse({"erro": "Sem permissão"}, status=403)
    
    # Gerar token
    token_obj = TokenAcessoPdf.gerar_token(
        usuario=request.user,
        documento_id=doc_id,
        duracao_minutos=15
    )
    
    _log_bo_pdf(f"Token gerado para doc {doc_id} - user {request.user.username}")
    
    return JsonResponse({
        "token": token_obj.token,
        "url": f"/bogcmi/pdf-token/{token_obj.token}/{doc_id}/"
    })


def servir_documento_com_token(request, token, doc_id):
    """Serve um PDF usando token temporário (sem login obrigatório).
    
    A app mobile obtém o token via gerar_token_acesso_pdf() e depois
    acessa o PDF diretamente via este endpoint com o token.
    
    Args:
        token: Token gerado anteriormente
        doc_id: ID do DocumentoAssinavel
    """
    # Validar token
    token_obj = TokenAcessoPdf.validar_token(token, int(doc_id))
    if not token_obj:
        _log_bo_pdf(f"Tentativa de acesso com token inválido/expirado: doc_id={doc_id}")
        return HttpResponse('Token inválido ou expirado', status=403)
    
    # Buscar documento
    documento = get_object_or_404(DocumentoAssinavel, pk=doc_id)
    
    # Buscar BO para verificações
    try:
        bo_numero = documento.bo_numero
        if not bo_numero:
            return HttpResponse('Número do BO não encontrado', status=400)
        bo = BO.objects.get(numero=bo_numero)
    except BO.DoesNotExist:
        return HttpResponse('BO não encontrado', status=400)
    
    # Verificações de permissão (mesmo usuário que gerou o token)
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, token_obj.usuario)
    e_integrante = _usuario_e_integrante_bo(bo, token_obj.usuario)
    
    if not pode_ver_completo and not e_integrante:
        return HttpResponse('Acesso negado', status=403)
    
    # Ler arquivo PDF
    arquivo = documento.arquivo_assinado if documento.arquivo_assinado else documento.arquivo
    if not arquivo:
        return HttpResponse('Documento não encontrado', status=404)
    
    try:
        # Ler bytes do PDF
        arquivo.seek(0)
        pdf_bytes = arquivo.read()
        
        # Aplicar marca d'água se necessário
        if e_integrante and not pode_ver_completo:
            _log_bo_pdf(f"Aplicando marca d'água no acesso via token para user {token_obj.usuario.username}")
            pdf_bytes = _aplicar_marca_dagua_pdf(pdf_bytes)
            filename_suffix = '_CONSULTIVO'
        else:
            filename_suffix = ''
        
        # Marcar token como usado
        token_obj.marcar_como_usado()
        
        # Retornar PDF
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"BO_{bo.numero or bo.pk}_ASSINADO{filename_suffix}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Cache-Control'] = 'no-store'
        
        _log_bo_pdf(f"PDF servido via token para doc {doc_id} - user {token_obj.usuario.username}")
        
        return response
        
    except Exception as e:
        _log_bo_pdf(f"Erro ao servir documento via token: {e}")
        return HttpResponse('Erro ao processar documento', status=500)
