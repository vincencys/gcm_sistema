from django.apps import AppConfig


class PanicConfig(AppConfig):
	name = 'panic'

	def ready(self):
		# Importa sinais para conectar post_save
		try:
			from . import signals  # noqa: F401
		except Exception as e:
			# Evita quebrar startup se houver erro inicial; log simplificado
			import logging
			logging.getLogger(__name__).warning(f"Falha ao carregar sinais panic: {e}")
