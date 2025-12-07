# Infraestrutura AWS - Sistema GCM

**Última atualização:** 07 de dezembro de 2025

## 🌐 Informações de Domínio e DNS

### Domínio
- **URL Principal:** https://gcmsysint.online
- **URL Alternativa:** https://www.gcmsysint.online
- **Provedor DNS:** Hostinger

### Configuração DNS (Hostinger)
```
Tipo: A
Nome: @
Valor: 15.229.168.173
TTL: 14400

Tipo: A
Nome: www
Valor: 15.229.168.173
TTL: 14400
```

## ☁️ Infraestrutura AWS

### EC2 Instance
- **Instance ID:** i-097e96dd7175173b0
- **Nome:** GCM-Sistema
- **Região:** sa-east-1 (São Paulo)
- **Tipo:** t2.micro
- **Sistema Operacional:** Amazon Linux 2023
- **Elastic IP:** 15.229.168.173 (fixo - não muda após reboot)

### Security Groups

#### launch-wizard-1 (sg-0b0bcf876a7986bae)
**Regras de Entrada:**
```
SSH (22)    | TCP | 22    | 0.0.0.0/0 | Acesso SSH
HTTP (80)   | TCP | 80    | 0.0.0.0/0 | Tráfego HTTP
HTTPS (443) | TCP | 443   | 0.0.0.0/0 | Tráfego HTTPS
```

**Regras de Saída:**
```
All traffic | All | All   | 0.0.0.0/0 | Todo tráfego de saída
```

### Network ACL
- **ACL ID:** acl-093fe65e1ebaeebd8
- **Configuração:** Padrão (permite todo tráfego)

### VPC e Subnet
- **VPC ID:** vpc-059c7b768bf79526
- **Subnet:** Subnet padrão da região sa-east-1

## 🔐 Certificado SSL

### Let's Encrypt
- **Domínios:** gcmsysint.online, www.gcmsysint.online
- **Tipo de Chave:** ECDSA
- **Validade:** 80 dias (renovação automática)
- **Expira em:** 26 de fevereiro de 2026
- **Caminho do Certificado:** `/etc/letsencrypt/live/gcmsysint.online/fullchain.pem`
- **Caminho da Chave Privada:** `/etc/letsencrypt/live/gcmsysint.online/privkey.pem`

### Renovação Automática
O Certbot está configurado para renovar automaticamente via systemd timer.

## 🔧 Configuração do Servidor

### Serviços Ativos

#### Nginx 1.28.0
- **Status:** Active (running)
- **Porta:** 80 (HTTP), 443 (HTTPS)
- **Configuração:** `/etc/nginx/conf.d/gcm.conf`
- **Redirecionamento:** HTTP → HTTPS (301)

#### Gunicorn 21.2.0
- **Status:** Active (running)
- **Workers:** 3
- **Porta:** 127.0.0.1:8001
- **Binding:** localhost apenas (proxy via Nginx)

#### Daphne (WebSockets)
- **Status:** Active (running)
- **Porta:** 127.0.0.1:8002
- **Binding:** localhost apenas (proxy via Nginx)

### Configuração Nginx (`/etc/nginx/conf.d/gcm.conf`)
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
    
    # Redirecionamento HTTP → HTTPS (configurado automaticamente pelo Certbot)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name gcmsysint.online www.gcmsysint.online;
    
    # Certificados SSL (gerenciados pelo Certbot)
    ssl_certificate /etc/letsencrypt/live/gcmsysint.online/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gcmsysint.online/privkey.pem;
    
    client_max_body_size 20M;
    
    location /static/ {
        alias /home/ec2-user/gcm_sistema/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /home/ec2-user/gcm_sistema/media/;
        expires 7d;
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
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔑 Acesso SSH

### Chave Privada
- **Localização:** `C:\Users\{username}\Downloads\sistema-gcm-key.pem`
- **Permissões:** Somente leitura (necessário no Linux/Mac)

### Comando de Conexão
```powershell
ssh -i C:\Users\$env:USERNAME\Downloads\sistema-gcm-key.pem ec2-user@15.229.168.173
```

Ou pelo IP Elástico (sempre funciona):
```powershell
ssh -i C:\Users\$env:USERNAME\Downloads\sistema-gcm-key.pem ec2-user@15.229.168.173
```

## 📦 Volumes EBS

### Volume Principal (Ativo)
- **Volume ID:** vol-037d35df8dcf94b61
- **Tamanho:** 10 GB
- **Tipo:** gp3
- **Estado:** Em uso (anexado à instância)
- **Taxa de transferência:** 125 IOPS

### Volume Secundário (Disponível)
- **Volume ID:** vol-0bc15c9678f6b825e
- **Tamanho:** 16 GB
- **Tipo:** gp3
- **Estado:** Disponível (não anexado)

## 🛠️ Comandos Úteis

### Reiniciar Serviços
```bash
# Via SSH na EC2
sudo systemctl restart nginx
sudo systemctl restart gunicorn
sudo systemctl restart daphne

# Verificar status
sudo systemctl status nginx gunicorn daphne
```

### Verificar Logs
```bash
# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn
sudo journalctl -u gunicorn -f

# Daphne
sudo journalctl -u daphne -f
```

### Renovar Certificado SSL Manualmente
```bash
sudo certbot renew --nginx
sudo systemctl reload nginx
```

### Verificar Portas em Uso
```bash
sudo netstat -tlnp | grep -E ':(80|443|8001|8002)'
```

## 🚨 Resolução de Problemas Comuns

### Problema: Site caiu após mudança de IP

**Sintoma:** ERR_CONNECTION_REFUSED

**Solução:**
1. Verificar se os serviços estão rodando:
   ```bash
   sudo systemctl status nginx gunicorn daphne
   ```

2. Se algum serviço falhou, verificar portas em uso:
   ```bash
   sudo lsof -ti:8001 | xargs -r sudo kill -9
   sudo lsof -ti:8002 | xargs -r sudo kill -9
   ```

3. Reiniciar serviços:
   ```bash
   sudo systemctl restart gunicorn
   sudo systemctl restart daphne
   sudo systemctl restart nginx
   ```

### Problema: Domínio não resolve (DNS cache)

**Sintoma:** IP funciona mas domínio não

**Solução no Windows:**
```powershell
# Limpar cache DNS
ipconfig /flushdns

# Verificar resolução
nslookup gcmsysint.online 8.8.8.8

# Se ainda não funcionar, adicionar temporariamente ao arquivo hosts:
# (Execute como Administrador)
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "`n15.229.168.173 gcmsysint.online`n15.229.168.173 www.gcmsysint.online"
```

**Solução no Linux/Mac:**
```bash
# Limpar cache DNS
sudo dscacheutil -flushcache  # macOS
sudo systemd-resolve --flush-caches  # Linux

# Adicionar ao /etc/hosts se necessário
echo "15.229.168.173 gcmsysint.online" | sudo tee -a /etc/hosts
echo "15.229.168.173 www.gcmsysint.online" | sudo tee -a /etc/hosts
```

### Problema: Certificado SSL expirado

**Sintoma:** Aviso de segurança no navegador

**Solução:**
```bash
# Renovar certificado
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

### Problema: Porta 80 ou 443 bloqueada

**Verificar Security Group:**
1. Acessar: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#SecurityGroups:
2. Verificar se as regras HTTP (80) e HTTPS (443) estão com origem `0.0.0.0/0`

**Verificar se Nginx está escutando:**
```bash
sudo ss -tlnp | grep nginx
# Deve mostrar: 0.0.0.0:80 e 0.0.0.0:443
```

## 📊 Monitoramento

### Verificar Saúde do Sistema
```bash
# CPU e Memória
top

# Espaço em disco
df -h

# Conexões ativas
sudo netstat -an | grep ESTABLISHED | wc -l

# Logs de erro recentes
sudo journalctl -p err -n 50
```

### Testar Conectividade Externa
```powershell
# Do Windows
Test-NetConnection -ComputerName gcmsysint.online -Port 443
Invoke-WebRequest -Uri https://gcmsysint.online -UseBasicParsing

# Verificar certificado
curl -vI https://gcmsysint.online 2>&1 | Select-String "SSL"
```

## 🔄 Backup e Recuperação

### Criar Snapshot do Volume EBS
1. Acessar: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Volumes:
2. Selecionar volume `vol-037d35df8dcf94b61`
3. Actions → Create Snapshot
4. Adicionar descrição com data

### Backup do Banco de Dados
```bash
# No servidor via SSH
cd /home/ec2-user/gcm_sistema
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json
```

## 📝 Notas Importantes

1. **Elastic IP é permanente:** O IP `15.229.168.173` não muda mesmo após reboot da instância
2. **Certificado SSL renovado automaticamente:** Certbot tem timer configurado
3. **Todos os serviços iniciam automaticamente:** Configurados com `systemctl enable`
4. **DNS pode ter cache:** ISPs podem demorar até 24h para atualizar (use arquivo hosts se necessário)
5. **Security Group permite tráfego mundial:** Porta 80 e 443 abertas para `0.0.0.0/0`

## 🆘 Contatos de Emergência

- **AWS Support:** https://console.aws.amazon.com/support/
- **Hostinger Support:** https://www.hostinger.com.br/contato
- **Let's Encrypt Community:** https://community.letsencrypt.org/

---

**Documento gerado automaticamente em:** 07/12/2025
**Mantido por:** Sistema de Deploy Automatizado
