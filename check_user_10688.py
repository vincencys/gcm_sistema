import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Verificar usuário com ID 10688
try:
    user = User.objects.get(id=10688)
    print(f'Usuário ID 10688: {user.username}')
    print(f'É superuser: {user.is_superuser}')
    print(f'É staff: {user.is_staff}')
    
    # Testar permissão
    from common.views import _is_comando
    print(f'Tem permissão comando: {_is_comando(user)}')
except User.DoesNotExist:
    print('Usuário ID 10688 não existe')

# Listar todos os usuários
print('\nTodos os usuários:')
for user in User.objects.all():
    print(f'ID: {user.id}, Username: {user.username}, Superuser: {user.is_superuser}')