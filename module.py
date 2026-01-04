"""
Commissions Module Configuration

This file defines the module metadata and navigation for the Commissions module.
Staff commission tracking and calculations for sales-based compensation.
Used by the @module_view decorator to automatically render navigation tabs.
"""
from django.utils.translation import gettext_lazy as _

# Module Identification
MODULE_ID = "commissions"
MODULE_NAME = _("Commissions")
MODULE_ICON = "wallet-outline"
MODULE_VERSION = "1.0.0"
MODULE_CATEGORY = "sales"

# Target Industries (business verticals this module is designed for)
MODULE_INDUSTRIES = [
    "retail",       # Retail stores
    "beauty",       # Beauty & wellness
    "consulting",   # Professional services
    "ecommerce",    # E-commerce
]

# Sidebar Menu Configuration
MENU = {
    "label": _("Commissions"),
    "icon": "wallet-outline",
    "order": 55,
    "show": True,
}

# Internal Navigation (Tabs)
NAVIGATION = [
    {
        "id": "dashboard",
        "label": _("Overview"),
        "icon": "stats-chart-outline",
        "view": "",
    },
    {
        "id": "transactions",
        "label": _("Transactions"),
        "icon": "receipt-outline",
        "view": "transactions",
    },
    {
        "id": "payouts",
        "label": _("Payouts"),
        "icon": "cash-outline",
        "view": "payouts",
    },
    {
        "id": "rules",
        "label": _("Rules"),
        "icon": "options-outline",
        "view": "rules",
    },
    {
        "id": "settings",
        "label": _("Settings"),
        "icon": "settings-outline",
        "view": "settings",
    },
]

# Module Dependencies
DEPENDENCIES = ["staff>=1.0.0", "sales>=1.0.0"]

# Default Settings
SETTINGS = {
    "calculation_mode": "percentage",
    "default_rate": 5.0,
    "payout_frequency": "monthly",
    "include_refunds": True,
}

# Permissions - tuple format (action_suffix, display_name)
PERMISSIONS = [
    ("view_commission", _("Can view commissions")),
    ("add_commission", _("Can add commissions")),
    ("change_commission", _("Can change commissions")),
    ("delete_commission", _("Can delete commissions")),
    ("view_transaction", _("Can view commission transactions")),
    ("manage_transaction", _("Can manage commission transactions")),
    ("view_payout", _("Can view payouts")),
    ("process_payout", _("Can process payouts")),
    ("view_rule", _("Can view commission rules")),
    ("add_rule", _("Can add commission rules")),
    ("change_rule", _("Can change commission rules")),
    ("delete_rule", _("Can delete commission rules")),
    ("view_settings", _("Can view settings")),
    ("change_settings", _("Can change settings")),
]

# Role-based permission assignments
ROLE_PERMISSIONS = {
    "admin": ["*"],  # All permissions
    "manager": [
        "view_commission",
        "add_commission",
        "change_commission",
        "view_transaction",
        "manage_transaction",
        "view_payout",
        "process_payout",
        "view_rule",
        "add_rule",
        "change_rule",
        "view_settings",
    ],
    "employee": [
        "view_commission",
        "view_transaction",
        "view_payout",
    ],
}
