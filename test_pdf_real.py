#!/usr/bin/env python
"""Teste prático da marca d'água em um PDF real."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from bogcmi.models import BO
from bogcmi.views_core import _aplicar_marca_dagua_pdf, _gerar_pdf_bo_bytes
from django.contrib.auth.models import User

# Buscar um BO finalizado com documento_html
bo = BO.objects.filter(status='FINALIZADO', documento_html__isnull=False).first()

if not bo:
    print("❌ Nenhum BO FINALIZADO com documento_html encontrado")
    sys.exit(1)

print(f"✅ BO encontrado: #{bo.numero or bo.pk}")

# Gerar PDF usando a mesma função que a view usa
print("\n1️⃣  Gerando PDF...")
try:
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.get('/')
    request.user = User.objects.first()  # Usar um usuário qualquer
    
    pdf_bytes = _gerar_pdf_bo_bytes(bo, request)
    print(f"   ✅ PDF gerado: {len(pdf_bytes)} bytes")
except Exception as e:
    print(f"   ❌ Erro: {e}")
    sys.exit(1)

# Aplicar marca d'água
print("\n2️⃣  Aplicando marca d'água...")
result = _aplicar_marca_dagua_pdf(pdf_bytes)
print(f"   Original: {len(pdf_bytes)} bytes")
print(f"   Com marca: {len(result)} bytes")
print(f"   Diferença: +{len(result) - len(pdf_bytes)} bytes")

if len(result) == len(pdf_bytes):
    print("\n❌ PROBLEMA: PDF não foi modificado!")
    print("   A marca d'água não foi aplicada.")
else:
    print("\n✅ Marca d'água aplicada com sucesso!")
    
    # Salvar arquivo de teste
    output_path = os.path.join(os.path.dirname(__file__), 'teste_pdf_real_com_marca.pdf')
    with open(output_path, 'wb') as f:
        f.write(result)
    print(f"   Arquivo salvo: {output_path}")
