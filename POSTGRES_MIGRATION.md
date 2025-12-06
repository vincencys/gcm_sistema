# Migração para Postgres (AWS RDS)

Este documento detalha o passo a passo para migrar de SQLite para Postgres em produção (EC2 + RDS), mantendo segurança e capacidade de rollback.

## 1. Provisionar RDS Postgres
- Engine: PostgreSQL (14+)
- DB Name: `gcm`
- User: `gcm_user`
- Password: defina segura
- Security Group: permitir acesso da EC2 (porta 5432)
- Obter: endpoint (host), porta

## 2. Configurar Variáveis de Ambiente na EC2
Crie/edite o arquivo `.env` em `/home/ec2-user/gcm_sistema/.env` (ou o usado pelo seu service unit), com:
```
POSTGRES_DB=gcm
POSTGRES_USER=gcm_user
POSTGRES_PASSWORD=********
POSTGRES_HOST=<endpoint.rds.amazonaws.com>
POSTGRES_PORT=5432
SECRET_KEY=********
DEBUG=0
ALLOWED_HOSTS=gcmsysint.online,www.gcmsysint.online,18.229.134.75
SITE_BASE_URL=https://gcmsysint.online
```

## 3. Reiniciar Serviços com EnvironmentFile (exemplo)
Se o unit do gunicorn usa `EnvironmentFile=/home/ec2-user/gcm_sistema/.env`:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl restart daphne
sudo systemctl restart nginx
```

## 4. Migrar Esquema e (Opcional) Dados
- Esquema:
```bash
cd /home/ec2-user/gcm_sistema
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```
- Dados (opções):
  - Recriar vazio (mais rápido, perde dados antigos): usar apenas `migrate`.
  - Migrar do SQLite para Postgres:
    - Usar `pgloader` (recomendado para bases grandes):
      - Exportar/permitir acesso ao `db.sqlite3` e rodar `pgloader` com mapeamento.
    - Usar scripts Django para exportar/importar entidades essenciais.
    - Usar `django-import-export` para modelos específicos via admin.

## 5. Validação
```bash
python manage.py check --deploy
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 100 --no-pager
```
- Navegar no site, testar CRUD nas áreas principais.

## 6. Rollback
- Parar serviços:
```bash
sudo systemctl stop gunicorn
sudo systemctl stop daphne
```
- Remover/ignorar env `POSTGRES_*` e voltar ao SQLite:
```bash
# Edite /home/ec2-user/gcm_sistema/.env e comente/remova POSTGRES_*
```
- Restaurar backup do `db.sqlite3`:
```bash
cd /home/ec2-user/gcm_sistema
cp db_backup_YYYYMMDD_HHMMSS.sqlite3 db.sqlite3
```
- Iniciar serviços:
```bash
sudo systemctl start gunicorn
sudo systemctl start daphne
sudo systemctl restart nginx
```

## 7. Dicas
- Garanta o `ALLOWED_HOSTS` correto.
- Cookies já configurados para produção (secure/samesite) quando `DEBUG=0`.
- Se usar Celery/Redis, verifique workers e broker.
- Faça backup do SQLite antes de qualquer migração.
