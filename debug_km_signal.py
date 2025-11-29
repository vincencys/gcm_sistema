#!/usr/bin/env python
"""
Script de diagnóstico para verificar por que o KM da viatura não está sendo atualizado.
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

print(f"\n📊 VIATURA 40 - Status Atual")
print(f"   KM Atual registrado: {viatura.km_atual}")
print(f"   Status: {viatura.status}")
print()

# Buscar últimos talões da viatura 40
print(f"📋 ÚLTIMOS TALÕES DA VIATURA 40:")
print(f"{'ID':<8} {'Status':<10} {'KM Inicial':<12} {'KM Final':<12} {'Iniciado em':<20}")
print("-" * 70)

taloes = Talao.objects.filter(viatura=viatura).order_by('-iniciado_em')[:10]
for t in taloes:
    km_ini = str(t.km_inicial) if t.km_inicial is not None else "—"
    km_fin = str(t.km_final) if t.km_final is not None else "—"
    iniciado = t.iniciado_em.strftime('%d/%m/%Y %H:%M') if t.iniciado_em else "—"
    print(f"{t.pk:<8} {t.status:<10} {km_ini:<12} {km_fin:<12} {iniciado:<20}")

print()

# Verificar qual deveria ser o KM atual
taloes_fechados = Talao.objects.filter(
    viatura=viatura,
    status='FECHADO',
    km_final__isnull=False
).order_by('-encerrado_em', '-iniciado_em')

if taloes_fechados.exists():
    ultimo = taloes_fechados.first()
    print(f"✅ ÚLTIMO TALÃO FECHADO COM KM FINAL:")
    print(f"   ID: {ultimo.pk}")
    print(f"   Status: {ultimo.status}")
    print(f"   KM Final: {ultimo.km_final}")
    print(f"   Encerrado em: {ultimo.encerrado_em.strftime('%d/%m/%Y %H:%M') if ultimo.encerrado_em else '—'}")
    print()
    
    if viatura.km_atual != ultimo.km_final:
        print(f"⚠️  DIVERGÊNCIA DETECTADA!")
        print(f"   KM da viatura: {viatura.km_atual}")
        print(f"   KM do último talão fechado: {ultimo.km_final}")
        print(f"   Diferença: {ultimo.km_final - viatura.km_atual}")
        print()
        
        # Testar o signal manualmente
        print(f"🔧 TESTANDO SIGNAL MANUALMENTE...")
        from taloes.signals import atualizar_km_viatura
        atualizar_km_viatura(sender=Talao, instance=ultimo, created=False)
        
        # Recarregar viatura
        viatura.refresh_from_db()
        print(f"   KM da viatura após signal: {viatura.km_atual}")
        
        if viatura.km_atual == ultimo.km_final:
            print(f"   ✅ Signal funcionou! KM atualizado para {viatura.km_atual}")
        else:
            print(f"   ❌ Signal não atualizou. Verificar código do signal.")
    else:
        print(f"✅ KM está correto: {viatura.km_atual}")
else:
    print(f"⚠️  Nenhum talão FECHADO com KM final encontrado para esta viatura")

print()
