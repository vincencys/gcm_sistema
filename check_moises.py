import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.get(username='moises')
print(f'moises - is_staff: {u.is_staff}, is_superuser: {u.is_superuser}')