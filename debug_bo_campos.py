"""Verificar campos do BO 192."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from bogcmi.models import BO

bo = BO.objects.get(pk=192)
print('BO #5-2025 - Todos os campos de pessoa:')
print(f'encarregado_id: {bo.encarregado_id}')
print(f'motorista_id: {bo.motorista_id}')
print(f'cecom_id: {bo.cecom_id}')
print(f'auxiliar1_id: {bo.auxiliar1_id}')
print(f'auxiliar2_id: {bo.auxiliar2_id}')

print('\nBuscando quem é o usuário 38 (FLAVIO/10681)...')
print(f'Em que lugar ele deveria estar nesse BO?')
print(f'\nVamos verificar no HTML da tela:')
print(f'Vejo que FLAVIO está como motorista no HTML')
print(f'Mas motorista_id no banco é: {bo.motorista_id}')
