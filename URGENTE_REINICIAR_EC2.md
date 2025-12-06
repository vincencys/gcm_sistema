# 🚨 URGENTE: Instância EC2 Travada - Precisa Reiniciar

## ❌ **DIAGNÓSTICO EXECUTADO (1 de dezembro, 20:35 BRT)**

```
✅ Porta 22 TCP: ACESSÍVEL (Test-NetConnection passou)
✅ Chave SSH: ENCONTRADA (1674 bytes, permissões corretas)
✅ Security Group: CONFIGURADO (portas 22, 80, 443 abertas)
❌ SSH: CONNECTION TIMEOUT - daemon não responde após banner
❌ HTTP porta 80: TIMEOUT - aplicação não responde
❌ Session Manager: FAILED - SSM não funciona
```

## 🎯 **PROBLEMA CONFIRMADO**

A instância EC2 **`i-097e96dd717517360`** está **travada**.

**Sintomas:**
- Porta 22 aceita conexão TCP mas SSH não completa handshake
- HTTP timeout (Nginx não está respondendo)
- Session Manager falha

**Causas prováveis:**
1. 🔥 SSH daemon (sshd) crashou
2. 💾 Disco 100% cheio
3. 🧠 Memória esgotada (OOM Killer)
4. ⚡ CPU em 100%
5. 🔄 Sistema em loop de boot

---

## 🚨 **SOLUÇÃO IMEDIATA: REINICIAR AGORA**

### Passo a Passo (Console AWS):

#### 1. Acesse o Console EC2
- URL: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances:

#### 2. Selecione a instância
- Marque o checkbox: **`i-097e96dd717517360` (GCM-Sistema)**
- Verifique: IP = `18.229.134.75`

#### 3. REINICIAR (Reboot)
- Clique: **"Instance state"** (botão superior direito)
- Selecione: **"Reboot instance"**
- Confirme: **"Reboot"**

#### 4. Aguarde
- ⏱️ **2-3 minutos** até status = "Running"
- ⏱️ **+2 minutos** até "Status checks" = **2/2 passed**

#### 5. Teste SSH novamente
```powershell
# No PowerShell:
ssh -i "$env:USERPROFILE\Downloads\sistema-gcm-key.pem" ec2-user@18.229.134.75
```

---

## 🔄 **SE REBOOT NÃO FUNCIONAR: STOP + START**

⚠️ **ATENÇÃO**: Isto pode mudar o IP público!

### Passo a Passo:

1. **PARE a instância**
   - Instance state > **"Stop instance"**
   - Aguarde até status = **"Stopped"** (pode levar 1-2 min)

2. **INICIE novamente**
   - Instance state > **"Start instance"**
   - Aguarde status = **"Running"**

3. **VERIFIQUE O IP**
   - Se mudou de `18.229.134.75`, anote o novo
   - Você precisará atualizar o DNS

4. **ALOCAR ELASTIC IP (recomendado)**
   - Vá em: EC2 > Network & Security > **Elastic IPs**
   - Clique: **"Allocate Elastic IP address"**
   - Clique: **"Allocate"**
   - Selecione o IP alocado
   - Actions > **"Associate Elastic IP address"**
   - Escolha sua instância
   - **IP agora é fixo e não muda mais!**

---

## 📊 **APÓS CONSEGUIR SSH: Diagnóstico**

Execute este script para identificar o que causou o travamento:

```bash
#!/bin/bash
echo "=== DIAGNÓSTICO PÓS-REINÍCIO ==="

echo -e "\n1. USO DE DISCO:"
df -h

echo -e "\n2. MEMÓRIA:"
free -h

echo -e "\n3. PROCESSOS QUE MAIS USAM MEMÓRIA:"
ps aux --sort=-%mem | head -11

echo -e "\n4. PROCESSOS QUE MAIS USAM CPU:"
ps aux --sort=-%cpu | head -11

echo -e "\n5. ÚLTIMOS ERROS DO SISTEMA:"
sudo journalctl -p err -xe --no-pager -n 50

echo -e "\n6. STATUS SSH:"
sudo systemctl status sshd --no-pager

echo -e "\n7. STATUS APLICAÇÃO:"
sudo systemctl status gunicorn-gcm --no-pager 2>/dev/null || echo "gunicorn-gcm não existe"
sudo systemctl status daphne-gcm --no-pager 2>/dev/null || echo "daphne-gcm não existe"
sudo systemctl status nginx --no-pager 2>/dev/null || echo "nginx não existe"

echo -e "\n8. PORTAS ABERTAS:"
sudo ss -tlnp | grep -E ':(22|80|443|8001|8002)'

echo -e "\n9. ÚLTIMAS 20 LINHAS DO BOOT:"
sudo dmesg | tail -20

echo -e "\n✅ Diagnóstico concluído!"
```

Salve como `diagnostico.sh`, depois:
```bash
chmod +x diagnostico.sh
./diagnostico.sh | tee diagnostico_$(date +%Y%m%d_%H%M%S).txt
```

---

## 🛠️ **CONFIGURAÇÃO COMPLETA DO SERVIDOR**

Após SSH funcionar, execute este script de configuração completa:

```bash
#!/bin/bash
set -e

echo "=== CONFIGURAÇÃO COMPLETA DO SERVIDOR GCM ==="

# 1. Atualizar sistema
echo -e "\n==> 1. Atualizando sistema..."
sudo yum update -y

# 2. Instalar pacotes necessários
echo -e "\n==> 2. Instalando pacotes..."
sudo yum install -y nginx python3.11 python3.11-pip git

# 3. Criar diretório do projeto se não existe
echo -e "\n==> 3. Verificando diretório do projeto..."
if [ ! -d /home/ec2-user/gcm_sistema ]; then
    echo "Criando diretório..."
    mkdir -p /home/ec2-user/gcm_sistema
    cd /home/ec2-user/gcm_sistema
    
    # Opção: clonar do Git
    echo "NOTA: Você precisa clonar o repositório manualmente:"
    echo "git clone https://github.com/vincencys/gcm_sistema.git ."
    echo "Ou fazer upload dos arquivos via SCP"
fi

cd /home/ec2-user/gcm_sistema || exit 1

# 4. Criar ambiente virtual se não existe
echo -e "\n==> 4. Configurando ambiente virtual Python..."
if [ ! -d .venv ]; then
    python3.11 -m venv .venv
fi

source .venv/bin/activate

# 5. Instalar dependências Python
echo -e "\n==> 5. Instalando dependências Python..."
if [ -f requirements-prod.txt ]; then
    pip install --upgrade pip wheel
    pip install -r requirements-prod.txt
elif [ -f requirements.txt ]; then
    pip install --upgrade pip wheel
    pip install -r requirements.txt
else
    echo "⚠️ AVISO: Nenhum arquivo requirements encontrado!"
    echo "Instalando pacotes básicos..."
    pip install django gunicorn daphne channels django-redis psycopg2-binary
fi

# 6. Configurar Nginx
echo -e "\n==> 6. Configurando Nginx..."
sudo tee /etc/nginx/conf.d/gcm.conf > /dev/null <<'NGINX_CONF'
upstream gunicorn_gcm {
    server 127.0.0.1:8001 fail_timeout=0;
}

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name gcmsysint.online www.gcmsysint.online 18.229.134.75 _;
    
    client_max_body_size 20M;
    
    # Logs
    access_log /var/log/nginx/gcm_access.log;
    error_log /var/log/nginx/gcm_error.log;
    
    # Arquivos estáticos
    location /static/ {
        alias /home/ec2-user/gcm_sistema/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Arquivos de mídia
    location /media/ {
        alias /home/ec2-user/gcm_sistema/media/;
        expires 7d;
    }
    
    # Favicon
    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }
    
    # Proxy para Gunicorn
    location / {
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
NGINX_CONF

# Remover configuração padrão que pode conflitar
sudo rm -f /etc/nginx/conf.d/default.conf

# 7. Testar configuração do Nginx
echo -e "\n==> 7. Testando configuração do Nginx..."
sudo nginx -t

# 8. Criar serviço Gunicorn
echo -e "\n==> 8. Criando serviço systemd para Gunicorn..."
sudo tee /etc/systemd/system/gunicorn-gcm.service > /dev/null <<'GUNICORN_SERVICE'
[Unit]
Description=Gunicorn daemon for GCM Sistema
After=network.target

[Service]
Type=notify
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/gcm_sistema
Environment="PATH=/home/ec2-user/gcm_sistema/.venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/ec2-user/gcm_sistema/.venv/bin/gunicorn \
    --workers 3 \
    --worker-class sync \
    --bind 127.0.0.1:8001 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    gcm_project.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
GUNICORN_SERVICE

# 9. Criar serviço Daphne (WebSockets)
echo -e "\n==> 9. Criando serviço systemd para Daphne..."
sudo tee /etc/systemd/system/daphne-gcm.service > /dev/null <<'DAPHNE_SERVICE'
[Unit]
Description=Daphne ASGI daemon for GCM Sistema
After=network.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/gcm_sistema
Environment="PATH=/home/ec2-user/gcm_sistema/.venv/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/ec2-user/gcm_sistema/.venv/bin/daphne \
    -b 127.0.0.1 \
    -p 8002 \
    --access-log - \
    gcm_project.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
DAPHNE_SERVICE

# 10. Recarregar systemd
echo -e "\n==> 10. Recarregando configuração systemd..."
sudo systemctl daemon-reload

# 11. Habilitar serviços para iniciar no boot
echo -e "\n==> 11. Habilitando serviços..."
sudo systemctl enable nginx
sudo systemctl enable gunicorn-gcm
sudo systemctl enable daphne-gcm

# 12. Aplicar migrações Django (se aplicável)
echo -e "\n==> 12. Aplicando migrações Django..."
if [ -f manage.py ]; then
    source .venv/bin/activate
    python manage.py migrate --noinput || echo "⚠️ Migrações falharam (verifique configuração)"
    python manage.py collectstatic --noinput --clear || echo "⚠️ Collectstatic falhou"
fi

# 13. Iniciar todos os serviços
echo -e "\n==> 13. Iniciando serviços..."
sudo systemctl start gunicorn-gcm
sudo systemctl start daphne-gcm
sudo systemctl start nginx

# 14. Verificar status
echo -e "\n==> 14. Status dos serviços:"
echo -e "\n--- NGINX ---"
sudo systemctl status nginx --no-pager -l

echo -e "\n--- GUNICORN ---"
sudo systemctl status gunicorn-gcm --no-pager -l

echo -e "\n--- DAPHNE ---"
sudo systemctl status daphne-gcm --no-pager -l

# 15. Testar endpoints
echo -e "\n==> 15. Testando endpoints..."
echo -e "\nGunicorn (porta 8001):"
curl -I http://127.0.0.1:8001/ 2>&1 | head -5

echo -e "\nNginx (porta 80):"
curl -I http://127.0.0.1/ 2>&1 | head -5

# 16. Verificar portas abertas
echo -e "\n==> 16. Portas abertas:"
sudo ss -tlnp | grep -E ':(22|80|443|8001|8002)'

echo -e "\n==============================================="
echo "✅ CONFIGURAÇÃO CONCLUÍDA!"
echo "==============================================="
echo ""
echo "URLs para testar:"
echo "  - http://18.229.134.75"
echo "  - http://gcmsysint.online (se DNS configurado)"
echo ""
echo "Comandos úteis:"
echo "  - Ver logs Nginx:     sudo tail -f /var/log/nginx/gcm_error.log"
echo "  - Ver logs Gunicorn:  sudo journalctl -u gunicorn-gcm -f"
echo "  - Ver logs Daphne:    sudo journalctl -u daphne-gcm -f"
echo "  - Reiniciar tudo:     sudo systemctl restart gunicorn-gcm daphne-gcm nginx"
echo ""
```

Salve como `setup_completo.sh` e execute:
```bash
chmod +x setup_completo.sh
./setup_completo.sh
```

---

## 🌐 **CONFIGURAR DNS**

Se o site funcionar em `http://18.229.134.75` mas não em `gcmsysint.online`:

### Verificar DNS atual:
```powershell
# No Windows PowerShell:
nslookup gcmsysint.online
```

### Configurar no provedor de domínio:
```
Tipo: A
Host: @
Valor: 18.229.134.75
TTL: 3600

Tipo: A
Host: www
Valor: 18.229.134.75
TTL: 3600
```

Aguarde 5-60 minutos para propagação DNS.

---

## 🔒 **INSTALAR SSL (HTTPS)**

Após tudo funcionar em HTTP:

```bash
# 1. Instalar Certbot
sudo yum install -y certbot python3-certbot-nginx

# 2. Obter certificado Let's Encrypt
sudo certbot --nginx -d gcmsysint.online -d www.gcmsysint.online

# 3. Testar renovação automática
sudo certbot renew --dry-run

# 4. Certificado renova automaticamente!
```

---

## 📋 **CHECKLIST COMPLETO**

### Urgente (faça AGORA):
- [ ] 1. **REINICIAR** instância EC2 via Console AWS
- [ ] 2. Aguardar 3-5 minutos
- [ ] 3. Testar SSH: `ssh -i <chave> ec2-user@18.229.134.75`

### Após SSH funcionar:
- [ ] 4. Executar `diagnostico.sh` para ver o que travou
- [ ] 5. Executar `setup_completo.sh` para configurar tudo
- [ ] 6. Testar: `curl http://127.0.0.1`
- [ ] 7. Testar: `curl http://18.229.134.75`
- [ ] 8. Abrir navegador: `http://18.229.134.75`
- [ ] 9. Configurar DNS para `gcmsysint.online`
- [ ] 10. Aguardar propagação DNS (5-60 min)
- [ ] 11. Testar: `http://gcmsysint.online`
- [ ] 12. Instalar SSL: `sudo certbot --nginx`
- [ ] 13. Testar: `https://gcmsysint.online`

### Prevenção futura:
- [ ] 14. Alocar **Elastic IP** (IP fixo)
- [ ] 15. Configurar **CloudWatch Alarms** (CPU, Memória, Disco)
- [ ] 16. Configurar **Auto Recovery** na instância
- [ ] 17. Habilitar **Monitoring detalhado**
- [ ] 18. Criar **snapshots do EBS** (backup automático)

---

## 🆘 **CONTATOS DE EMERGÊNCIA**

### Se nada funcionar:

1. **AWS Support**:
   - https://console.aws.amazon.com/support/home
   - Categoria: Technical Support > EC2 > Instance Connectivity

2. **Criar nova instância**:
   - Se instância estiver irrecuperável
   - Criar snapshot do disco (EBS) antes!
   - Anexar disco à nova instância

3. **Restaurar de backup**:
   - Se tiver snapshot/AMI, lance nova instância

---

**🚨 AÇÃO IMEDIATA**: REINICIAR A INSTÂNCIA AGORA VIA CONSOLE AWS  
**📅 Data**: 1 de dezembro de 2025, 20:40 BRT  
**⏱️ Tempo estimado para resolver**: 10-15 minutos após reboot
