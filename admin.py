from django.contrib import admin
from .models import (
    CommissionsConfig,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)


@admin.register(CommissionsConfig)
class CommissionsConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'calculation_basis', 'payout_frequency', 'default_commission_rate', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']

    def has_add_permission(self, request):
        # Only allow one config instance
        return not CommissionsConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'rate', 'is_active', 'priority', 'created_at']
    list_filter = ['rule_type', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['-priority', 'name']


@admin.register(CommissionTransaction)
class CommissionTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'staff_name', 'sale_amount',
        'commission_amount', 'status', 'transaction_date'
    ]
    list_filter = ['status', 'transaction_date']
    search_fields = ['staff_name', 'sale_reference']
    date_hierarchy = 'transaction_date'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CommissionPayout)
class CommissionPayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'staff_name', 'gross_amount', 'net_amount', 'status',
        'period_start', 'period_end', 'paid_at'
    ]
    list_filter = ['status', 'period_start']
    search_fields = ['staff_name', 'reference']
    date_hierarchy = 'period_start'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CommissionAdjustment)
class CommissionAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'staff_name', 'adjustment_type', 'amount',
        'adjustment_date', 'created_at'
    ]
    list_filter = ['adjustment_type', 'adjustment_date']
    search_fields = ['staff_name', 'reason']
    date_hierarchy = 'adjustment_date'
    readonly_fields = ['created_at', 'updated_at']
