# Script PowerShell para corrigir Nginx no servidor EC2
$SSHKey = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"
$Server = "ec2-user@18.229.134.75"

Write-Host "=== CORRIGINDO NGINX NO SERVIDOR EC2 ===" -ForegroundColor Cyan
Write-Host ""

# Script bash que será executado no servidor
$RemoteScript = @'
#!/bin/bash
set -e

echo "=== CORRIGINDO NGINX PARA SERVIR /media/ ==="
echo ""

# 1. Backup da config atual
echo "1. Fazendo backup..."
sudo cp /etc/nginx/conf.d/gcm.conf /etc/nginx/conf.d/gcm.conf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "Sem config anterior"

# 2. Criar configuração correta
echo ""
echo "2. Criando configuração do Nginx..."
sudo tee /etc/nginx/conf.d/gcm.conf > /dev/null <<'NGINX_END'
upstream gunicorn_gcm {
    server 127.0.0.1:8001 fail_timeout=0;
}

upstream daphne_gcm {
    server 127.0.0.1:8002 fail_timeout=0;
}

server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 20M;

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
        proxy_redirect off;
        proxy_read_timeout 86400;
    }

    location / {
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 300;
    }
}
NGINX_END

echo "✓ Configuração criada"

# 3. Permissões
echo ""
echo "3. Ajustando permissões..."
sudo chmod -R o+rX /home/ec2-user/gcm_sistema/media
echo "✓ Permissões OK"

# 4. Testar config
echo ""
echo "4. Testando configuração..."
sudo nginx -t

# 5. Recarregar
echo ""
echo "5. Recarregando Nginx..."
sudo systemctl reload nginx
echo "✓ Nginx recarregado"

# 6. Status
echo ""
echo "6. Status do Nginx:"
sudo systemctl status nginx --no-pager -l | head -10

# 7. Teste
echo ""
echo "7. Testando acesso ao media..."
PDF=$(find /home/ec2-user/gcm_sistema/media/documentos/origem -name "*.pdf" -type f | head -1)
if [ -n "$PDF" ]; then
    REL=${PDF#/home/ec2-user/gcm_sistema/media/}
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1/media/$REL")
    if [ "$CODE" = "200" ]; then
        echo "✓ Media funcionando! (HTTP $CODE)"
    else
        echo "✗ Media com problema (HTTP $CODE)"
    fi
fi

echo ""
echo "✅ CONCLUÍDO!"
'@

# Executar no servidor via SSH
Write-Host "Conectando ao servidor..." -ForegroundColor Yellow
ssh -i $SSHKey $Server $RemoteScript

Write-Host ""
Write-Host "✅ Correção aplicada!" -ForegroundColor Green
Write-Host ""
Write-Host "Teste no navegador:" -ForegroundColor Cyan
Write-Host "https://gcmsysint.online/media/documentos/origem/2025/20251207_050257_BOGCMI_6-2025_110_a3b07fcc.pdf" -ForegroundColor White
