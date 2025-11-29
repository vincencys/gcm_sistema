import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gcm_project.settings")

django_app = get_asgi_application()

try:
	from panic.routing import websocket_urlpatterns as panic_ws
except Exception:
	panic_ws = []

application = ProtocolTypeRouter({
	"http": django_app,
	"websocket": AuthMiddlewareStack(
		URLRouter(panic_ws)
	),
})
