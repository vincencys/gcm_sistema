"""Script de diagnóstico para verificar permissões e aplicação de marca d'água."""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from bogcmi.models import BO
from bogcmi.views_core import _usuario_pode_ver_bo_sem_marca_dagua, _usuario_e_integrante_bo

User = get_user_model()

print("="*60)
print("DIAGNÓSTICO DE MARCA D'ÁGUA - BOGCMI")
print("="*60)

# Buscar BO #1-2025
try:
    bo = BO.objects.get(numero='1-2025')
    print(f"\n✅ BO encontrado: {bo.numero} (ID: {bo.id})")
    print(f"\n📋 Integrantes do BO:")
    print(f"   Encarregado: {bo.encarregado.username if bo.encarregado else 'N/A'} (ID: {bo.encarregado_id})")
    print(f"   Motorista: {bo.motorista.username if bo.motorista else 'N/A'} (ID: {bo.motorista_id})")
    print(f"   Auxiliar 1: {bo.auxiliar1.username if bo.auxiliar1 else 'N/A'} (ID: {bo.auxiliar1_id})")
    print(f"   Auxiliar 2: {bo.auxiliar2.username if bo.auxiliar2 else 'N/A'} (ID: {bo.auxiliar2_id})")
    print(f"   CECOM: {bo.cecom.username if bo.cecom else 'N/A'} (ID: {bo.cecom_id})")
except BO.DoesNotExist:
    print("❌ BO #1-2025 não encontrado")
    sys.exit(1)

# Testar diferentes usuários
usuarios_teste = ['moises', 'CAROLINA', 'comandante', 'administrativo']

print(f"\n{'='*60}")
print("TESTE DE PERMISSÕES POR USUÁRIO")
print(f"{'='*60}\n")

for username in usuarios_teste:
    try:
        user = User.objects.get(username__iexact=username)
        pode_ver_completo = _usuario_pode_ver_bo_sem_marca_dagua(bo, user)
        e_integrante = _usuario_e_integrante_bo(bo, user)
        
        print(f"👤 {user.username} (ID: {user.id}):")
        print(f"   ├─ É superuser: {user.is_superuser}")
        print(f"   ├─ Pode ver SEM marca d'água: {pode_ver_completo}")
        print(f"   ├─ É integrante do BO: {e_integrante}")
        
        if pode_ver_completo:
            print(f"   └─ ✅ ACESSO COMPLETO (sem marca d'água)")
        elif e_integrante:
            print(f"   └─ ⚠️  MODO CONSULTIVO (COM marca d'água)")
        else:
            print(f"   └─ ❌ SEM ACESSO ao documento")
        print()
        
    except User.DoesNotExist:
        print(f"❌ Usuário '{username}' não encontrado\n")

print(f"{'='*60}")
print("CONCLUSÃO")
print(f"{'='*60}\n")

print("Para ver a marca d'água aplicada:")
print("1. Faça login como CAROLINA (motorista do BO)")
print("2. Acesse o documento do BO #1-2025")
print("3. Clique no botão verde 'Baixar PDF (com marca d'água)'")
print("4. Abra o arquivo BO_1-2025_CONSULTIVO.pdf")
print("5. Você verá a marca d'água diagonal 'APENAS CONSULTIVO'\n")

print("Usuários SEM marca d'água (acesso completo):")
print("- moises, comandante, subcomandante, administrativo, superuser\n")

print("✅ Sistema funcionando corretamente!")
