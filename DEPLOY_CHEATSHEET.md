# Guia de Deploy e Operação — Sistema GCM

Este guia reúne comandos práticos para desenvolvimento local e deploy/operação em produção (EC2). Ajuste placeholders conforme seu ambiente.

## Variáveis e Placeholders
- PEM: `C:\REGISTRO_SISTEMA_GCM_2025\sistema-gcm-key.pem`
- Host: `ec2-user@18.229.134.75`
- Path EC2: `/home/ec2-user/gcm_sistema`
- Services (ajuste se necessário): `gunicorn`, `daphne`, `nginx`, `celery`

## Dev Quick Start (Windows PowerShell)
```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py runserver 0.0.0.0:8000
# Ou com Daphne (ASGI/WebSockets)
# daphne -b 127.0.0.1 -p 8000 gcm_project.asgi:application
```

## Deploy Produção via PowerShell + SSH (PEM)
```powershell
# Testar SSH
ssh -i "C:\REGISTRO_SISTEMA_GCM_2025\sistema-gcm-key.pem" ec2-user@18.229.134.75 "echo OK"

# Aplicar código + deps + migrate + static + restart
ssh -i "C:\REGISTRO_SISTEMA_GCM_2025\sistema-gcm-key.pem" ec2-user@18.229.134.75 `
"source /home/ec2-user/gcm_sistema/.venv/bin/activate; \
 cd /home/ec2-user/gcm_sistema; \
 git pull; \
 python manage.py migrate; \
 python manage.py collectstatic --noinput; \
 sudo systemctl restart gunicorn; \
 sudo systemctl restart daphne; \
 sudo systemctl restart nginx"
```

## Deploy Direto na EC2 (Linux SSH)
```bash
cd /home/ec2-user/gcm_sistema
source .venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl restart gunicorn
sudo systemctl restart daphne
sudo systemctl restart nginx
```

## Backup / Rollback (SQLite)
```bash
# Backup (EC2)
cd /home/ec2-user/gcm_sistema
cp db.sqlite3 db_backup_$(date +%Y%m%d_%H%M%S).sqlite3

# Rollback (parar serviços, restaurar, iniciar)
sudo systemctl stop gunicorn; sudo systemctl stop daphne
cp db_backup_YYYYMMDD_HHMMSS.sqlite3 db.sqlite3
sudo systemctl start gunicorn; sudo systemctl start daphne
```

## Hardening de Sessão/Cookies
- `DEBUG=False` em produção.
- Cookies já configurados no settings: `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE='Lax'`.
- Ajuste `ALLOWED_HOSTS` e `SITE_BASE_URL` via env se necessário.

## Logs e Status
```bash
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 100 --no-pager
sudo systemctl status daphne
sudo journalctl -u daphne -n 100 --no-pager
sudo systemctl status nginx
sudo journalctl -u nginx -n 100 --no-pager
```

---
# Migração para Postgres (RDS) — Plano

## Opção B: Migrar para AWS RDS Postgres
1. Criar instância RDS (PostgreSQL):
   - Engine: PostgreSQL 14+ (sugestão)
   - Database name: `gcm`
   - Usuário: `gcm_user`
   - Senha: defina segura
   - Security Group: permitir acesso da EC2
2. Anotar: host, porta, db, usuário, senha.
3. Definir variáveis de ambiente na EC2 (arquivo `.env` ou unit `EnvironmentFile`):
   - `POSTGRES_DB=gcm`
   - `POSTGRES_USER=gcm_user`
   - `POSTGRES_PASSWORD=***`
   - `POSTGRES_HOST=<endpoint RDS>`
   - `POSTGRES_PORT=5432`
   - `SECRET_KEY=***`
   - `DEBUG=0`
   - `ALLOWED_HOSTS=gcmsysint.online,www.gcmsysint.online,18.229.134.75`
4. Ajustar `gcm_project/settings.py` já possui bloco comentado para Postgres. Basta definir as envs acima e reiniciar.
5. Migrar dados do SQLite para Postgres (opções):
   - Simples (recriar vazio): rodar `python manage.py migrate` e começar sem dados.
   - Com dados (ferramenta de migração):
     - Usar `django-import-export` ou script customizado.
     - Alternativa: `pgloader` do SQLite para Postgres (precisa mapear tabelas e constraints) — recomendado para bases maiores.
6. Aplicar migrações e coletar estáticos.

## Comandos na EC2 (após configurar env Postgres)
```bash
# Editar env
sudo nano /home/ec2-user/gcm_sistema/.env
# (adicione variáveis POSTGRES_* e outras)

# Carregar env no serviço (exemplo usando gunicorn unit com EnvironmentFile)
sudo systemctl daemon-reload
sudo systemctl restart gunicorn

# Dentro do venv
cd /home/ec2-user/gcm_sistema
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart daphne nginx
```

## Validação
- `python manage.py check --deploy`
- Navegar no site; verificar criação de tabelas no Postgres.
- Testar operações de leitura/escrita.

## Rollback (se necessário)
- Voltar `DATABASES` para SQLite removendo env `POSTGRES_*` e reiniciando serviços.
- Restaurar `db.sqlite3` de backup.

---
# Observações
- Se usar Celery/Redis, mantenha `CELERY_*` e verifique workers.
- `WKHTMLTOPDF_CMD` já autodetecta; ajuste via env se necessário.
- Em produção, evite `DEBUG=True`.
