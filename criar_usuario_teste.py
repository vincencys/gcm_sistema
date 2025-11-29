import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Criar usuário comum de teste
username = 'teste_comum'
try:
    user = User.objects.get(username=username)
    print(f'Usuário {username} já existe')
except User.DoesNotExist:
    user = User.objects.create_user(
        username=username,
        password='123',
        first_name='Teste',
        last_name='Comum',
        email='teste@gcm.local'
    )
    print(f'Usuário {username} criado com sucesso')

# Testar permissões
from common.views import _is_comando
print(f'{username} é comando: {_is_comando(user)}')