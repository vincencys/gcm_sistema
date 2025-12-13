# 🖥️ Setup Rápido em outro notebook (Windows)

Use estes passos quando for programar no segundo PC. Pressupondo que você copiará a pasta `C:\GCM_Sistema` completa ou fará um clone do repo.

## 1) Copiar ou clonar o projeto
- **Opção A (copiar pasta):** copie toda a pasta `C:\GCM_Sistema` para o notebook.
- **Opção B (clonar):**
  ```powershell
  git clone https://github.com/vincencys/gcm_sistema.git C:\GCM_Sistema
  ```

## 2) Instalar dependências do sistema
- Instale Python 3.11 (Windows) e adicione ao PATH.
- Instale Git for Windows.
- Instale Node 18+ se for mexer no app mobile (panic_app_android).

## 3) Criar/ativar virtualenv e instalar pacotes
```powershell
cd C:\GCM_Sistema
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Configurar Git (se precisar)
```powershell
git config --global user.name "Seu Nome"
git config --global user.email "seuemail@exemplo.com"
```

## 5) Arquivo de chave SSH (para deploy)
- Coloque a chave em: `C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem`
- Comando base de SSH:
  ```powershell
  ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173
  ```

## 6) Fluxo de trabalho (local)
```powershell
cd C:\GCM_Sistema
.\.venv\Scripts\Activate.ps1
# editar código
python manage.py check        # checar Django
# opcional: python manage.py test
```

## 7) Fluxo de commit/push
```powershell
cd C:\GCM_Sistema
.\.venv\Scripts\Activate.ps1
git status
git add -A
git commit -m "Mensagem"
git push
```

## 8) Deploy no servidor (depois do push)
```powershell
ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && git pull && sudo lsof -ti:8001 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart gunicorn && sleep 3 && systemctl is-active gunicorn"
```

## 9) Comandos úteis rápidos
- **Pull somente:**
  ```powershell
  ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && git pull"
  ```
- **Reiniciar Gunicorn:**
  ```powershell
  ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo lsof -ti:8001 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart gunicorn && sleep 3 && systemctl is-active gunicorn"
  ```
- **Reiniciar Daphne (WebSockets):**
  ```powershell
  ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo lsof -ti:8002 | xargs -r sudo kill -9 && sleep 2 && sudo systemctl restart daphne && sleep 3 && systemctl is-active daphne"
  ```
- **Reiniciar Nginx:**
  ```powershell
  ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo systemctl restart nginx && systemctl is-active nginx"
  ```

## 10) Logs
```powershell
# Gunicorn
ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo journalctl -u gunicorn -n 50 --no-pager"
# Nginx erros
ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "sudo tail -n 50 /var/log/nginx/error.log"
```

## 11) Migrações / estáticos (quando mudar modelos ou front)
```powershell
ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && source .venv/bin/activate && python manage.py migrate"
ssh -i "C:\Users\<seu-usuario>\Downloads\sistema-gcm-key.pem" -o StrictHostKeyChecking=no ec2-user@15.229.168.173 "cd /home/ec2-user/gcm_sistema && source .venv/bin/activate && python manage.py collectstatic --noinput"
```

## 12) Mobile (Ionic/Capacitor)
```powershell
cd C:\GCM_Sistema\panic_app_android
npm install
npx cap sync
npx cap build android
# para instalar no dispositivo:
adb install -r caminho\para\app-debug.apk
```

## 13) Checklist rápido antes de deploy
- Código commitado e push feito
- `git pull` no servidor
- Migrações aplicadas (se alterou modelos)
- `collectstatic` se alterou front estático
- Gunicorn reiniciado
- (Opcional) Daphne/Nginx se mexeu em WebSockets ou configs

**Pronto.** Este arquivo fica em `C:\GCM_Sistema\SETUP_SEGUNDO_PC.md`.
