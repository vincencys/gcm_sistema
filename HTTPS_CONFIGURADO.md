# 🔒 HTTPS Configurado com Sucesso!

**Data:** 13/12/2024  
**Status:** ✅ Ativo e funcionando

## 📋 Resumo

- **Domínios:** gcmsysint.online, www.gcmsysint.online
- **Certificado SSL:** Let's Encrypt (válido por 90 dias)
- **Renovação automática:** Configurada via Certbot
- **HTTP → HTTPS:** Redirecionamento automático ativo

## ✅ Testes Confirmados

### 1. HTTPS Funcionando
```bash
curl https://gcmsysint.online/
# HTTP/1.1 302 Found (redireciona para login)
```

### 2. Redirecionamento HTTP → HTTPS
```bash
curl http://gcmsysint.online/
# HTTP/1.1 301 Moved Permanently
# Location: https://gcmsysint.online/
```

### 3. HSTS Ativo (HTTP Strict Transport Security)
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```
Isso força navegadores a sempre usarem HTTPS por 1 ano.

### 4. Headers de Segurança Completos
```
✓ X-Frame-Options: DENY
✓ X-Content-Type-Options: nosniff
✓ X-XSS-Protection: 1
✓ Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

## 🔧 Configurações Ativadas

### Django (settings.py)
```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True              # Força HTTPS
    SESSION_COOKIE_SECURE = True            # Cookies apenas HTTPS
    CSRF_COOKIE_SECURE = True               # Token CSRF apenas HTTPS
    SECURE_HSTS_SECONDS = 31536000          # HSTS por 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True   # HSTS em subdomínios
    SECURE_HSTS_PRELOAD = True              # HSTS preload list
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

### Nginx (gcm.conf)
O Certbot configurou automaticamente:
- Certificado SSL: `/etc/letsencrypt/live/gcmsysint.online/fullchain.pem`
- Chave privada: `/etc/letsencrypt/live/gcmsysint.online/privkey.pem`
- Server HTTPS na porta 443
- Redirecionamento HTTP (80) → HTTPS (443)

## 🔄 Renovação Automática do Certificado

O Certbot cria um timer systemd que renova automaticamente:

```bash
# Verificar status da renovação automática
sudo systemctl status certbot-renew.timer

# Testar renovação manualmente (dry-run)
sudo certbot renew --dry-run

# Forçar renovação (se necessário)
sudo certbot renew --force-renewal
```

Certificados Let's Encrypt expiram em **90 dias**. O timer do Certbot tenta renovar automaticamente quando faltam 30 dias.

## 📊 Arquitetura Atual

```
Internet
    ↓
AWS Security Group (porta 443, 80)
    ↓
Nginx (porta 80 → redireciona para 443)
    ↓
Nginx HTTPS (porta 443)
    ↓ rate limit + bot block
    ├─→ Gunicorn (porta 8001) → Django
    └─→ Daphne (porta 8002) → WebSockets
```

## 🔐 Níveis de Segurança Aplicados

### Camada 1: AWS Security Group
- Porta 443 (HTTPS): Aberta para 0.0.0.0/0
- Porta 80 (HTTP): Aberta para 0.0.0.0/0 (apenas para redirecionar)
- Porta 22 (SSH): Restrita ao IP do usuário (191.183.3.232/32)

### Camada 2: Nginx
- ✅ Rate limiting (10 req/s)
- ✅ Bloqueio de bots por User-Agent
- ✅ SSL/TLS (Let's Encrypt)
- ✅ HTTP → HTTPS redirect
- ✅ Headers de segurança

### Camada 3: Django
- ✅ HTTPS obrigatório (SECURE_SSL_REDIRECT)
- ✅ Cookies seguros (SECURE, HTTPONLY)
- ✅ HSTS ativo
- ✅ CSRF protection
- ✅ X-Frame-Options

## 🧪 Como Testar

### Do Windows (PowerShell):
```powershell
# HTTPS funcionando
curl -I https://gcmsysint.online/

# Redirecionamento HTTP → HTTPS
curl -I http://gcmsysint.online/

# Verificar headers de segurança
curl -I https://gcmsysint.online/ | Select-String "Strict-Transport"
```

### Do servidor EC2:
```bash
# Status do Certbot
sudo certbot certificates

# Logs do Nginx
sudo tail -f /var/log/nginx/access.log

# Status dos serviços
sudo systemctl status nginx gunicorn daphne
```

## 📝 Comandos Úteis

```bash
# Ver certificado instalado
sudo certbot certificates

# Testar renovação (não renova de fato)
sudo certbot renew --dry-run

# Recarregar Nginx após mudanças
sudo nginx -t && sudo systemctl reload nginx

# Ver logs de renovação do Certbot
sudo journalctl -u certbot-renew.service
```

## 🌐 Acessar o Sistema

- **HTTPS (recomendado):** https://gcmsysint.online/
- **HTTP (redireciona):** http://gcmsysint.online/ → https://gcmsysint.online/
- **www (funciona):** https://www.gcmsysint.online/

## ⚠️ Avisos Importantes

### 1. HSTS Ativado
Uma vez que um navegador visita o site com HSTS, ele **sempre** usará HTTPS por 1 ano, mesmo se você remover o certificado SSL. Não há como reverter facilmente.

### 2. Renovação Automática
Se a renovação automática falhar (ex: DNS mudou, servidor fora do ar), o certificado expira e o site fica inacessível via HTTPS. Monitore:
```bash
sudo certbot renew --dry-run
```

### 3. Firewall/Security Group
Certifique-se de que a porta 443 está sempre aberta no Security Group da AWS.

## 🚀 Próximos Passos Opcionais

### 1. Monitorar Expiração do Certificado
Adicionar ao cron ou usar serviço de monitoramento externo:
- https://crt.sh/ (verifica certificados públicos)
- AWS CloudWatch alarm para porta 443

### 2. Backup da Configuração
```bash
# Backup do certificado (importante!)
sudo tar -czvf /home/ec2-user/letsencrypt-backup.tar.gz /etc/letsencrypt/

# Baixar para Windows
scp -i "sistema-gcm-key.pem" ec2-user@15.229.168.173:/home/ec2-user/letsencrypt-backup.tar.gz .
```

### 3. CAA Record no DNS (opcional)
Adicionar no DNS da Hostinger:
```
gcmsysint.online. CAA 0 issue "letsencrypt.org"
```
Isso previne que outras CAs emitam certificados para seu domínio.

---

**✅ HTTPS totalmente funcional e seguro!**

O site agora usa criptografia SSL/TLS, força HTTPS, bloqueia bots, limita requisições e adiciona todos os headers de segurança recomendados.
