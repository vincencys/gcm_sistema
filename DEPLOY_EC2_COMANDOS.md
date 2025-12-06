# 🚀 DEPLOY EC2 - Comandos Rápidos

## 📋 Informações da Instância
- **ID:** `i-097e96dd7175173b0`
- **Nome:** GCM-Sistema
- **Região:** `sa-east-1` (São Paulo)
- **IP Público:** `ec2-18-231-248-75.sa-east-1.compute.amazonaws.com`
- **IP Privado:** `172.31.5.118`
- **Sistema:** Amazon Linux 2023
- **Usuário:** `ec2-user`
- **Diretório do Projeto:** `/home/ec2-user/gcm_sistema`
- **Chave SSH:** `C:\REGISTRO_SISTEMA_GCM_2025\sistema-gcm-key.pem`

---

## 🔧 Método 1: Session Manager (Recomendado - Sem SSH)

### Via Console AWS:
1. Acesse: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances
2. Selecione instância **"GCM-Sistema"** (ID: `i-097e96dd7175173b0`)
3. Clique em **"Conectar"** (botão laranja no topo)
4. Aba **"Session Manager"** → Clique em **"Conectar"**
5. Execute os comandos abaixo no terminal que abrir

### Comandos no Session Manager:
```bash
# Navegar para o projeto
cd /home/ec2-user/gcm_sistema

# Atualizar código do GitHub
git pull origin main

# Reiniciar serviços
sudo systemctl restart gunicorn
sudo systemctl restart daphne

# Verificar status
sudo systemctl status gunicorn --no-pager
sudo systemctl status daphne --no-pager

# Confirmar deploy
echo "✅ Deploy concluído em $(date)"
```

---

## 🔑 Método 2: SSH Direto (com chave)

### Windows PowerShell:
```powershell
# Conectar via SSH
ssh -i "C:\REGISTRO_SISTEMA_GCM_2025\sistema-gcm-key.pem" ec2-user@ec2-18-231-248-75.sa-east-1.compute.amazonaws.com

# Após conectar, execute os comandos de deploy acima
```

### Via Script Automatizado:
```powershell
# No PowerShell, no diretório C:\GCM_Sistema
.\deploy_aws_direto.ps1 -Message "Descrição do deploy" -SkipTests
```

---

## 📝 Método 3: Deploy Completo com Migrações

```bash
cd /home/ec2-user/gcm_sistema
git pull origin main

# Atualizar dependências (se necessário)
source .venv/bin/activate
pip install -r requirements-prod.txt

# Aplicar migrações
python manage.py migrate

# Coletar arquivos estáticos
python manage.py collectstatic --noinput

# Reiniciar serviços
sudo systemctl restart gunicorn
sudo systemctl restart daphne

# Verificar logs
sudo journalctl -u gunicorn -n 50 --no-pager
sudo journalctl -u daphne -n 50 --no-pager
```

---

## 🔍 Comandos Úteis de Diagnóstico

### Ver logs em tempo real:
```bash
# Logs do Gunicorn
sudo journalctl -u gunicorn -f

# Logs do Daphne (WebSockets)
sudo journalctl -u daphne -f

# Logs do Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Verificar status dos serviços:
```bash
sudo systemctl status gunicorn
sudo systemctl status daphne
sudo systemctl status nginx
```

### Reiniciar serviços individualmente:
```bash
sudo systemctl restart gunicorn
sudo systemctl restart daphne
sudo systemctl restart nginx
```

### Verificar processos Python:
```bash
ps aux | grep python
ps aux | grep gunicorn
ps aux | grep daphne
```

---

## 🆘 Troubleshooting

### Se o site não responder após deploy:
```bash
# 1. Verificar se os serviços estão rodando
sudo systemctl status gunicorn
sudo systemctl status daphne

# 2. Ver últimos erros
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u daphne -n 100 --no-pager

# 3. Reiniciar tudo
sudo systemctl restart gunicorn
sudo systemctl restart daphne
sudo systemctl restart nginx

# 4. Verificar conectividade
curl http://localhost:8000
curl http://127.0.0.1:8001
```

### Se migrations falharem:
```bash
cd /home/ec2-user/gcm_sistema
source .venv/bin/activate

# Ver migrações pendentes
python manage.py showmigrations

# Aplicar migrações específicas
python manage.py migrate nome_app

# Fake migration (emergência)
python manage.py migrate --fake nome_app numero_migration
```

### Se código não atualizar:
```bash
# Forçar atualização do Git
cd /home/ec2-user/gcm_sistema
git fetch --all
git reset --hard origin/main

# Limpar cache Python
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reiniciar
sudo systemctl restart gunicorn
sudo systemctl restart daphne
```

---

## 📊 Informações dos Serviços

### Gunicorn (Django HTTP):
- **Porta:** 8000
- **Workers:** 3
- **Arquivo:** `/etc/systemd/system/gunicorn.service`
- **Socket:** `127.0.0.1:8000`

### Daphne (Django WebSockets):
- **Porta:** 8001
- **Arquivo:** `/etc/systemd/system/daphne.service`
- **Socket:** `127.0.0.1:8001`

### Nginx (Proxy Reverso):
- **Porta:** 80 (HTTP) / 443 (HTTPS)
- **Config:** `/etc/nginx/nginx.conf`
- **Sites:** `/etc/nginx/sites-available/gcm_sistema`

---

## 🔄 Workflow de Deploy Típico

```bash
# 1. Conectar via Session Manager (método preferido)
# 2. Navegar para o projeto
cd /home/ec2-user/gcm_sistema

# 3. Atualizar código
git pull origin main

# 4. Reiniciar serviços
sudo systemctl restart gunicorn && sudo systemctl restart daphne

# 5. Verificar
sudo systemctl status gunicorn --no-pager && sudo systemctl status daphne --no-pager

# 6. Testar no navegador
# Acessar: https://gcmsystem.online
```

---

## 💾 Backup antes de Deploy (Opcional)

```bash
# Backup do banco de dados
cd /home/ec2-user/gcm_sistema
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json

# Backup do código
cd /home/ec2-user
tar -czf gcm_sistema_backup_$(date +%Y%m%d_%H%M%S).tar.gz gcm_sistema/

# Listar backups
ls -lh gcm_sistema_backup_*.tar.gz
```

---

## 📝 Notas Importantes

1. **Sempre use Session Manager** quando possível (não precisa de chave SSH)
2. **Verifique os logs** após cada deploy para detectar erros
3. **Teste o site** após deploy antes de fechar o terminal
4. **Mantenha backups** antes de deploys grandes
5. **Documente mudanças** no commit do Git

---

## 🔗 Links Úteis

- **Site:** https://gcmsystem.online
- **Console AWS EC2:** https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances
- **GitHub Repo:** https://github.com/vincencys/gcm_sistema
- **Session Manager:** Use botão "Conectar" no console AWS

---

**Última atualização:** 06/12/2025  
**Criado por:** GitHub Copilot durante sessão de desenvolvimento
