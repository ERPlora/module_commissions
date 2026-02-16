from django.utils.translation import gettext_lazy as _

MODULE_ID = 'commissions'
MODULE_NAME = _('Commissions')
MODULE_VERSION = '1.0.0'

MENU = {
    'label': _('Commissions'),
    'icon': 'wallet-outline',
    'order': 55,
}

NAVIGATION = [
    {'id': 'dashboard', 'label': _('Overview'), 'icon': 'stats-chart-outline', 'view': ''},
    {'id': 'transactions', 'label': _('Transactions'), 'icon': 'receipt-outline', 'view': 'transactions'},
    {'id': 'payouts', 'label': _('Payouts'), 'icon': 'cash-outline', 'view': 'payouts'},
    {'id': 'rules', 'label': _('Rules'), 'icon': 'options-outline', 'view': 'rules'},
    {'id': 'adjustments', 'label': _('Adjustments'), 'icon': 'swap-horizontal-outline', 'view': 'adjustments'},
    {'id': 'settings', 'label': _('Settings'), 'icon': 'settings-outline', 'view': 'settings'},
]

# Module Dependencies
DEPENDENCIES = ['staff', 'services', 'inventory', 'sales', 'appointments']
