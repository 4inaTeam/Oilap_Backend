from django.apps import AppConfig


class FacturesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'factures'
    verbose_name = 'Factures Management'

    def ready(self):
        import factures.signals