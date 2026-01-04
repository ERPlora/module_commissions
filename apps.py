from django.apps import AppConfig


class CommissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commissions"
    verbose_name = "Commissions"

    def ready(self):
        pass

    # =========================================================================
    # HOOK HELPER METHODS
    # =========================================================================

    @staticmethod
    def do_after_sale_complete(sale) -> None:
        """Called after a sale is completed to calculate commission."""
        pass

    @staticmethod
    def do_before_payout_create(data: dict) -> dict:
        """Called before creating a payout. Can modify data."""
        return data

    @staticmethod
    def do_after_payout_process(payout) -> None:
        """Called after a payout is processed."""
        pass

    @staticmethod
    def do_after_rule_change(rule) -> None:
        """Called after a commission rule is changed."""
        pass

    @staticmethod
    def filter_transactions_list(queryset, request):
        """Filter transactions queryset before display."""
        return queryset

    @staticmethod
    def filter_payouts_list(queryset, request):
        """Filter payouts queryset before display."""
        return queryset
