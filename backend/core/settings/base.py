import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv(
    'SECRET_KEY',
    "django-insecure-CHANGE_ME"
    )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third Party Apps
    'corsheaders',
    'rest_framework',
    'drf_spectacular',
    "rest_framework_simplejwt.token_blacklist",
    
    # Local Apps
    'users',
    'shifts',
    'user_notifications',
    'forecasting'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ═══════════ ПУТИ ML ═══════════
# Корень репозитория (parent от backend/)
REPO_ROOT = BASE_DIR.parent

# Путь к ml_data
ML_DATA_DIR = Path(os.getenv("ML_DATA_DIR", str(REPO_ROOT / "ml_data"))).resolve()
ML_DATA_RAW = Path(os.getenv("ML_DATA_RAW", str(ML_DATA_DIR / "data" / "raw"))).resolve()
ML_DATA_PROCESSED = Path(
    os.getenv("ML_DATA_PROCESSED", str(ML_DATA_DIR / "data" / "processed"))
).resolve()
ML_DATA_PREDICTED = Path(
    os.getenv("ML_DATA_PREDICTED", str(ML_DATA_DIR / "data" / "predicted"))
).resolve()
ML_MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", str(ML_DATA_DIR / "models"))).resolve()

# Добавить ml_data в PYTHONPATH чтобы import ml_data.* работал
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# ════════════════════════════════

ROOT_URLCONF = "core.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ===================== КРИТИЧНО! ======================
# Указать ДО первой миграции, иначе Django создаст
# стандартную таблицу auth_user и откатить будет больно
AUTH_USER_MODEL = "users.User"
# =====================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
DEFAULT_CHARSET = "utf-8"
TIME_ZONE = "Asia/Vladivostok"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_STATIC_DIR = BASE_DIR / "frontend_static"
STATICFILES_DIRS = [FRONTEND_STATIC_DIR] if FRONTEND_STATIC_DIR.exists() else []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "480"))  # 8 hours
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "30"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Swagger
SPECTACULAR_SETTINGS = {
    "TITLE": "Supra API",
    "DESCRIPTION": "Автоматизированная система планирования трудовых ресурсов",
    "VERSION": "0.1.0",
}

# =============== КОНСТАНТЫ ПЛАНИРОВАНИЯ ===============
# Глобальные правила, не зависящие от конкретного сотрудника.
# Используются в scheduler, вынесены сюда чтобы менять в одном месте.
SCHEDULE_RULES = {
    "MIN_SHIFTS_PER_WEEK": 4,
    "MAX_EVENING_SHIFTS_PER_WEEK": 2,
    "SCHEDULE_HORIZON_DAYS": 30,       # расписание на месяц
}
# ======================================================
