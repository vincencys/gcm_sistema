🚀 INSTRUÇÕES DE DEPLOY - 7 de dezembro de 2025

## ✅ O QUE JÁ FOI FEITO:

1. ✓ Corrigido erro: NameError em `_gerar_qr_code_para_bo` (yimg → img)
2. ✓ Código commitado no Git
3. ✓ Push realizado para GitHub (branch main)

Commit: b40c673
Mensagem: "Fix: corrigir NameError em _gerar_qr_code_para_bo - yimg para img"

## 🔧 COMO FAZER DEPLOY NA EC2:

### OPÇÃO 1: Via AWS Session Manager (RECOMENDADO - Mais seguro)

1. Abra o Console AWS:
   https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances

2. Selecione a instância: "GCM-Sistema" (ID: i-097e96dd7175173b0)

3. Clique no botão laranja "Conectar" (canto superior direito)

4. Clique na aba "Session Manager"

5. Clique no botão "Conectar" (abrirá um terminal web)

6. NO TERMINAL WEB, COLE E EXECUTE ESTE COMANDO:

```bash
bash <(curl -s https://raw.githubusercontent.com/vincencys/gcm_sistema/main/deploy_session_manager.sh)
```

**OU, se não tiver acesso a internet, copie e cole:**

```bash
#!/bin/bash
set -e

echo "=== DEPLOY GCM SISTEMA VIA SESSION MANAGER ==="
echo "Data: $(date)"

cd /home/ec2-user/gcm_sistema
source .venv/bin/activate

echo "==> Atualizando código..."
git fetch origin
git reset --hard origin/main

echo "==> Instalando dependências..."
pip install -q --upgrade pip
pip install -q -r requirements-prod.txt 2>/dev/null || pip install -q -r requirements.txt

echo "==> Migrações..."
python manage.py migrate --noinput

echo "==> Coletando estáticos..."
python manage.py collectstatic --noinput --clear

echo "==> Verificação..."
python manage.py check

echo "==> Reiniciando serviços..."
sudo systemctl restart gunicorn-gcm
sleep 2
sudo systemctl restart daphne-gcm
sleep 2

echo "✅ DEPLOY CONCLUÍDO!"
echo "Acesse: https://gcmsysint.online"
```

7. Aguarde 2-3 minutos até aparecer "✅ DEPLOY CONCLUÍDO!"

---

### OPÇÃO 2: Via PowerShell (Se SSH estiver funcionando)

Execute no PowerShell (na pasta C:\GCM_Sistema):

```powershell
# Conectar via SSH e executar deploy
$SSHKey = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"
$Server = "ec2-user@18.229.134.75"

ssh -i $SSHKey $Server 'cd /home/ec2-user/gcm_sistema && source .venv/bin/activate && git pull origin main && python manage.py migrate && python manage.py collectstatic --noinput && sudo systemctl restart gunicorn-gcm daphne-gcm'
```

---

## 📊 INFORMAÇÕES DO SERVIDOR:

- **IP Público:** 18.229.134.75
- **IP Privado:** 172.31.5.118
- **Region:** sa-east-1 (São Paulo)
- **Instância:** GCM-Sistema (i-097e96dd7175173b0)
- **Sistema:** Amazon Linux 2023
- **Projeto:** /home/ec2-user/gcm_sistema

---

## 🔗 URLS PARA TESTAR APÓS DEPLOY:

- Produção (HTTPS): https://gcmsysint.online
- Alternativa: https://gcmsystem.online
- Desenvolvimento HTTP: http://18.229.134.75:80

---

## ✅ O QUE O DEPLOY FAZ:

1. Atualiza código do GitHub
2. Instala/atualiza dependências Python
3. Aplica migrações do banco de dados
4. Coleta arquivos estáticos (CSS, JS, imagens)
5. Executa verificação do Django
6. Reinicia Gunicorn (HTTP) 
7. Reinicia Daphne (WebSockets)
8. Verifica status dos serviços

---

## 🆘 SE ALGO DER ERRADO:

### Ver logs de erro:
```bash
sudo journalctl -u gunicorn-gcm -n 50 --no-pager
sudo journalctl -u daphne-gcm -n 50 --no-pager
```

### Reiniciar manualmente:
```bash
sudo systemctl restart gunicorn-gcm daphne-gcm nginx
```

### Verificar status:
```bash
sudo systemctl status gunicorn-gcm --no-pager
sudo systemctl status daphne-gcm --no-pager
sudo systemctl status nginx --no-pager
```

---

## 📝 PRÓXIMOS PASSOS:

1. Execute o comando de deploy acima
2. Aguarde conclusão
3. Acesse https://gcmsysint.online para testar
4. Teste a funcionalidade de despacho de BO (que estava com erro)
5. Se tudo OK, anote a hora do deploy neste arquivo

---

**Criado:** 7 de dezembro de 2025 - 01:50 BRT
**Correção:** NameError em QR code (yimg → img)
**Status:** ✅ Pronto para Deploy
