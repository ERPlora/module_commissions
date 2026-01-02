from django.urls import path
from . import views

app_name = 'commissions'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<int:pk>/approve/', views.transaction_approve, name='transaction_approve'),
    path('transactions/<int:pk>/reject/', views.transaction_reject, name='transaction_reject'),

    # Payouts
    path('payouts/', views.payout_list, name='payout_list'),
    path('payouts/create/', views.payout_create, name='payout_create'),
    path('payouts/<int:pk>/', views.payout_detail, name='payout_detail'),
    path('payouts/<int:pk>/approve/', views.payout_approve, name='payout_approve'),
    path('payouts/<int:pk>/process/', views.payout_process, name='payout_process'),
    path('payouts/<int:pk>/cancel/', views.payout_cancel, name='payout_cancel'),

    # Rules
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/create/', views.rule_create, name='rule_create'),
    path('rules/<int:pk>/', views.rule_detail, name='rule_detail'),
    path('rules/<int:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<int:pk>/delete/', views.rule_delete, name='rule_delete'),
    path('rules/<int:pk>/toggle/', views.rule_toggle, name='rule_toggle'),

    # Adjustments
    path('adjustments/', views.adjustment_list, name='adjustment_list'),
    path('adjustments/create/', views.adjustment_create, name='adjustment_create'),
    path('adjustments/<int:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('adjustments/<int:pk>/approve/', views.adjustment_approve, name='adjustment_approve'),
    path('adjustments/<int:pk>/reject/', views.adjustment_reject, name='adjustment_reject'),

    # Settings
    path('settings/', views.settings, name='settings'),

    # API / HTMX endpoints
    path('api/calculate/', views.api_calculate_commission, name='api_calculate'),
    path('api/staff/<int:staff_id>/summary/', views.api_staff_summary, name='api_staff_summary'),
]
