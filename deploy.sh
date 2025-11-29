#!/bin/bash
# Script de deploy para VPS Ubuntu/Debian

echo "🚀 Iniciando deploy do Sistema GCM..."

# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib redis-server

# Criar usuário do sistema
sudo useradd --system --shell /bin/bash --home /opt/gcm --create-home gcm

# Clonar/copiar código
sudo mkdir -p /opt/gcm/sistema
sudo chown gcm:gcm /opt/gcm/sistema

# Configurar PostgreSQL
sudo -u postgres createdb gcm_sistema
sudo -u postgres createuser gcm_user
sudo -u postgres psql -c "ALTER USER gcm_user PASSWORD 'your-password-here';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE gcm_sistema TO gcm_user;"

# Configurar ambiente Python
cd /opt/gcm/sistema
sudo -u gcm python3 -m venv venv
sudo -u gcm ./venv/bin/pip install -r requirements-prod.txt

# Configurar variáveis de ambiente
sudo -u gcm cp .env.example .env
# Editar .env com suas configurações

# Executar migrações
sudo -u gcm ./venv/bin/python manage.py migrate
sudo -u gcm ./venv/bin/python manage.py collectstatic --noinput

# Configurar Gunicorn
sudo tee /etc/systemd/system/gcm.service > /dev/null <<EOF
[Unit]
Description=GCM Sistema
After=network.target

[Service]
User=gcm
Group=gcm
WorkingDirectory=/opt/gcm/sistema
Environment=PATH=/opt/gcm/sistema/venv/bin
EnvironmentFile=/opt/gcm/sistema/.env
ExecStart=/opt/gcm/sistema/venv/bin/gunicorn --workers 3 --bind unix:/opt/gcm/sistema/gcm.sock gcm_project.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Configurar Nginx
sudo tee /etc/nginx/sites-available/gcm > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /opt/gcm/sistema;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        root /opt/gcm/sistema;
        expires 30d;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/opt/gcm/sistema/gcm.sock;
    }
}
EOF

# Ativar configurações
sudo ln -s /etc/nginx/sites-available/gcm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# Iniciar serviços
sudo systemctl daemon-reload
sudo systemctl start gcm
sudo systemctl enable gcm

# Configurar SSL (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

echo "✅ Deploy concluído!"
echo "🌐 Acesse: https://your-domain.com"
echo "👨‍💼 Crie um superuser: sudo -u gcm /opt/gcm/sistema/venv/bin/python /opt/gcm/sistema/manage.py createsuperuser"