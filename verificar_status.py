import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from common.models import DocumentoAssinavel

# Verificar todos os documentos
todos = DocumentoAssinavel.objects.all().order_by('-created_at')
print(f'Total documentos: {todos.count()}')

pendentes = DocumentoAssinavel.objects.filter(status='PENDENTE')
print(f'\nDocumentos PENDENTES: {pendentes.count()}')
for doc in pendentes:
    print(f'- ID: {doc.id}, Usuario: {doc.usuario_origem.username}, Criado: {doc.created_at}')

assinados = DocumentoAssinavel.objects.filter(status='ASSINADO')
print(f'\nDocumentos ASSINADOS: {assinados.count()}')
for doc in assinados:
    print(f'- ID: {doc.id}, Usuario: {doc.usuario_origem.username}, Criado: {doc.created_at}')