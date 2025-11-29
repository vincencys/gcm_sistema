# Deploy Automático para AWS

## Configuração Inicial (Fazer 1x)

### 1. Editar o arquivo `deploy_aws.ps1`

Abra o arquivo e configure estas variáveis no topo:

```powershell
$AWS_HOST = "18.229.134.75"  # Seu IP AWS
$AWS_USER = "ubuntu"         # ou "ec2-user" se for Amazon Linux
$AWS_KEY = "C:\caminho\para\sua-chave.pem"  # Caminho completo da chave SSH
$REMOTE_PATH = "/home/ubuntu/GCM_Sistema"   # Onde está o projeto no servidor
```

### 2. Ajustar permissões da chave SSH (Windows)

```powershell
# Remover herança e deixar só você com acesso
icacls "C:\caminho\para\sua-chave.pem" /inheritance:r
icacls "C:\caminho\para\sua-chave.pem" /grant:r "$($env:USERNAME):(R)"
```

### 3. Testar conexão SSH manualmente

```powershell
ssh -i "C:\caminho\para\sua-chave.pem" ubuntu@18.229.134.75
```

## Uso Diário

### Deploy completo (recomendado)
```powershell
.\deploy_aws.ps1
```

### Deploy com mensagem customizada
```powershell
.\deploy_aws.ps1 -Message "Adiciona rodapé de copyright"
```

### Deploy pulando testes (mais rápido)
```powershell
.\deploy_aws.ps1 -SkipTests
```

## O que o script faz

1. ✅ Verifica mudanças locais e commita automaticamente
2. ✅ Faz push para o Git (se configurado)
3. ✅ Testa conexão SSH com AWS
4. ✅ Faz git pull no servidor
5. ✅ Instala dependências Python atualizadas
6. ✅ Executa migrations do Django
7. ✅ Coleta arquivos estáticos
8. ✅ Reinicia Gunicorn, Daphne, Celery e Nginx
9. ✅ Verifica se serviços estão rodando
10. ✅ Oferece abrir navegador

## Tempo médio
- Deploy completo: 30-60 segundos
- Deploy sem testes: 20-40 segundos

## Logs

Se der erro, o script para e mostra a mensagem. Verifique:
- Conexão SSH (chave, IP, security group)
- Serviços no servidor (systemctl status)
- Permissões de arquivos

## Automatizar ainda mais (CI/CD)

Para deploy automático ao fazer `git push`, considere:
- GitHub Actions
- AWS CodeDeploy
- GitLab CI/CD
