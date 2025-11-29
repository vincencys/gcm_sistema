# Sistema GCM - Como Executar

## 🚀 Iniciando o Servidor

### Método Recomendado (PowerShell)

Execute o script de inicialização:

```powershell
.\start_server.ps1
```

Ou manualmente:

```powershell
# 1. Ativar ambiente virtual
& .venv\Scripts\Activate.ps1

# 2. Iniciar servidor ASGI (Daphne) com suporte a WebSockets
daphne -b 127.0.0.1 -p 8000 gcm_project.asgi:application
```

### ⚠️ IMPORTANTE

**NÃO use `python manage.py runserver`** quando precisar de WebSockets!

- ❌ `python manage.py runserver` → Não suporta WebSockets
- ✅ `daphne -b 127.0.0.1 -p 8000 gcm_project.asgi:application` → Suporta HTTP + WebSockets

## 🌐 Acessando o Sistema

Após iniciar o servidor:

- **URL Local:** http://127.0.0.1:8000
- **URL Rede:** http://192.168.1.8:8000 (WebSocket só funciona via localhost em HTTP)

### Páginas principais:

- Login: http://127.0.0.1:8000/
- Disparos de Pânico: http://127.0.0.1:8000/cecom/panico/
- CECOM: http://127.0.0.1:8000/cecom/

## ✅ Funcionalidades WebSocket

Quando logado e na página de pânico:

1. **Modal abre automaticamente** se houver disparos com status "Aberta" ou "Em atendimento"
2. **Som toca 1x** por novo disparo
3. **Modal fecha automaticamente** quando disparo é encerrado
4. **Mapa atualiza em tempo real** com localização da assistida

## 🧪 Testando o Sistema

### Disparar teste de pânico:

```powershell
Invoke-WebRequest -Method POST -Uri "http://127.0.0.1:8000/panic/_dev/trigger/"
```

### Verificar se Daphne está rodando:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
```

### Parar todos os servidores na porta 8000:

```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## 📦 Dependências

Certifique-se de que as dependências estão instaladas:

```powershell
pip install -r requirements.txt
```

Dependências principais para WebSocket:
- `channels>=4.1`
- `daphne>=4.1`

## 🔧 Troubleshooting

### WebSocket não conecta?

1. Certifique-se de usar **Daphne**, não runserver
2. Acesse via **localhost** ou **127.0.0.1**, não via IP da rede em HTTP
3. Verifique o console do navegador (F12) para mensagens de erro

### Modal não aparece?

1. Verifique se está **logado** no sistema
2. Recarregue a página após conectar WebSocket
3. Verifique se há disparos com status "Aberta" no banco

### Porta 8000 ocupada?

Execute:
```powershell
.\start_server.ps1
```

O script para automaticamente processos na porta 8000 antes de iniciar.
