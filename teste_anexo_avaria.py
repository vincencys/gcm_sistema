#!/usr/bin/env python
"""
Script de teste para verificar a funcionalidade de anexos de avaria.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from taloes.models import ChecklistViatura, AvariaAnexo
from cecom.models import PlantaoCECOM
from django.utils import timezone

def teste_anexos():
    print("=== Teste de Anexos de Avaria ===\n")
    
    # Buscar checklist mais recente
    checklist = ChecklistViatura.objects.order_by('-criado_em').first()
    
    if not checklist:
        print("❌ Nenhum checklist encontrado no sistema")
        return
    
    print(f"✅ Checklist encontrado:")
    print(f"   ID: {checklist.id}")
    print(f"   Data: {checklist.data}")
    print(f"   Criado em: {checklist.criado_em}")
    
    if checklist.plantao_id:
        plantao = PlantaoCECOM.objects.filter(id=checklist.plantao_id).first()
        if plantao:
            print(f"   Plantão: {plantao.id}")
            print(f"   Viatura: {plantao.viatura}")
    
    # Buscar anexos desse checklist
    anexos = AvariaAnexo.objects.filter(checklist=checklist)
    
    print(f"\n📎 Anexos encontrados: {anexos.count()}")
    
    if anexos.exists():
        for anexo in anexos:
            print(f"\n   Anexo ID: {anexo.id}")
            print(f"   Campo: {anexo.campo_label}")
            print(f"   Arquivo: {anexo.arquivo.name}")
            print(f"   Descrição: {anexo.descricao or '(sem descrição)'}")
            print(f"   Criado em: {anexo.criado_em}")
    else:
        print("   (Nenhum anexo ainda)")
    
    # Mostrar itens marcados
    itens_marcados = checklist.itens_marcados()
    print(f"\n🔴 Itens marcados no checklist: {len(itens_marcados)}")
    for item in itens_marcados:
        print(f"   - {item}")
        # Verificar se tem anexo
        anexos_item = AvariaAnexo.objects.filter(
            checklist=checklist,
            campo_avaria=item.split(':')[0] if ':' in item else item
        )
        if anexos_item.exists():
            print(f"     📷 {anexos_item.count()} foto(s) anexada(s)")
    
    print("\n" + "="*50)
    print("Teste concluído!")
    print("\nPara testar upload:")
    print("1. Acesse o checklist de viatura")
    print("2. Marque um item de avaria")
    print("3. Clique em 'Anexar Foto'")
    print("4. Escolha uma imagem")
    print("5. Execute este script novamente para ver o anexo")

if __name__ == "__main__":
    teste_anexos()
