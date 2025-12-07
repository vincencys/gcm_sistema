# gcm_project/settings.py
import os
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.getenv("DEBUG", "1") == "1"
SITE_BASE_URL = os.getenv("SITE_BASE_URL") or ""  # usado em QR/links absolutos - NÃO usar default aqui!
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,0.0.0.0,gcmsysint.online,www.gcmsysint.online,18.229.134.75",
).split(",")

# Para POST/CSRF no dev e em possíveis hosts locais
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://192.168.1.7:8000",
    "https://192.168.100.1:8000",
    "http://192.168.1.7:8000",
    "http://192.168.100.1:8000",
    # Android Emulator -> host machine loopback
    "http://10.0.2.2:8000",
    "https://10.0.2.2:8000",


]

# Produção: confiar nos domínios públicos (com e sem www) e ambos os esquemas
for _host in ["gcmsysint.online", "www.gcmsysint.online"]:
    for _scheme in ("http", "https"):
        _entry = f"{_scheme}://{_host}"
        if _entry not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_entry)

# Configurações CORS para app mobile
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# Em desenvolvimento, facilitar acesso pela rede local
if DEBUG:
    try:
        import socket
        local_ips = set()
        # Método 1: descobrir IP "saída" (mais comum em IPv4)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ips.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        # Método 2: varrer IPs resolvidos pelo hostname
        try:
            hn = socket.gethostname()
            for fam, _, _, _, addr in socket.getaddrinfo(hn, None):
                ip = addr[0]
                if "." in ip:
                    local_ips.add(ip)
        except Exception:
            pass
        # Adicionar '*' para evitar bloqueio por host durante dev
        ALLOWED_HOSTS = list(set([*ALLOWED_HOSTS, "*"] + list(local_ips)))
        # Confiar nos IPs locais também para CSRF durante dev (porta 8000)
        for ip in list(local_ips):
            entry_http = f"http://{ip}:8000"
            entry_https = f"https://{ip}:8000"
            if entry_http not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(entry_http)
            if entry_https not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(entry_https)
        # Se não definir explicitamente, padroniza base como http (sem TLS) no IP local, porta 8000
        # MAS APENAS EM DESENVOLVIMENTO (não em produção)
        if not SITE_BASE_URL and DEBUG:
            # Escolhe um IP local preferencial para QR (evita https em dev)
            ip = next(iter(local_ips), "127.0.0.1")
            SITE_BASE_URL = f"http://{ip}:8000"
    except Exception:
        # Em último caso, permitir todos os hosts somente em DEBUG
        ALLOWED_HOSTS = list(set([*ALLOWED_HOSTS, "*"]))
        if not SITE_BASE_URL and DEBUG:
            SITE_BASE_URL = "http://127.0.0.1:8000"

# --- Apps ---
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Terceiros
    "corsheaders",
    "django_filters",
    "rest_framework",
    "crispy_forms",
    "crispy_tailwind",
    "channels",  # ASGI/WebSockets

    # Apps do projeto
    "common",
    "core",
    "users",
    "viaturas",
    "taloes",
    "bogcmi",
    "panic",
    "cecom",
    "almoxarifado",
    "notificacoes",
    "integracoes",
    "relatorios",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # estáticos com cache+gzip
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.AuditLogMiddleware",
    "common.middleware.TwoFAMiddleware",
]

ROOT_URLCONF = "gcm_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.plantao",
                "core.context_processors.user_permissions",
                "core.context_processors.oficios_pendentes",
                "core.context_processors.viaturas_avarias_nav",
            ],
        },
    }
]

# --- WSGI/ASGI (HTTP + Channels) ---
WSGI_APPLICATION = "gcm_project.wsgi.application"
ASGI_APPLICATION = "gcm_project.asgi.application"

# Channels (dev em memória; produção use channels_redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
# Exemplo produção:
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
#     }
# }

# --- Database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# Para Postgres (opcional):
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("POSTGRES_DB", "gcm"),
#         "USER": os.getenv("POSTGRES_USER", "gcm"),
#         "PASSWORD": os.getenv("POSTGRES_PASSWORD", "gcm"),
#         "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
#         "PORT": os.getenv("POSTGRES_PORT", "5432"),
#     }
# }

# --- Password validation ---
# Validações simplificadas para desenvolvimento
AUTH_PASSWORD_VALIDATORS = [
    # Removidos para permitir senhas simples no desenvolvimento
]

# --- Locale/Time ---
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Static & Media ---
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Notificações Push (Firebase) ---
# Caminho para o arquivo JSON de credenciais do serviço do Firebase (Service Account)
# Defina via variável de ambiente FIREBASE_CREDENTIALS_JSON em produção.
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')
# Fallback em dev: procurar arquivo local BASE_DIR/firebase-credentials.json
if not FIREBASE_CREDENTIALS_JSON:
    _fb_local = BASE_DIR / 'firebase-credentials.json'
    if _fb_local.exists():
        FIREBASE_CREDENTIALS_JSON = str(_fb_local)
    else:
        # Fallback adicional: detectar arquivo gerado pelo Firebase Console (padrão *firebase-adminsdk-*.json)
        import glob
        _cands = glob.glob(str(BASE_DIR / '*firebase-adminsdk-*.json'))
        if _cands:
            FIREBASE_CREDENTIALS_JSON = _cands[0]

# WhiteNoise (Django 5+ usa STORAGES)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 7  # 7 dias

# Uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth redirects ---
LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "users:login"

# --- Branding / PDFs ---
# Permite ocultar brasão e nome institucional nos novos documentos/PDFs
PDF_HIDE_BRANDING = True

# --- Crispy Forms ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- Celery (opcional; só entra em ação se você rodar o worker) ---
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = USE_TZ
CELERY_TASK_TIME_LIMIT = 60 * 15          # 15 min (hard)
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 10     # 10 min (soft)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "0") == "1"  # útil em testes

# --- Logging (simples e útil no dev) ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}

# --- IA Configuration ---
# Groq API para assistência em relatórios (gratuito)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", None)  # Definir no .env para produção

# --- Sessão / Cookies ---
# Controla a duração da sessão quando "Lembrar-me" está marcado.
# O RememberLoginView usa este valor via request.session.set_expiry.
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 24 * 14)))  # 14 dias padrão

# Em produção, não expira ao fechar navegador se o usuário marcou "Lembrar-me".
# Quando não marcado, o RememberLoginView aplica set_expiry(0) (sessão de navegador).
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Segurança de cookies
SESSION_COOKIE_SECURE = not DEBUG  # exige HTTPS em produção
CSRF_COOKIE_SECURE = not DEBUG

# Lax evita bloqueio de envio de cookie em navegação normal, mantendo proteção CSRF
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --- PDF / wkhtmltopdf ---
# Se o executável padrao existir, definir automaticamente (pode ser sobrescrito via env)
WKHTMLTOPDF_CMD = os.getenv("WKHTMLTOPDF_CMD", "")
if not WKHTMLTOPDF_CMD:
    for _cand in [
        r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        r"C:\\Program Files (x86)\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",
        "/usr/local/bin/wkhtmltopdf",
        "/usr/bin/wkhtmltopdf",
    ]:
        if os.path.exists(_cand):
            WKHTMLTOPDF_CMD = _cand
            break

# Flag para desabilitar completamente uso do WeasyPrint (evita warnings quando libs nativas faltam)
PDF_DISABLE_WEASYPRINT = os.getenv("PDF_DISABLE_WEASYPRINT", "1") == "1"

# --- E-mail (SMTP) ---
# Por padrão, em DEBUG usa console (imprime no terminal). Em produção, configure variáveis de ambiente.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@gcm.local")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

if EMAIL_USE_SSL and os.getenv("EMAIL_PORT") is None:
    # Se usar SSL e a porta não foi definida, adota 465 por padrão
    EMAIL_PORT = 465

# --- Almoxarifado: Políticas e Regras ---
# Permite configurar validações de negócio do almoxarifado sem alterar código
# - dupla_operacao: exige que solicitante/supervisor/almoxarife sejam usuários distintos
# - horarios: janelas de retirada/devolução (HH:MM)
# - limites: caps de munição por perfil (por_cargo, por_classe) e padrão
ALMOXARIFADO_POLICY = {
    "dupla_operacao": True,
    "horarios": {
        # Retirada (entrega da cautela)
        "retirada_inicio": os.getenv("ALMOX_RETIRADA_INICIO", "07:00"),
        "retirada_fim": os.getenv("ALMOX_RETIRADA_FIM", "22:00"),
        # Devolução
        "devolucao_inicio": os.getenv("ALMOX_DEVOLUCAO_INICIO", "07:00"),
        "devolucao_fim": os.getenv("ALMOX_DEVOLUCAO_FIM", "22:00"),
    },
    "limites": {
        # Ex.: por cargo
        "por_cargo": {
            # "Guarda Civil Municipal": {"municao_total_max": 60, "carregadores_max": 2},
        },
        # Ex.: por classe funcional
        "por_classe": {
            # "3C": {"municao_total_max": 60},
        },
        # Padrão caso não haja correspondência por cargo/classe
        "default": {"municao_total_max": int(os.getenv("ALMOX_MUNICAO_TOTAL_MAX", "60"))},
    },
    # Permissão que autoriza exceção fora de horário
    "permissao_excecao": "almoxarifado.desbloquear_excecao",
}
