from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Talao
from viaturas.models import Viatura


@receiver(post_save, sender=Talao)
def atualizar_km_viatura(sender, instance: Talao, created: bool, **kwargs):
    """
    Atualiza Viatura.km_atual com base no KM final do último talão FECHADO.
    
    Comportamento:
    - Só atualiza quando o talão está com status FECHADO (arquivado)
    - Usa o km_final do talão como km_atual da viatura
    - Atualiza automaticamente conforme novos talões são fechados
    
    Regras:
    - Só processa se houver viatura vinculada e km_final válido
    - SEMPRE atualiza quando o talão é fechado (permite correções)
    - Remove a proteção de regressão para permitir correções de KM incorreto
    """
    viatura: Viatura | None = instance.viatura
    if not viatura:
        return

    # Só atualiza se o talão estiver FECHADO (arquivado)
    if instance.status != "FECHADO":
        return

    # Só atualiza se houver km_final válido
    if instance.km_final is None or instance.km_final < 0:
        return

    novo_km = instance.km_final

    # Atualiza SEMPRE quando um talão é fechado
    # Isso permite que talões mais recentes corrijam KMs incorretos
    Viatura.objects.filter(pk=viatura.pk).update(km_atual=novo_km)
