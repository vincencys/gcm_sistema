# Guia de Hardening do Nginx no EC2

## 1. Backup da configuração atual

```bash
sudo cp /etc/nginx/conf.d/gcm.conf /etc/nginx/conf.d/gcm.conf.backup
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
```

## 2. Adicionar Rate Limiting e Bloqueio de Bots

Edite `/etc/nginx/nginx.conf` e adicione dentro do bloco `http {}`:

```bash
sudo nano /etc/nginx/nginx.conf
```

Adicione ANTES dos blocos `upstream` e `server`:

```nginx
# Rate limiting - previne ataques de força bruta e DDoS
limit_req_zone $binary_remote_addr zone=req_limit:10m rate=10r/s;
limit_req_status 429;

# Bloqueio de User-Agents conhecidos de bots/scrapers
map $http_user_agent $block_ua {
    default 0;
    ~*(semrush|scrapy|python-requests|curl|wget|bot|spider|crawl) 1;
}
```

## 3. Atualizar configuração do server em `/etc/nginx/conf.d/gcm.conf`

```bash
sudo nano /etc/nginx/conf.d/gcm.conf
```

Substitua o conteúdo por:

```nginx
upstream gunicorn_gcm {
    server 127.0.0.1:8001 fail_timeout=0;
}

upstream daphne_gcm {
    server 127.0.0.1:8002 fail_timeout=0;
}

server {
    listen 80 default_server;
    server_name gcmsysint.online www.gcmsysint.online;
    client_max_body_size 20M;
    
    # Bloqueio de User-Agents suspeitos
    if ($block_ua) {
        return 403;
    }
    
    # Headers de segurança
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Ocultar versão do Nginx
    server_tokens off;
    
    location /static/ {
        alias /home/ec2-user/gcm_sistema/staticfiles/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /home/ec2-user/gcm_sistema/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    location /ws/ {
        proxy_pass http://daphne_gcm;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        # Rate limiting: 10 req/s com burst de 20
        limit_req zone=req_limit burst=20 nodelay;
        
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Bloquear acesso a arquivos sensíveis
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
    
    location ~ \.(sql|bak|backup|env|log|ini)$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

## 4. (OPCIONAL) Proteger rota /admin com IP específico

Se quiser restringir o acesso ao admin Django apenas ao seu IP:

```nginx
    location /admin {
        allow 191.183.3.232;  # Seu IP atual
        deny all;
        
        limit_req zone=req_limit burst=5 nodelay;
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

## 5. Testar e aplicar configuração

```bash
# Testar configuração
sudo nginx -t

# Se OK, recarregar
sudo systemctl reload nginx

# Verificar status
sudo systemctl status nginx
```

## 6. Monitorar logs de bots bloqueados

```bash
# Ver últimos acessos bloqueados (403)
sudo tail -f /var/log/nginx/access.log | grep " 403 "

# Ver rate limiting (429)
sudo tail -f /var/log/nginx/access.log | grep " 429 "
```

## 7. (FUTURO) Ativar HTTPS com Let's Encrypt

Quando estiver pronto para HTTPS:

```bash
# Instalar certbot
sudo dnf install -y certbot python3-certbot-nginx

# Obter certificado
sudo certbot --nginx -d gcmsysint.online -d www.gcmsysint.online

# Certbot configurará automaticamente redirect 80→443 e HTTPS
```

Depois disso, ative no Django (`settings.py` produção):
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

## 8. (OPCIONAL) Fail2ban para banimento automático

Instalar fail2ban para banir IPs com múltiplas tentativas:

```bash
sudo dnf install -y fail2ban

# Criar jail para Nginx
sudo tee /etc/fail2ban/jail.d/nginx.conf <<EOF
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
findtime = 60
bantime = 3600
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Ver banimentos
sudo fail2ban-client status nginx-limit-req
```

## 9. Mudar URL do Admin Django (recomendado)

No seu projeto, edite `gcm_project/urls.py` e mude:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('painel-gestao-gcm/', admin.site.urls),  # URL customizada
    # ... resto das URLs
]
```

Isso torna mais difícil para bots encontrarem o painel admin.

## 10. Checklist final de segurança

- [ ] Security Group: apenas 80, 443 e 22 (seu IP)
- [ ] Nginx: rate-limit e bloqueio de bots aplicados
- [ ] Django: DEBUG=False em produção
- [ ] Django: SECRET_KEY em variável de ambiente
- [ ] Django: ALLOWED_HOSTS correto
- [ ] Senha admin forte e usuário não-padrão
- [ ] URL do /admin customizada
- [ ] Logs sendo monitorados
- [ ] Backups configurados (snapshot EC2)
- [ ] HTTPS com Let's Encrypt (quando pronto)
- [ ] Fail2ban instalado e ativo
