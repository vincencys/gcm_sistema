#!/usr/bin/env python
"""
Script para testar se SITE_BASE_URL está sendo carregado corretamente
no ambiente de produção
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gcm_project.settings")
django.setup()

from django.conf import settings

print(f"DEBUG: {settings.DEBUG}")
print(f"SITE_BASE_URL: {settings.SITE_BASE_URL}")
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS[:3]}...")  # primeiros 3

# Verificar se é a URL esperada
if settings.SITE_BASE_URL == "https://gcmsysint.online":
    print("\n✅ SUCESSO: SITE_BASE_URL está correto!")
    sys.exit(0)
else:
    print(f"\n❌ ERRO: SITE_BASE_URL esperado 'https://gcmsysint.online', mas recebeu '{settings.SITE_BASE_URL}'")
    sys.exit(1)
