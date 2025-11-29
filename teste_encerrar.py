import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from cecom.models import PlantaoCECOM
from taloes.views_extra import _gerar_pdf_plantao_encerrado
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils import timezone

User = get_user_model()
user = User.objects.get(username='moises')
plantao = PlantaoCECOM.objects.filter(ativo=True).first()

if plantao:
    print(f"Plantão encontrado: ID={plantao.id}")
    plantao.encerrado_em = timezone.now()
    plantao.ativo = False
    plantao.save()
    
    request = HttpRequest()
    request.user = user
    request.session = {}
    
    try:
        result = _gerar_pdf_plantao_encerrado(request, plantao)
        print(f"PDF gerado: {bool(result)}")
    except Exception as e:
        print(f"Erro: {e}")
else:
    print("Nenhum plantão ativo encontrado")

# Verificar documentos criados
from common.models import DocumentoAssinavel
docs = DocumentoAssinavel.objects.all().order_by('-created_at')
print(f"\nTotal documentos: {docs.count()}")
for doc in docs:
    print(f"- ID: {doc.id}, Status: {doc.status}, Usuario: {doc.usuario_origem.username}")