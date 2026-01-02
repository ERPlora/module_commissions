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
MODULE_CATEGORY = "sales"  # Changed from "operations" to valid category

# Target Industries (business verticals this module is designed for)
MODULE_INDUSTRIES = [
    "retail",       # Retail stores
    "salon",        # Beauty & wellness
    "professional", # Professional services
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

# Permissions
PERMISSIONS = [
    "commissions.view_commission",
    "commissions.add_commission",
    "commissions.change_commission",
    "commissions.delete_commission",
    "commissions.view_payout",
    "commissions.process_payout",
    "commissions.view_rule",
    "commissions.add_rule",
    "commissions.change_rule",
    "commissions.delete_rule",
]
