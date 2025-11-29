import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from common.views import _is_comando

User = get_user_model()

# Verificar usuário 10688
user_10688 = User.objects.get(username='10688')
print(f'Usuário 10688: {user_10688.username}')
print(f'É comando: {_is_comando(user_10688)}')

# Verificar usuários do comando
print('\nUsuários do comando:')
for username in ['comandante', 'subcomandante', 'administrativo']:
    user = User.objects.get(username=username)
    print(f'{username}: É comando = {_is_comando(user)}')