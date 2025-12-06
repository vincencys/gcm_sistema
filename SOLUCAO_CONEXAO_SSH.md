# 🔧 Solução para Falha de Conexão SSH na EC2

## ❌ Problema Identificado
- **Erro**: "Failed to connect to your instance" no AWS Console
- **Causa**: Instância EC2 pode estar:
  1. ✅ Rodando, mas **sem SSM Agent instalado/configurado**
  2. 🔄 **Reiniciando** ou em estado transitório
  3. 🔥 Com **problema no sistema operacional**
  4. 🔒 **Sem permissões IAM** para Session Manager

---

## ✅ Solução 1: Verificar Estado da Instância

### Via Console AWS:
1. Acesse: https://sa-east-1.console.aws.amazon.com/ec2/home?region=sa-east-1#Instances:
2. Encontre a instância **`i-097e96dd717517360`** (GCM-Sistema)
3. Verifique o **"Instance state"**:
   - ✅ **Running** = Instância ligada
   - ⏸️ **Stopped** = Precisa iniciar
   - 🔄 **Stopping/Pending** = Aguarde

4. Verifique **"Status checks"**:
   - ✅ **2/2 checks passed** = Tudo OK
   - ⚠️ **1/2 checks passed** = Problema no sistema operacional
   - ❌ **0/2 checks passed** = Instância não inicializou

---

## ✅ Solução 2: Tentar SSH Direto (Windows PowerShell)

```powershell
# Teste 1: Ping no servidor
Test-NetConnection -ComputerName 18.229.134.75 -Port 22

# Teste 2: SSH com debug
ssh -vvv -i "$env:USERPROFILE\Downloads\sistema-gcm-key.pem" ec2-user@18.229.134.75

# Teste 3: Verificar permissões da chave
icacls "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"

# Teste 4: Corrigir permissões da chave (se necessário)
icacls "$env:USERPROFILE\Downloads\sistema-gcm-key.pem" /inheritance:r
icacls "$env:USERPROFILE\Downloads\sistema-gcm-key.pem" /grant:r "$env:USERNAME:(R)"
```

---

## ✅ Solução 3: Configurar Session Manager (SSM)

### 3.1. Adicionar IAM Role à Instância EC2

1. No Console AWS, vá em **EC2 > Instâncias**
2. Selecione a instância `i-097e96dd717517360`
3. Clique em **Actions > Security > Modify IAM role**
4. Selecione ou crie uma role com a policy: **`AmazonSSMManagedInstanceCore`**
5. Clique em **Update IAM role**

### 3.2. Instalar/Verificar SSM Agent (via User Data)

Se você tem acesso limitado, pode tentar **reiniciar a instância** com User Data:

1. No Console AWS, **PARE a instância** (Actions > Instance state > Stop)
2. Aguarde até status = **Stopped**
3. Clique em **Actions > Instance settings > Edit user data**
4. Cole o script abaixo:

```bash
#!/bin/bash
# Instalar/Atualizar SSM Agent no Amazon Linux
yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent
systemctl status amazon-ssm-agent
```

5. Clique em **Save**
6. **Inicie a instância novamente** (Actions > Instance state > Start)
7. Aguarde 5 minutos e tente conectar via **Session Manager**

---

## ✅ Solução 4: Usar EC2 Instance Connect (se disponível)

1. No Console AWS, selecione a instância
2. Clique no botão **Connect** (canto superior direito)
3. Vá na aba **EC2 Instance Connect**
4. Clique em **Connect**

**Nota**: Só funciona se:
- Instância tem IP público ✅ (18.229.134.75)
- Security group permite SSH da AWS ✅ (porta 22)
- Amazon Linux 2/2023 ou Ubuntu 16.04+ ✅

---

## ✅ Solução 5: Acessar Console via Serial Console (Último Recurso)

1. No Console AWS, selecione a instância
2. Clique em **Actions > Monitor and troubleshoot > EC2 Serial Console**
3. Se habilitado, você terá acesso ao terminal mesmo sem rede

⚠️ **Requer configuração prévia** da conta AWS.

---

## 🔍 Solução 6: Verificar Logs da Instância

1. No Console AWS, selecione a instância
2. Clique em **Actions > Monitor and troubleshoot > Get system log**
3. Procure por erros como:
   - Kernel panic
   - Failed to start services
   - Network configuration errors

---

## 🚀 Solução Alternativa: Recriar Instância com Terraform/CloudFormation

Se nada funcionar e a instância estiver inacessível, você pode:

1. **Criar snapshot do EBS** (backup do disco)
2. **Criar nova instância** com:
   - Amazon Linux 2023
   - Security Group correto (portas 22, 80, 443)
   - IAM Role com SSM
   - User Data para instalar/configurar tudo
3. **Anexar o volume EBS** da instância antiga (com os dados)

---

## 📝 Checklist de Diagnóstico

Execute estes comandos no **PowerShell** para diagnóstico completo:

```powershell
# 1. Verificar conectividade de rede
Write-Host "=== TESTE 1: Ping porta 22 ===" -ForegroundColor Cyan
Test-NetConnection -ComputerName 18.229.134.75 -Port 22

# 2. Verificar se chave existe
Write-Host "`n=== TESTE 2: Verificar chave SSH ===" -ForegroundColor Cyan
$keyPath = "$env:USERPROFILE\Downloads\sistema-gcm-key.pem"
if (Test-Path $keyPath) {
    Write-Host "✓ Chave encontrada: $keyPath" -ForegroundColor Green
    (Get-Item $keyPath).Length
} else {
    Write-Host "✗ Chave NÃO encontrada!" -ForegroundColor Red
}

# 3. Verificar permissões da chave
Write-Host "`n=== TESTE 3: Permissões da chave ===" -ForegroundColor Cyan
icacls $keyPath

# 4. Teste de DNS
Write-Host "`n=== TESTE 4: DNS do domínio ===" -ForegroundColor Cyan
nslookup gcmsysint.online

# 5. Teste HTTP direto no IP (sem Nginx)
Write-Host "`n=== TESTE 5: Teste HTTP porta 80 ===" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://18.229.134.75" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✓ HTTP responde! Status: $($response.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "✗ HTTP não responde: $($_.Exception.Message)" -ForegroundColor Red
}

# 6. Tentar SSH com verbose
Write-Host "`n=== TESTE 6: SSH com debug ===" -ForegroundColor Cyan
Write-Host "Pressione Ctrl+C se travar..." -ForegroundColor Yellow
ssh -vv -i $keyPath -o ConnectTimeout=10 -o StrictHostKeyChecking=no ec2-user@18.229.134.75 'echo "SSH OK!"'
```

---

## 🎯 Próximos Passos Recomendados

### Se conseguir acessar a instância de QUALQUER forma:

```bash
# 1. Verificar serviços
sudo systemctl status gunicorn-gcm
sudo systemctl status daphne-gcm
sudo systemctl status nginx

# 2. Instalar Nginx se não existir
sudo yum install -y nginx

# 3. Criar configuração do Nginx
sudo tee /etc/nginx/conf.d/gcm.conf > /dev/null <<'EOF'
upstream gunicorn_gcm {
    server 127.0.0.1:8001 fail_timeout=0;
}

server {
    listen 80;
    server_name gcmsysint.online www.gcmsysint.online 18.229.134.75;
    
    client_max_body_size 20M;
    
    location /static/ {
        alias /home/ec2-user/gcm_sistema/staticfiles/;
    }
    
    location /media/ {
        alias /home/ec2-user/gcm_sistema/media/;
    }
    
    location / {
        proxy_pass http://gunicorn_gcm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 4. Testar e iniciar Nginx
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx

# 5. Verificar status
curl -I http://127.0.0.1
curl -I http://18.229.134.75
```

---

## 📞 Suporte AWS

Se nada funcionar, abra um ticket de suporte AWS:
- Categoria: **EC2 Instance Connect Issue**
- Descrição: "Cannot connect to instance i-097e96dd717517360 via SSH or Session Manager"

---

## 🔄 Reiniciar Instância (Tentativa Simples)

Às vezes um simples reboot resolve:

1. Console AWS > EC2 > Instâncias
2. Selecione a instância
3. **Actions > Instance state > Reboot**
4. Aguarde 2-3 minutos
5. Tente conectar novamente

---

**Última atualização**: 1 de dezembro de 2025
