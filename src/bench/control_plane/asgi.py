import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.control_plane.settings")
application = get_asgi_application()
