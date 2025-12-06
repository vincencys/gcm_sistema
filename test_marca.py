#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth.models import User
from bogcmi.models import BO
from bogcmi.views_core import _usuario_pode_ver_bo_sem_marca_dagua, _usuario_e_integrante_bo, _aplicar_marca_dagua_pdf
from io import BytesIO

# Buscar um BO arquivado com documento assinado
from common.models import DocumentoAssinavel

docs = DocumentoAssinavel.objects.filter(tipo='BOGCMI').first()
if docs:
    print(f"✅ Documento encontrado: {docs.id}")
    print(f"   BO: {docs.bo_numero}")
    
    # Tentar aplicar marca d'água
    if docs.arquivo_assinado:
        arquivo = docs.arquivo_assinado
    else:
        arquivo = docs.arquivo
    
    if arquivo:
        arquivo.seek(0)
        pdf_bytes = arquivo.read()
        print(f"✅ PDF lido: {len(pdf_bytes)} bytes")
        
        # Aplicar marca
        result = _aplicar_marca_dagua_pdf(pdf_bytes)
        print(f"✅ Marca aplicada: {len(result)} bytes")
        print(f"   PDF original: {len(pdf_bytes)} bytes")
        print(f"   PDF com marca: {len(result)} bytes")
        
        if len(result) == len(pdf_bytes):
            print("⚠️  AVISO: PDF não foi modificado (marca não aplicada?)")
        else:
            print("✅ PDF foi modificado (marca provavelmente aplicada)")
else:
    print("❌ Nenhum documento BOGCMI encontrado")
