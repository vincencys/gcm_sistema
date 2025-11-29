import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from common.views import _is_comando

User = get_user_model()

# Testar usuários
users_to_test = ['comandante', 'subcomandante', 'administrativo', 'moises']

for username in users_to_test:
    try:
        user = User.objects.get(username=username)
        has_permission = _is_comando(user)
        print(f'{username}: É comando = {has_permission}')
    except User.DoesNotExist:
        print(f'{username}: Não encontrado')

# Testar context processor
from core.context_processors import user_permissions
from django.http import HttpRequest

class MockUser:
    def __init__(self, username, is_superuser=False):
        self.username = username
        self.is_superuser = is_superuser
        self.is_authenticated = True

request = HttpRequest()
request.user = MockUser('comandante')
context = user_permissions(request)
print(f'\nContext processor para comandante: {context}')