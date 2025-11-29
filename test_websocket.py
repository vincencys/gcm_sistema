#!/usr/bin/env python
"""Teste rápido de conexão WebSocket ao panic alerts."""
import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/panico/alertas/"
    print(f"🔌 Conectando em {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("✅ WebSocket conectado!")
            print("📡 Aguardando mensagens (Ctrl+C para parar)...")
            async for message in ws:
                data = json.loads(message)
                print(f"📨 Recebido: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Erro de status HTTP: {e.status_code}")
        print(f"   Headers: {e.headers}")
    except Exception as e:
        print(f"❌ Erro: {type(e).__name__}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_ws())
    except KeyboardInterrupt:
        print("\n👋 Encerrado")
