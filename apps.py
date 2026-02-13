from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'commissions'
    label = 'commissions'
    verbose_name = _('Commissions')

    def ready(self):
        pass
