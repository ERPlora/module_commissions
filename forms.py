"""Commissions forms."""

from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import (
    CommissionsSettings,
    CommissionRule,
    CommissionAdjustment,
)


class CommissionRuleForm(forms.ModelForm):
    class Meta:
        model = CommissionRule
        fields = [
            'name', 'description', 'rule_type', 'rate',
            'effective_from', 'effective_until',
            'priority', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'description': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'rule_type': forms.Select(attrs={'class': 'select'}),
            'rate': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0'}),
            'effective_from': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'effective_until': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'priority': forms.NumberInput(attrs={'class': 'input', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'toggle'}),
        }


class CommissionAdjustmentForm(forms.ModelForm):
    class Meta:
        model = CommissionAdjustment
        fields = ['adjustment_type', 'amount', 'reason', 'adjustment_date']
        widgets = {
            'adjustment_type': forms.Select(attrs={'class': 'select'}),
            'amount': forms.NumberInput(attrs={'class': 'input', 'step': '0.01'}),
            'reason': forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'adjustment_date': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
        }


class PayoutCreateForm(forms.Form):
    staff_id = forms.UUIDField(widget=forms.HiddenInput())
    period_start = forms.DateField(widget=forms.DateInput(attrs={
        'class': 'input', 'type': 'date'
    }))
    period_end = forms.DateField(widget=forms.DateInput(attrs={
        'class': 'input', 'type': 'date'
    }))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'textarea', 'rows': 2})
    )


class PayoutProcessForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=[('', _('Select...'))] + list(dict(
            cash=_("Cash"),
            bank_transfer=_("Bank Transfer"),
            check=_("Check"),
            payroll=_("Added to Payroll"),
            other=_("Other"),
        ).items()),
        widget=forms.Select(attrs={'class': 'select'})
    )
    payment_reference = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input'})
    )


class CommissionsSettingsForm(forms.ModelForm):
    class Meta:
        model = CommissionsSettings
        fields = [
            'default_commission_rate', 'calculation_basis',
            'payout_frequency', 'payout_day', 'minimum_payout_amount',
            'apply_tax_withholding', 'tax_withholding_rate',
            'show_commission_on_receipt', 'show_pending_commission',
        ]
        widgets = {
            'default_commission_rate': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0', 'max': '100'}),
            'calculation_basis': forms.Select(attrs={'class': 'select'}),
            'payout_frequency': forms.Select(attrs={'class': 'select'}),
            'payout_day': forms.NumberInput(attrs={'class': 'input', 'min': '1', 'max': '31'}),
            'minimum_payout_amount': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0'}),
            'apply_tax_withholding': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'tax_withholding_rate': forms.NumberInput(attrs={'class': 'input', 'step': '0.01', 'min': '0', 'max': '100'}),
            'show_commission_on_receipt': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'show_pending_commission': forms.CheckboxInput(attrs={'class': 'toggle'}),
        }
