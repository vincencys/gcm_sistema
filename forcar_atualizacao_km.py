#!/usr/bin/env python
"""
Força a atualização do KM da viatura 40 com base no último talão fechado.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from taloes.models import Talao
from viaturas.models import Viatura

# Buscar viatura 40
viatura = Viatura.objects.filter(prefixo='40').first()
if not viatura:
    print("❌ Viatura 40 não encontrada!")
    exit(1)

print(f"\n🔄 FORÇANDO ATUALIZAÇÃO DO KM DA VIATURA 40")
print(f"   KM atual: {viatura.km_atual}")

# Buscar último talão fechado
ultimo = Talao.objects.filter(
    viatura=viatura,
    status='FECHADO',
    km_final__isnull=False
).order_by('-encerrado_em', '-iniciado_em').first()

if ultimo:
    print(f"   Último talão fechado: #{ultimo.pk}")
    print(f"   KM final do talão: {ultimo.km_final}")
    print()
    
    # Forçar atualização
    from taloes.signals import atualizar_km_viatura
    atualizar_km_viatura(sender=Talao, instance=ultimo, created=False)
    
    # Verificar
    viatura.refresh_from_db()
    print(f"✅ KM atualizado para: {viatura.km_atual}")
else:
    print("❌ Nenhum talão fechado encontrado")
