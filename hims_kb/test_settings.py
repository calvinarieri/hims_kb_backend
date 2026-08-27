from .settings import *

TESTING = True

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

# Patch Postgres ArrayField placeholder, db_type, and get_db_prep_value for SQLite test runner compatibility
import json
try:
    from django.contrib.postgres.fields import ArrayField
    ArrayField.db_type = lambda self, connection: 'json'
    ArrayField.get_placeholder = lambda self, value=None, compiler=None, connection=None: '%s'
    ArrayField.get_db_prep_value = lambda self, value, connection, prepared=False: json.dumps([str(v) for v in value]) if isinstance(value, (list, tuple)) else value
except ImportError:
    pass
