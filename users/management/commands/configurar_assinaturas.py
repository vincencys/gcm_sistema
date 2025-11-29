"""
Management command para configurar assinaturas dos usuários comando
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import Perfil
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

User = get_user_model()

class Command(BaseCommand):
    help = 'Configura assinaturas para usuários do comando'

    def gerar_assinatura_simples(self, nome):
        """Gera uma assinatura simples usando PIL"""
        # Criar imagem
        width, height = 300, 100
        img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Tentar usar uma fonte mais elegante, senão usar default
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            try:
                font = ImageFont.load_default()
            except:
                font = None
        
        # Desenhar o nome em cursivo/elegante
        text_color = (0, 0, 139, 255)  # Azul escuro
        if font:
            draw.text((20, 30), nome, fill=text_color, font=font)
        else:
            draw.text((20, 30), nome, fill=text_color)
        
        # Adicionar uma linha decorativa
        draw.line([(20, 70), (280, 70)], fill=text_color, width=2)
        
        # Converter para base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_data = buffer.getvalue()
        buffer.close()
        
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"

    def handle(self, *args, **options):
        usuarios_comando = [
            ('comandante', 'Comandante GCM', 'CMT'),
            ('subcomandante', 'Subcomandante GCM', 'SCM'), 
            ('administrativo', 'Administrativo GCM', '1C')
        ]

        self.stdout.write('Configurando assinaturas para usuários do comando...\n')

        for username, nome_completo, classe in usuarios_comando:
            try:
                user = User.objects.get(username=username)
                perfil, created = Perfil.objects.get_or_create(user=user)
                
                # Atualizar dados do perfil
                perfil.cargo = nome_completo
                perfil.classe = classe
                
                # Criar assinatura se não existir
                if not perfil.assinatura_digital:
                    assinatura_base64 = self.gerar_assinatura_simples(nome_completo)
                    perfil.assinatura_digital = assinatura_base64
                    self.stdout.write(f'✓ Assinatura criada para {username}')
                else:
                    self.stdout.write(f'- {username} já possui assinatura')
                
                perfil.save()
                self.stdout.write(f'✓ Perfil configurado: {username} ({classe})')
                
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ Usuário {username} não encontrado')
                )

        self.stdout.write('\n' + self.style.SUCCESS('Configuração concluída!'))
        self.stdout.write('\nUsuários configurados para assinatura de documentos:')
        self.stdout.write('- comandante (Comandante GCM)')
        self.stdout.write('- subcomandante (Subcomandante GCM)')
        self.stdout.write('- administrativo (Administrativo GCM)')