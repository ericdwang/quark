from settings import *

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'noiro_test.db',
    },
}

# We don't need to test these apps.
BLACKLISTED_APPS = ['django_evolution', 'django.contrib.flatpages']
for app in BLACKLISTED_APPS:
    if app in INSTALLED_APPS:
        INSTALLED_APPS.remove(app)

# These middleware classes mess up testing.
BLACKLISTED_MIDDLEWARE = [
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware']
for middleware in BLACKLISTED_MIDDLEWARE:
    if middleware in MIDDLEWARE_CLASSES:
        MIDDLEWARE_CLASSES.remove(middleware)
