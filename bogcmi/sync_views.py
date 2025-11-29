import json
import uuid
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import BO
from .services import proximo_numero_bo
from common.audit_simple import record

@csrf_exempt
@login_required
def sync_offline_bos(request):  # noqa: C901
    """Endpoint isolado para sincronização de BOs offline.

    Ver documentação original em views.py. Este arquivo foi criado para contornar
    erro intermitente de IndentationError possivelmente ligado a corrupção de bytecode.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception as exc:
        return JsonResponse({'error': 'JSON inválido', 'detail': str(exc)}, status=400)

    bos_in = payload.get('bos') or []
    resultados = []

    campos_permitidos = {
        'natureza', 'cod_natureza', 'solicitante', 'endereco', 'bairro', 'cidade', 'uf', 'numero_endereco', 'rua', 'referencia',
        'km_inicio', 'km_final', 'horario_inicial', 'horario_final', 'duracao', 'numero_bopc', 'numero_tco', 'autoridade_policial',
        'escrivao', 'algemas', 'grande_vulto', 'local_finalizacao', 'flagrante', 'providencias', 'viatura_id', 'motorista_id',
        'auxiliar1_id', 'auxiliar2_id', 'cecom_id'
    }

    for item in bos_in:
        c_uuid = (item.get('client_uuid') or '').strip() or str(uuid.uuid4())
        dados = item.get('dados') or {}
        status_in = (item.get('status') or dados.get('status') or 'EDICAO').upper()
        bo_id = item.get('bo_id') or dados.get('bo_id')
        criado = False

        bo = BO.objects.filter(id=bo_id).first() if bo_id else None
        if not bo:
            bo = BO.objects.filter(client_uuid=c_uuid).first()
        if not bo:
            bo = BO(client_uuid=c_uuid, offline=True)
            # encarregado será atribuído abaixo se possível
            criado = True

        if hasattr(request, 'user') and request.user.is_authenticated and not bo.encarregado_id:
            bo.encarregado = request.user

        if criado or bo.status == 'EDICAO':
            for k, v in dados.items():
                if k not in campos_permitidos:
                    continue
                if k in {'km_inicio', 'km_final'}:
                    try:
                        v_norm = int(v) if str(v).strip() not in ('', 'None', 'null') else None
                    except (ValueError, TypeError):
                        v_norm = None
                    setattr(bo, k, v_norm)
                    continue
                if k in {'horario_inicial', 'horario_final'}:
                    if not v:
                        setattr(bo, k, None)
                    else:
                        try:
                            from datetime import time
                            hh, mm = str(v).split(':', 1)
                            setattr(bo, k, time(int(hh), int(mm)))
                        except Exception:
                            setattr(bo, k, None)
                    continue
                if k.endswith('_id'):
                    try:
                        v_id = int(v) if str(v).strip() not in ('', 'None', 'null') else None
                    except (ValueError, TypeError):
                        v_id = None
                    setattr(bo, k, v_id)
                    continue
                setattr(bo, k, v)

        if (not getattr(bo, 'cod_natureza', None)) and getattr(bo, 'natureza', None) and ' - ' in bo.natureza:
            bo.cod_natureza = bo.natureza.split(' - ', 1)[0].strip()

        if status_in == 'FINALIZADO':
            bo.status = 'FINALIZADO'
            if not bo.numero:
                bo.numero = proximo_numero_bo()
            bo.finalizado_em = bo.finalizado_em or timezone.now()
        else:
            bo.status = 'EDICAO'

        bo.synced_at = timezone.now()
        bo.offline = (bo.status != 'FINALIZADO')
        bo.save()

        # Log simplificado
        if criado:
            record(request, event="BO_CRIADO", obj=bo, message=f"BO criado (UUID: {c_uuid})", app="bogcmi")
        if status_in == 'FINALIZADO':
            record(request, event="BO_FINALIZADO", obj=bo, message=f"BO #{bo.numero} finalizado", app="bogcmi")

        resultados.append({
            'client_uuid': c_uuid,
            'bo_id': bo.id,
            'numero': bo.numero,
            'status': bo.status,
            'criado': criado,
            'updated': not criado
        })

    return JsonResponse({'results': resultados, 'count': len(resultados)})