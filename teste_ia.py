import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
django.setup()

from common.ai_service import RelatorioAIService

# Testar o serviço de IA
ai_service = RelatorioAIService()

# Teste 1: Texto com erros básicos
texto_teste = "durante o plantao nao ocorreu nada. tudo normal sem problemas."

print("=== TESTE DA IA ===")
print(f"Texto original: {texto_teste}")

resultado = ai_service.melhorar_relatorio(texto_teste)

if resultado['sucesso']:
    print(f"Texto melhorado: {resultado['texto_melhorado']}")
    if 'modo' in resultado:
        print(f"Modo: {resultado['modo']}")
else:
    print(f"Erro: {resultado['erro']}")

# Teste 2: Texto vazio
print("\n=== TESTE TEXTO VAZIO ===")
resultado2 = ai_service.melhorar_relatorio("")
print(f"Resultado: {resultado2}")

# Teste 3: Texto já bom
texto_bom = "Durante o plantão foram realizadas atividades de patrulhamento preventivo. Nada mais há a relatar."
print(f"\n=== TESTE TEXTO BOM ===")
print(f"Texto original: {texto_bom}")
resultado3 = ai_service.melhorar_relatorio(texto_bom)
if resultado3['sucesso']:
    print(f"Texto melhorado: {resultado3['texto_melhorado']}")
else:
    print(f"Erro: {resultado3['erro']}")