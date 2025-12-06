"""View temporária para debugar marca d'água."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from bogcmi.models import BO
from bogcmi.views_core import (
    _usuario_pode_ver_bo_sem_marca_dagua,
    _usuario_e_integrante_bo,
    _aplicar_marca_dagua_pdf,
    _gerar_pdf_bo_bytes,
    _log_bo_pdf
)

@login_required
def debug_marca_dagua(request, pk):
    """Endpoint de teste para debugar marca d'água."""
    bo = get_object_or_404(BO, pk=pk)
    
    pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, request.user)
    e_integrante = _usuario_e_integrante_bo(bo, request.user)
    
    info = f"""
    <h1>Debug Marca D'água - BO #{bo.numero or bo.pk}</h1>
    <p><strong>User:</strong> {request.user.username} (id={request.user.id})</p>
    
    <h2>Permissões:</h2>
    <p><strong>pode_ver_completo:</strong> {pode_ver_completo}</p>
    <p><strong>e_integrante:</strong> {e_integrante}</p>
    <p><strong>Deve aplicar marca:</strong> {e_integrante and not pode_ver_completo}</p>
    
    <h2>BO Info:</h2>
    <p><strong>Encarregado ID:</strong> {bo.encarregado_id} (username: {bo.encarregado.username if bo.encarregado else 'N/A'})</p>
    <p><strong>Motorista ID:</strong> {bo.motorista_id} (username: {bo.motorista.username if bo.motorista else 'N/A'})</p>
    <p><strong>CECOM ID:</strong> {bo.cecom_id} (username: {bo.cecom.username if bo.cecom else 'N/A'})</p>
    <p><strong>Auxiliar1 ID:</strong> {bo.auxiliar1_id} (username: {bo.auxiliar1.username if bo.auxiliar1 else 'N/A'})</p>
    <p><strong>Auxiliar2 ID:</strong> {bo.auxiliar2_id} (username: {bo.auxiliar2.username if bo.auxiliar2 else 'N/A'})</p>
    
    <h2>Username Check:</h2>
    <p>Username: '{request.user.username.lower()}'</p>
    <p>Em ['comandante', 'subcomandante', 'administrativo', 'moises']: {request.user.username.lower() in ['comandante', 'subcomandante', 'administrativo', 'moises']}</p>
    """
    
    return HttpResponse(info, content_type='text/html')
