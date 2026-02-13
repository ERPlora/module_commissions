"""Commissions URL Configuration."""

from django.urls import path
from . import views

app_name = 'commissions'

urlpatterns = [
    # Dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/<uuid:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<uuid:pk>/approve/', views.transaction_approve, name='transaction_approve'),
    path('transactions/<uuid:pk>/reject/', views.transaction_reject, name='transaction_reject'),

    # Payouts
    path('payouts/', views.payout_list, name='payout_list'),
    path('payouts/create/', views.payout_create, name='payout_create'),
    path('payouts/<uuid:pk>/', views.payout_detail, name='payout_detail'),
    path('payouts/<uuid:pk>/approve/', views.payout_approve, name='payout_approve'),
    path('payouts/<uuid:pk>/process/', views.payout_process, name='payout_process'),
    path('payouts/<uuid:pk>/cancel/', views.payout_cancel, name='payout_cancel'),

    # Rules
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/add/', views.rule_add, name='rule_add'),
    path('rules/<uuid:pk>/', views.rule_detail, name='rule_detail'),
    path('rules/<uuid:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<uuid:pk>/delete/', views.rule_delete, name='rule_delete'),
    path('rules/<uuid:pk>/toggle/', views.rule_toggle, name='rule_toggle'),

    # Adjustments
    path('adjustments/', views.adjustment_list, name='adjustment_list'),
    path('adjustments/add/', views.adjustment_add, name='adjustment_add'),
    path('adjustments/<uuid:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('adjustments/<uuid:pk>/delete/', views.adjustment_delete, name='adjustment_delete'),

    # Settings
    path('settings/', views.settings, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/toggle/', views.settings_toggle, name='settings_toggle'),
    path('settings/input/', views.settings_input, name='settings_input'),
    path('settings/reset/', views.settings_reset, name='settings_reset'),

    # API
    path('api/calculate/', views.api_calculate, name='api_calculate'),
    path('api/staff/<uuid:staff_pk>/summary/', views.api_staff_summary, name='api_staff_summary'),
]
