"""
Management command para criar usuários do comando
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

class Command(BaseCommand):
    help = 'Cria usuários comandante, subcomandante e administrativo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', 
            action='store_true',
            help='Remove e recria os usuários se já existirem'
        )

    def handle(self, *args, **options):
        usuarios = [
            {
                'username': 'comandante',
                'first_name': 'Comandante',
                'last_name': 'GCM',
                'email': 'comandante@gcm.local',
                'password': '123',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'subcomandante',
                'first_name': 'Subcomandante',
                'last_name': 'GCM',
                'email': 'subcomandante@gcm.local',
                'password': '123',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'administrativo',
                'first_name': 'Administrativo',
                'last_name': 'GCM',
                'email': 'administrativo@gcm.local',
                'password': '123',
                'is_staff': True,
                'is_superuser': False,
            }
        ]

        with transaction.atomic():
            for user_data in usuarios:
                username = user_data['username']
                
                # Se --reset foi usado e o usuário existe, remove
                if options['reset'] and User.objects.filter(username=username).exists():
                    User.objects.filter(username=username).delete()
                    self.stdout.write(
                        self.style.WARNING(f'Usuário {username} removido para recriação')
                    )
                
                # Cria o usuário se não existir
                if not User.objects.filter(username=username).exists():
                    password = user_data.pop('password')
                    user = User.objects.create_user(**user_data)
                    user.set_password(password)
                    user.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Usuário {username} criado com sucesso')
                    )
                    self.stdout.write(f'  - Email: {user.email}')
                    self.stdout.write(f'  - Senha: {password}')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Usuário {username} já existe')
                    )

        self.stdout.write('\n' + self.style.SUCCESS('Processo concluído!'))
        self.stdout.write('\nUsuários criados para acesso ao sistema de documentos:')
        self.stdout.write('- comandante (senha: 123)')
        self.stdout.write('- subcomandante (senha: 123)')
        self.stdout.write('- administrativo (senha: 123)')
        self.stdout.write('\nURL: http://127.0.0.1:8001/common/documentos/pendentes/')