# Configuração de E-mail (SMTP) no GCM Sistema

Este guia explica como configurar o envio de e-mails para recursos como "Enviar segunda via por e-mail" nas Notificações.

O sistema está preparado para:
- Em desenvolvimento (DEBUG=True): usar o backend de console (apenas imprime o e-mail no terminal)
- Em produção (DEBUG=False): usar SMTP, lendo variáveis de ambiente

## 1) Variáveis de ambiente
Defina estas variáveis no ambiente do servidor (ou num arquivo `.env` se você usa dotenv):

```
# Backend (opcional). Em produção, deixe SMTP. Em DEV, console é o default.
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# Servidor SMTP
EMAIL_HOST=smtp.seu-provedor.com
# Porta padrão TLS é 587; SSL é 465
EMAIL_PORT=587

# Credenciais
EMAIL_HOST_USER=nao-responder@seu-dominio.com.br
EMAIL_HOST_PASSWORD=senha_ou_app_password

# Segurança: use UM dos dois (TLS ou SSL)
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0

# Remetente padrão
DEFAULT_FROM_EMAIL=GCM Sistema <nao-responder@seu-dominio.com.br>

# (Opcional)
EMAIL_TIMEOUT=15
```

Observações:
- Se `EMAIL_USE_SSL=1` e você não informar `EMAIL_PORT`, a porta padrão usada será 465.
- Se nada for configurado e `DEBUG=True`, o sistema usa `console.EmailBackend` (e imprime o e-mail no terminal do servidor).

## 2) Provedores comuns

### Gmail (recomendado apenas com domínio Google Workspace)
- É necessário usar "App Passwords" (senhas de app) com 2FA ativado.
- Host: `smtp.gmail.com`
- Porta TLS: `587`
- `EMAIL_USE_TLS=1`
- `EMAIL_HOST_USER=seu-email@seu-dominio.com`
- `EMAIL_HOST_PASSWORD=<app_password>`

> Contas Gmail pessoais têm limitações e filtros rigorosos (SPF/DKIM/DMARC). Preferir domínio próprio.

### Outlook/Office 365 (Exchange Online)
- Host: `smtp.office365.com`
- Porta TLS: `587`
- `EMAIL_USE_TLS=1`
- `EMAIL_HOST_USER=seu-email@seu-dominio.com`
- `EMAIL_HOST_PASSWORD=<sua_senha_ou_app_password>`

### Provedor do seu domínio (recomendado)
- Peça ao TI os dados SMTP (host, porta, usuário, senha, TLS/SSL) e configure as variáveis.
- Garanta que o remetente DEFAULT_FROM_EMAIL seja um endereço do seu domínio com SPF/DKIM/DMARC corretos para evitar SPAM.

## 3) Teste rápido
Com o ambiente configurado, rode o comando de teste (substitua pelo seu e-mail):

```
python manage.py send_test_email --to seuemail@seu-dominio.com.br
```

Se estiver em DEBUG e não tiver configurado SMTP, o e-mail será impresso no terminal.

## 4) Boas práticas
- Use um e-mail específico de remetente (ex.: `nao-responder@seu-dominio.com.br`).
- Configure SPF, DKIM e DMARC no DNS do domínio para boa entregabilidade.
- Em produção, use TLS (porta 587) sempre que possível.
- Evite contas pessoais (Gmail/Outlook) — prefira contas do domínio institucional.

## 5) Problemas comuns
- Autenticação falha: confira usuário/senha, App Password (Gmail) e 2FA.
- Porta errada: 587 (TLS) ou 465 (SSL).
- Bloqueio por firewall: libere saída para o host/porta do SMTP.
- SPAM: ajuste SPF/DKIM/DMARC e use remetente do seu domínio.
