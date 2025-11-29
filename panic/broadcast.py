from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse

def broadcast_panico(disparo):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[BROADCAST] Iniciando broadcast para disparo ID: {disparo.id}")
    
    layer = get_channel_layer()
    if not layer:
        logger.error("[BROADCAST] Channel layer é None! Broadcast não enviado.")
        return
    
    logger.info(f"[BROADCAST] Channel layer OK: {type(layer).__name__}")
    
    data = {
        "tipo": "PANICO_DISPARADO",
        "disparo_id": disparo.id,
        # Envia também telefone para exibição imediata
        "assistida": {
            "nome": disparo.assistida.nome,
            "cpf": disparo.assistida.cpf,
            "telefone": getattr(disparo.assistida, 'telefone', '')
        },
        "coords": {
            "lat": float(disparo.latitude or 0),
            "lng": float(disparo.longitude or 0),
            "accuracy": disparo.precisao_m,
        },
        "aberto_em": disparo.created_at.isoformat() if disparo.created_at else None,
        # Direcionar diretamente para a página de DETALHE no CECOM
        "link_cecom": reverse("cecom:panico_detalhe", args=[disparo.id]),
    }
    
    logger.info(f"[BROADCAST] Enviando para grupo 'panico_global': {data}")
    async_to_sync(layer.group_send)("panico_global", {"type": "panico_disparado", "data": data})
    logger.info(f"[BROADCAST] ✅ Broadcast enviado com sucesso para disparo ID: {disparo.id}")


def broadcast_panico_localizacao(disparo):
    """Broadcast em tempo real de atualização de localização do disparo."""
    layer = get_channel_layer()
    if not layer:
        return
    data = {
        "tipo": "PANICO_LOCALIZACAO",
        "disparo_id": disparo.id,
        "coords": {
            "lat": float(disparo.latitude or 0),
            "lng": float(disparo.longitude or 0),
            "accuracy": disparo.precisao_m,
        },
    }
    async_to_sync(layer.group_send)("panico_global", {"type": "panico_localizacao", "data": data})


def broadcast_panico_status_mudou(disparo):
    """Broadcast quando status do disparo muda (ex: encerrado)."""
    layer = get_channel_layer()
    if not layer:
        return
    data = {
        "tipo": "PANICO_STATUS_MUDOU",
        "disparo_id": disparo.id,
        "status": disparo.status,
        "encerrado_em": disparo.encerrado_em.isoformat() if disparo.encerrado_em else None,
        "motivo": (disparo.relato_final or ""),
    }
    async_to_sync(layer.group_send)("panico_global", {"type": "panico_status_mudou", "data": data})
