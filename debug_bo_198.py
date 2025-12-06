"""Debug do BO 198 e suas permissões."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth.models import User
from bogcmi.models import BO
from bogcmi.views_core import (
    _usuario_pode_ver_bo_sem_marca_dagua,
    _usuario_e_integrante_bo,
)

# Busca o BO
try:
    bo = BO.objects.get(pk=192)
    print(f"\n✅ BO encontrado: #{bo.numero or bo.pk}")
except BO.DoesNotExist:
    print("\n❌ BO 198 não existe!")
    print("\nBOs disponíveis:")
    for b in BO.objects.all()[:10]:
        print(f"  ID {b.pk}: #{b.numero or 'N/A'}")
    exit()

# Busca FLAVIO
try:
    flavio = User.objects.get(username='10681')
    print(f"✅ Usuário encontrado: {flavio.username} (ID={flavio.id})")
except User.DoesNotExist:
    print("❌ Usuário FLAVIO não encontrado!")
    exit()

print(f"\n{'='*60}")
print(f"BO #{bo.numero or bo.pk} (ID={bo.pk})")
print(f"{'='*60}")
print(f"\nEncarregado: {bo.encarregado.username if bo.encarregado else 'N/A'} (ID={bo.encarregado_id})")
print(f"Motorista: {bo.motorista.username if bo.motorista else 'N/A'} (ID={bo.motorista_id})")
print(f"CECOM: {bo.cecom.username if bo.cecom else 'N/A'} (ID={bo.cecom_id})")
print(f"Auxiliar 1: {bo.auxiliar1.username if bo.auxiliar1 else 'N/A'} (ID={bo.auxiliar1_id})")
print(f"Auxiliar 2: {bo.auxiliar2.username if bo.auxiliar2 else 'N/A'} (ID={bo.auxiliar2_id})")

print(f"\n{'='*60}")
print(f"PERMISSÕES DO USUÁRIO: {flavio.username}")
print(f"{'='*60}")

pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, flavio)
e_integrante = _usuario_e_integrante_bo(bo, flavio)
deve_aplicar_marca = e_integrante and not pode_ver_completo

print(f"\npode_ver_completo (is_staff/é comando): {pode_ver_completo}")
print(f"e_integrante (é motorista/encarregado/auxiliar/cecom): {e_integrante}")
print(f"Deve aplicar marca d'água: {deve_aplicar_marca}")

if flavio.username.lower() in ['comandante', 'subcomandante', 'administrativo', 'moises']:
    print(f"\n⚠️ Username '{flavio.username}' está em lista whitelist (sem marca)")
else:
    print(f"\n✓ Username '{flavio.username}' NÃO está em whitelist")

print(f"\nFlavio é superuser? {flavio.is_superuser}")
print(f"Flavio é staff? {flavio.is_staff}")

# Verificar grupos
if flavio.groups.exists():
    print(f"\nGrupos: {', '.join([g.name for g in flavio.groups.all()])}")
else:
    print(f"\nGrupos: (nenhum)")
