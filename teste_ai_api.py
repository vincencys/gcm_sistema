#!/usr/bin/env python3
"""
Script para testar as APIs de IA
"""
import requests
import json

# Configurações
BASE_URL = "http://127.0.0.1:8001"
SESSION_ID = "teste_session"

def test_ai_apis():
    print("=== TESTANDO APIs DE IA ===\n")
    
    # Criar uma sessão para manter cookies
    session = requests.Session()
    
    # 1. Primeiro fazer login ou pegar CSRF token
    print("1. Obtendo CSRF token...")
    try:
        response = session.get(f"{BASE_URL}/users/login/")
        csrf_token = None
        
        if 'csrftoken' in session.cookies:
            csrf_token = session.cookies['csrftoken']
        else:
            # Extrair do HTML se necessário
            import re
            match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
        
        print(f"CSRF Token: {csrf_token[:20]}..." if csrf_token else "❌ CSRF token não encontrado")
        
    except Exception as e:
        print(f"❌ Erro ao obter CSRF: {e}")
        return
    
    if not csrf_token:
        print("❌ Não foi possível obter CSRF token. Testando sem autenticação...")
        return
    
    # Headers comuns
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token,
        'Referer': BASE_URL
    }
    
    # 2. Testar API de melhorar relatório
    print("\n2. Testando API melhorar_relatorio_ai...")
    test_data = {
        'texto': 'durante o plantao nao ocorreu nada'
    }
    
    try:
        response = session.post(
            f"{BASE_URL}/common/ai/melhorar-relatorio/",
            headers=headers,
            data=json.dumps(test_data)
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # 3. Testar API de sugerir relatório
    print("\n3. Testando API sugerir_relatorio_ai...")
    test_data = {
        'texto': ''  # Texto vazio
    }
    
    try:
        response = session.post(
            f"{BASE_URL}/common/ai/sugerir-relatorio/",
            headers=headers,
            data=json.dumps(test_data)
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # 4. Testar API de sugerir com texto
    print("\n4. Testando API sugerir_relatorio_ai com texto...")
    test_data = {
        'texto': 'nada aconteceu'
    }
    
    try:
        response = session.post(
            f"{BASE_URL}/common/ai/sugerir-relatorio/",
            headers=headers,
            data=json.dumps(test_data)
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_ai_apis()