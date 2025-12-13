# 🚀 Deploy Rápido - Sistema GCM

## 📋 Informações do Servidor

- **IP Público**: 15.229.168.173
- **Domínio**: https://gcmsysint.online
- **Instância EC2**: i-097e96dd7175173b0 (sa-east-1)
- **Chave SSH**: `C:\Users\moise\Downloads\sistema-gcm-key.pem`
- **Usuário**: ec2-user
- **Diretório no servidor**: /home/ec2-user/gcm_sistema

## 🔑 Comando SSH Base

```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173
```

---

## 📦 DEPLOY COMPLETO (Commit Local + Push + Deploy Servidor)

```powershell
# 1. Commit e Push das alterações locais
cd c:\GCM_Sistema
git add -A
git commit -m "Descrição das alterações aqui"
git push

# 2. Atualizar código no servidor e reiniciar Gunicorn
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && git pull && sudo lsof -ti:8001 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart gunicorn && sleep 3 && systemctl is-active gunicorn"
```

---

## ⚡ COMANDOS RÁPIDOS

### 1️⃣ Apenas atualizar código (sem commit local)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && git pull"
```

### 2️⃣ Reiniciar Gunicorn (Django)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo lsof -ti:8001 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart gunicorn && sleep 3 && systemctl is-active gunicorn"
```

### 3️⃣ Reiniciar Daphne (WebSockets)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo lsof -ti:8002 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart daphne && sleep 3 && systemctl is-active daphne"
```

### 4️⃣ Reiniciar Nginx
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo systemctl restart nginx && systemctl is-active nginx"
```

### 5️⃣ Ver logs do Gunicorn (últimas 50 linhas)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo journalctl -u gunicorn -n 50 --no-pager"
```

### 6️⃣ Ver logs do Nginx (erros)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo tail -n 50 /var/log/nginx/error.log"
```

### 7️⃣ Verificar status de todos os serviços
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "systemctl is-active nginx gunicorn daphne"
```

### 8️⃣ Fazer backup do banco de dados
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && cp db.sqlite3 db.backup_$(date +%Y%m%d_%H%M%S).sqlite3"
```

### 9️⃣ Rodar migrações do Django
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && source .venv/bin/activate && python manage.py migrate"
```

### 🔟 Coletar arquivos estáticos
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && source .venv/bin/activate && python manage.py collectstatic --noinput"
```

---

## 📂 TRANSFERIR ARQUIVOS (SCP)

### Enviar arquivo LOCAL → SERVIDOR
```powershell
scp -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" "C:\caminho\local\arquivo.txt" ec2-user@15.229.168.173:/home/ec2-user/gcm_sistema/
```

### Baixar arquivo SERVIDOR → LOCAL
```powershell
scp -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" ec2-user@15.229.168.173:/home/ec2-user/gcm_sistema/arquivo.txt "C:\caminho\local\"
```

---

## 🔧 CONFIGURAÇÕES DO SERVIDOR

### Variáveis de Ambiente (Gunicorn)
Arquivo: `/etc/systemd/system/gunicorn.service`

```ini
Environment="SITE_BASE_URL=https://gcmsysint.online"
Environment="DEBUG=0"
```

### Recarregar configuração do systemd (após editar .service)
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo systemctl daemon-reload && sudo systemctl restart gunicorn"
```

---

## 🐛 TROUBLESHOOTING

### Porta 8001 em uso?
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo lsof -i :8001"
```

### Matar processo específico por PID
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo kill -9 PID_AQUI"
```

### Ver processos Python rodando
```powershell
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "ps aux | grep python"
```

### Testar se o site está respondendo
```powershell
curl -sL https://gcmsysint.online/ | Select-String "title" -Context 0,0 | Select-Object -First 1
```

---

## 📱 GERAR APK ANDROID

### Build e instalação no dispositivo conectado
```powershell
cd c:\GCM_Sistema\panic_app_android
npx cap sync
npx cap build android
# Ou usar Android Studio para build manual
```

### Instalar APK direto no dispositivo via ADB
```powershell
adb install -r caminho\para\app-debug.apk
```

---

## ✅ CHECKLIST DE DEPLOY

- [ ] Código commitado localmente (`git add -A && git commit -m "mensagem"`)
- [ ] Push para GitHub (`git push`)
- [ ] Pull no servidor (`git pull`)
- [ ] Migrações aplicadas (se houver)
- [ ] Estáticos coletados (se houver mudanças)
- [ ] Gunicorn reiniciado
- [ ] Daphne reiniciado (se alterou WebSockets)
- [ ] Nginx reiniciado (se alterou configuração)
- [ ] Testado no navegador (https://gcmsysint.online)
- [ ] Testado no aplicativo Android

---

## 🎯 WORKFLOW TÍPICO

```powershell
# 1. Fez alterações no código local
cd c:\GCM_Sistema

# 2. Commit e push
git add -A
git commit -m "Fix: corrigiu bug X"
git push

# 3. Deploy completo no servidor
ssh -i "C:\Users\moise\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && git pull && sudo lsof -ti:8001 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart gunicorn && sleep 3 && systemctl is-active gunicorn"

# 4. Verificar se está tudo OK
curl -sL https://gcmsysint.online/ | Select-String "title"
```

---

## 📞 INFORMAÇÕES ÚTEIS

- **Repositório GitHub**: https://github.com/vincencys/gcm_sistema
- **SSL Certificate**: Let's Encrypt (auto-renova)
- **Timezone servidor**: UTC
- **Python**: 3.11 (no virtualenv em .venv/)
- **Django**: Última versão compatível

---

**Última atualização**: 07/12/2025
**Responsável**: Moisés
