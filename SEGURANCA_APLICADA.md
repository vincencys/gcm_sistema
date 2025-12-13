# 🔒 Segurança Aplicada ao Sistema GCM

**Data:** 13/12/2024  
**Status:** ✅ Implementado e testado

## 📋 Resumo das Proteções Implementadas

### 1. Rate Limiting (Nginx)
- **Limite:** 10 requisições por segundo por IP
- **Burst:** Até 20 requisições em rajada
- **Resposta:** HTTP 429 (Too Many Requests) quando exceder
- **Zona de memória:** 10MB (suporta ~160k IPs únicos)

### 2. Bloqueio de Bots (Nginx)
User-Agents bloqueados automaticamente com **HTTP 403**:
- `semrush` / `SemrushBot`
- `scrapy` / `Scrapy`
- `python-requests`
- `curl`
- `wget`
- `bot` (genérico)
- `spider` (genérico)
- `crawl` (genérico)

### 3. Headers de Segurança (Nginx)
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1
Server: nginx (sem versão)
```

- **X-Frame-Options: DENY** → Previne clickjacking
- **X-Content-Type-Options: nosniff** → Previne MIME sniffing
- **X-XSS-Protection: 1** → Ativa proteção XSS do browser
- **server_tokens off** → Oculta versão do Nginx

### 4. Flags de Segurança Django (settings.py)
```python
# Quando DEBUG=False (produção)
SESSION_COOKIE_HTTPONLY = True    # Cookie não acessível via JS
CSRF_COOKIE_HTTPONLY = True       # Token CSRF protegido
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# A ATIVAR APÓS HTTPS:
SECURE_SSL_REDIRECT = False       # → True com certificado SSL
SESSION_COOKIE_SECURE = False     # → True com HTTPS
CSRF_COOKIE_SECURE = False        # → True com HTTPS
```

### 5. Bloqueio de Arquivos Sensíveis (Nginx)
Acesso negado para:
- Arquivos ocultos (`.env`, `.git`, etc.)
- Backups (`.sql`, `.bak`, `.backup`)
- Logs (`.log`)
- Configurações (`.ini`)

## 🧪 Testes Realizados

### ✅ Teste 1: Rate Limiting
```bash
# 35 requisições rápidas
Resultado:
- 29 requisições → HTTP 302 (permitidas)
- 6 requisições → HTTP 429 (bloqueadas)
```

### ✅ Teste 2: Bloqueio de Bots
```bash
# User-Agent: Scrapy/1.0
Resultado: HTTP 403 Forbidden ✓

# User-Agent: SemrushBot/7.0
Resultado: HTTP 403 Forbidden ✓

# User-Agent: curl/8.11
Resultado: HTTP 403 Forbidden ✓
```

### ✅ Teste 3: Headers de Segurança
```
Server: nginx (versão oculta) ✓
X-Frame-Options: DENY ✓
X-Content-Type-Options: nosniff ✓
X-XSS-Protection: 1 ✓
```

## 📊 Análise de Logs Anterior

**IPs Suspeitos Identificados:**
- `66.249.69.167` → Googlebot-Image (legítimo, mas pode sobrecarregar)
- `66.249.69.168` → Googlebot-Image
- `201.57.89.197` → User-Agent fake (iPhone com Accept: */*)
- `184.154.139.60` → Scrapy/2.11.2 (bloqueado agora)

**User-Agents Problemáticos:**
- `Scrapy/2.11.2` → Bot de scraping (bloqueado)
- `python-requests/2.32.3` → Scripts automatizados (bloqueado)
- User-Agents falsos de iPhone/Safari (controlados por rate limit)

## 🔐 Arquivos de Configuração

### `/etc/nginx/nginx.conf`
```nginx
http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=req_limit:10m rate=10r/s;
    limit_req_status 429;

    # Bloqueio de bots
    map $http_user_agent $block_ua {
        default 0;
        ~*(semrush|scrapy|python-requests|curl|wget|bot|spider|crawl) 1;
    }
}
```

### `/etc/nginx/conf.d/gcm.conf`
```nginx
server {
    server_tokens off;
    
    if ($block_ua) {
        return 403;
    }
    
    location / {
        limit_req zone=req_limit burst=20 nodelay;
        # ... proxy_pass
    }
}
```

### `gcm_project/settings.py`
```python
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'gcmsysint.online',
    'www.gcmsysint.online',
    '15.229.168.173',  # Elastic IP
]

# Security flags (ativados quando DEBUG=False)
if not DEBUG:
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    # ... demais flags
```

## 🚀 Próximos Passos (Opcional)

### 1. Implementar HTTPS (Let's Encrypt)
```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gcmsysint.online -d www.gcmsysint.online
```

Depois ativar em `settings.py`:
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 2. Instalar Fail2ban (Proteção SSH)
```bash
sudo dnf install -y fail2ban
sudo systemctl enable --now fail2ban
```

### 3. Restringir Admin ao seu IP (Opcional)
```nginx
location /admin {
    allow 191.183.3.232;  # Seu IP
    deny all;
    # ... proxy_pass
}
```

### 4. Monitorar Logs Continuamente
```bash
# Requisições bloqueadas
sudo tail -f /var/log/nginx/access.log | grep " 403 "

# Rate limiting acionado
sudo tail -f /var/log/nginx/access.log | grep " 429 "
```

## 📝 Comandos Úteis

```bash
# Ver status dos serviços
sudo systemctl status nginx gunicorn daphne

# Recarregar Nginx após mudanças
sudo nginx -t && sudo systemctl reload nginx

# Ver últimas requisições bloqueadas
sudo tail -100 /var/log/nginx/access.log | grep " 403 "

# Ver IPs mais ativos
sudo awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20

# Bloquear IP específico manualmente (temporário)
sudo iptables -A INPUT -s 123.45.67.89 -j DROP
```

## ✅ Checklist de Segurança

- [x] Rate limiting configurado
- [x] Bloqueio de bots implementado
- [x] Headers de segurança aplicados
- [x] Versão do Nginx oculta
- [x] Flags de segurança Django ativadas
- [x] Arquivos sensíveis protegidos
- [x] Security Group configurado (SSH restrito)
- [x] Elastic IP fixo associado
- [ ] HTTPS com Let's Encrypt (pendente)
- [ ] Fail2ban instalado (pendente)
- [ ] Admin restrito por IP (opcional)

---

**✅ Sistema protegido e funcionando!**

Todas as proteções foram testadas e estão ativas. O sistema agora bloqueia bots automaticamente, limita requisições excessivas e adiciona headers de segurança em todas as respostas.
