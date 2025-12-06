"""Testar baixar PDF do BO 192 como se fosse FLAVIO."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Criar cliente HTTP
client = Client()

# Logar como FLAVIO
flavio = User.objects.get(username='10681')
client.force_login(flavio)

# Fazer requisição ao endpoint de download
response = client.get('/bogcmi/192/baixar-pdf/')

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type')}")
print(f"Content-Disposition: {response.get('Content-Disposition')}")
print(f"Tamanho do PDF: {len(response.content)} bytes")

# Salvar PDF para análise
with open('test_bo192_flavio.pdf', 'wb') as f:
    f.write(response.content)
    
print(f"✅ PDF salvo em test_bo192_flavio.pdf")

# Comparar com tamanho esperado
print(f"\nComparação:")
print(f"  Sem marca (esperado ~114KB): {len(response.content)} bytes")
print(f"  Com marca (esperado ~154KB): ???")
