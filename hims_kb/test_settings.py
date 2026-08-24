from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Patch Postgres ArrayField for SQLite test runner compatibility
try:
    from django.contrib.postgres.fields import ArrayField
    ArrayField.db_type = lambda self, connection: 'json'
except ImportError:
    pass

