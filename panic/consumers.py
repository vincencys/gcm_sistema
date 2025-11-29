from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging

logger = logging.getLogger(__name__)

class PanicoAlertasConsumer(AsyncJsonWebsocketConsumer):
    group_name = "panico_global"

    async def connect(self):
        logger.info(f"[WS] Nova conexão de pânico: {self.channel_name}")
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"[WS] Conexão aceita: {self.channel_name}")
        
        # Ao conectar, enviar disparos em aberto para exibir imediatamente
        from .models import DisparoPanico
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_disparos_abertos():
            return list(DisparoPanico.objects.filter(
                status__in=['ABERTA', 'EM_ATENDIMENTO']
            ).select_related('assistida').order_by('-created_at')[:5])
        
        disparos = await get_disparos_abertos()
        for d in disparos:
            await self.send_json({
                "tipo": "PANICO_DISPARADO",
                "disparo_id": d.id,
                "assistida": {
                    "nome": d.assistida.nome,
                    "cpf": d.assistida.cpf,
                    "telefone": getattr(d.assistida, 'telefone', '')
                },
                "coords": {
                    "lat": float(d.latitude or 0),
                    "lng": float(d.longitude or 0),
                    "accuracy": d.precisao_m,
                },
                "aberto_em": d.created_at.isoformat() if d.created_at else None,
                "status": d.status,
            })

    async def disconnect(self, close_code):
        logger.info(f"[WS] Desconexão: {self.channel_name}, code={close_code}")
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def panico_disparado(self, event):
        logger.info(f"[WS] Enviando PANICO_DISPARADO: {event.get('data', {}).get('disparo_id')}")
        await self.send_json(event.get("data", {}))

    async def panico_localizacao(self, event):
        logger.debug(f"[WS] Enviando PANICO_LOCALIZACAO: {event.get('data', {}).get('disparo_id')}")
        await self.send_json(event.get("data", {}))
    
    async def panico_status_mudou(self, event):
        logger.info(f"[WS] Enviando PANICO_STATUS_MUDOU: {event.get('data', {}).get('disparo_id')}")
        await self.send_json(event.get("data", {}))
