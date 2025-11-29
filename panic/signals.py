from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DisparoPanico
from .broadcast import broadcast_panico


@receiver(post_save, sender=DisparoPanico)
def disparo_created_broadcast(sender, instance: DisparoPanico, created: bool, **kwargs):
    # Envia broadcast somente na criação do disparo
    if created:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SIGNAL] Novo disparo criado! ID: {instance.id} - Enviando broadcast...")
        
        try:
            broadcast_panico(instance)
            logger.info(f"[SIGNAL] Broadcast enviado com sucesso para disparo ID: {instance.id}")
        except Exception as e:
            # Não interromper fluxo; apenas logar.
            logger.warning(f"Falha ao broadcast panico: {e}")

        # Envia push FCM para usuários relevantes (plantões CECOM ativos)
        try:
            import logging
            logger = logging.getLogger(__name__)
            # Coleta usuários do plantão principal CECOM (usuario + aux) ativos
            try:
                from cecom.models import PlantaoCecomPrincipal
                ativos = PlantaoCecomPrincipal.objects.filter(ativo=True).only('usuario_id','aux_cecom_id')
                user_ids = []
                for p in ativos:
                    if p.usuario_id:
                        user_ids.append(p.usuario_id)
                    if p.aux_cecom_id:
                        user_ids.append(p.aux_cecom_id)
                user_ids = list({u for u in user_ids if u})
            except Exception as e:  # pragma: no cover
                logger.warning(f"Pânico push: falha ao obter plantões CECOM: {e}")
                user_ids = []
            if user_ids:
                try:
                    from common.models import PushDevice
                    tokens = list(PushDevice.objects.filter(user_id__in=user_ids, enabled=True).values_list('token', flat=True))
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Pânico push: falha ao buscar tokens: {e}")
                    tokens = []
                if tokens:
                    title = f"Pânico - {instance.assistida.nome}"[:100]
                    body_parts = ["Botão de pânico acionado"]
                    try:
                        if instance.latitude and instance.longitude:
                            body_parts.append(f"@ {float(instance.latitude):.5f},{float(instance.longitude):.5f}")
                    except Exception:
                        pass
                    body = " ".join(body_parts)[:180]
                    data = {
                        'kind': 'panico',
                        'disparo_id': str(instance.id),
                        'assistida': instance.assistida.nome,
                        'status': instance.status,
                        'lat': str(instance.latitude or ''),
                        'lng': str(instance.longitude or ''),
                    }
                    try:
                        from common.views import enviar_push
                        enviar_push(tokens, title=title, body=body, data=data)
                    except Exception as e:  # pragma: no cover
                        logger.warning(f"Pânico push: falha ao enviar FCM: {e}")
        except Exception as e:  # pragma: no cover
            import logging
            logging.getLogger(__name__).warning(f"Pânico push: erro inesperado wrapper: {e}")
