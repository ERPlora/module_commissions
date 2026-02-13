"""Commissions module models."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import HubBaseModel


# =============================================================================
# Settings
# =============================================================================

class CommissionsSettings(HubBaseModel):
    """Per-hub commissions settings."""

    CALCULATION_BASIS_CHOICES = [
        ('gross', _("Gross Sales")),
        ('net', _("Net Sales (after discounts)")),
        ('profit', _("Profit Margin")),
    ]

    PAYOUT_FREQUENCY_CHOICES = [
        ('weekly', _("Weekly")),
        ('biweekly', _("Bi-weekly")),
        ('monthly', _("Monthly")),
        ('custom', _("Custom")),
    ]

    # Commission defaults
    default_commission_rate = models.DecimalField(
        _("Default Commission Rate (%)"), max_digits=5, decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    calculation_basis = models.CharField(
        _("Calculation Basis"), max_length=20,
        choices=CALCULATION_BASIS_CHOICES, default='net',
        help_text=_("What the commission percentage is based on")
    )

    # Payout settings
    payout_frequency = models.CharField(
        _("Payout Frequency"), max_length=20,
        choices=PAYOUT_FREQUENCY_CHOICES, default='monthly'
    )
    payout_day = models.PositiveSmallIntegerField(
        _("Payout Day"), default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text=_("Day of month/week for payouts")
    )
    minimum_payout_amount = models.DecimalField(
        _("Minimum Payout Amount"), max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Minimum amount required for payout")
    )

    # Tax settings
    apply_tax_withholding = models.BooleanField(_("Apply Tax Withholding"), default=False)
    tax_withholding_rate = models.DecimalField(
        _("Tax Withholding Rate (%)"), max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )

    # Display
    show_commission_on_receipt = models.BooleanField(_("Show Commission on Receipt"), default=False)
    show_pending_commission = models.BooleanField(_("Show Pending Commission to Staff"), default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'commissions_settings'
        verbose_name = _("Commissions Settings")
        verbose_name_plural = _("Commissions Settings")
        unique_together = [('hub_id',)]

    def __str__(self):
        return f"Commissions Settings (Hub {self.hub_id})"

    @classmethod
    def get_settings(cls, hub_id):
        settings, _ = cls.all_objects.get_or_create(hub_id=hub_id)
        return settings

    def calculate_tax(self, commission_amount):
        """Calculate tax withholding on a commission amount."""
        if not self.apply_tax_withholding or self.tax_withholding_rate <= 0:
            return commission_amount, Decimal('0')
        tax = (commission_amount * self.tax_withholding_rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        return commission_amount - tax, tax


# =============================================================================
# Rules
# =============================================================================

class CommissionRule(HubBaseModel):
    """Commission rules for different scenarios."""

    TYPE_CHOICES = [
        ('flat', _("Flat Amount")),
        ('percentage', _("Percentage")),
        ('tiered', _("Tiered (based on sales volume)")),
    ]

    name = models.CharField(_("Rule Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    # Type and value
    rule_type = models.CharField(
        _("Type"), max_length=20, choices=TYPE_CHOICES, default='percentage'
    )
    rate = models.DecimalField(
        _("Rate"), max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text=_("Percentage rate or flat amount")
    )

    # Applicability — real FKs (all optional, null = global)
    staff = models.ForeignKey(
        'staff.StaffMember', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_rules',
        verbose_name=_("Staff Member")
    )
    service = models.ForeignKey(
        'services.Service', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_rules',
        verbose_name=_("Service")
    )
    category = models.ForeignKey(
        'services.ServiceCategory', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_rules',
        verbose_name=_("Category")
    )
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_rules',
        verbose_name=_("Product")
    )

    # Tiered thresholds
    tier_thresholds = models.JSONField(
        _("Tier Thresholds"), default=list, blank=True,
        help_text=_("List of {min_amount, max_amount, rate} for tiered rules")
    )

    # Date range
    effective_from = models.DateField(_("Effective From"), null=True, blank=True)
    effective_until = models.DateField(_("Effective Until"), null=True, blank=True)

    # Priority
    priority = models.PositiveIntegerField(
        _("Priority"), default=0,
        help_text=_("Higher priority rules are applied first")
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'commissions_rule'
        verbose_name = _("Commission Rule")
        verbose_name_plural = _("Commission Rules")
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

    def is_applicable_on(self, check_date):
        if not self.is_active:
            return False
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_until and check_date > self.effective_until:
            return False
        return True

    def calculate_commission(self, amount, sales_volume=None):
        """Calculate commission for given amount."""
        if self.rule_type == 'flat':
            return self.rate
        elif self.rule_type == 'percentage':
            return amount * (self.rate / Decimal('100'))
        elif self.rule_type == 'tiered':
            if not self.tier_thresholds or sales_volume is None:
                return Decimal('0')
            for tier in sorted(self.tier_thresholds, key=lambda x: x.get('min_amount', 0)):
                min_amt = Decimal(str(tier.get('min_amount', 0)))
                max_amt = tier.get('max_amount')
                tier_rate = Decimal(str(tier.get('rate', 0)))
                if max_amt is None:
                    if sales_volume >= min_amt:
                        return amount * (tier_rate / Decimal('100'))
                else:
                    if min_amt <= sales_volume <= Decimal(str(max_amt)):
                        return amount * (tier_rate / Decimal('100'))
            return Decimal('0')
        return Decimal('0')


# =============================================================================
# Transactions
# =============================================================================

class CommissionTransaction(HubBaseModel):
    """Individual commission transaction record."""

    STATUS_CHOICES = [
        ('pending', _("Pending")),
        ('approved', _("Approved")),
        ('paid', _("Paid")),
        ('cancelled', _("Cancelled")),
        ('adjusted', _("Adjusted")),
    ]

    # Staff — real FK + snapshot
    staff = models.ForeignKey(
        'staff.StaffMember', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_transactions',
        verbose_name=_("Staff Member")
    )
    staff_name = models.CharField(_("Staff Name"), max_length=200)

    # Source references — real FKs
    sale = models.ForeignKey(
        'sales.Sale', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_transactions',
        verbose_name=_("Sale")
    )
    sale_reference = models.CharField(_("Sale Reference"), max_length=100, blank=True)
    appointment = models.ForeignKey(
        'appointments.Appointment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_transactions',
        verbose_name=_("Appointment")
    )

    # Amounts
    sale_amount = models.DecimalField(_("Sale Amount"), max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(_("Commission Rate (%)"), max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(_("Commission Amount"), max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(
        _("Tax Withheld"), max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    net_commission = models.DecimalField(_("Net Commission"), max_digits=10, decimal_places=2)

    # Rule
    rule = models.ForeignKey(
        CommissionRule, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',
        verbose_name=_("Rule")
    )

    # Status and payout
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    payout = models.ForeignKey(
        'CommissionPayout', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',
        verbose_name=_("Payout")
    )

    # Dates
    transaction_date = models.DateField(_("Transaction Date"), default=date.today)
    approved_at = models.DateTimeField(_("Approved At"), null=True, blank=True)
    approved_by = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_commissions',
        verbose_name=_("Approved By")
    )

    description = models.TextField(_("Description"), blank=True)
    notes = models.TextField(_("Notes"), blank=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'commissions_transaction'
        verbose_name = _("Commission Transaction")
        verbose_name_plural = _("Commission Transactions")
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['hub_id', 'staff_id', 'status']),
            models.Index(fields=['hub_id', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.staff_name}: {self.commission_amount} ({self.transaction_date})"

    def save(self, *args, **kwargs):
        if self.net_commission is None:
            self.net_commission = self.commission_amount - self.tax_amount
        super().save(*args, **kwargs)


# =============================================================================
# Payouts
# =============================================================================

class CommissionPayout(HubBaseModel):
    """Commission payout batch."""

    STATUS_CHOICES = [
        ('draft', _("Draft")),
        ('pending', _("Pending Approval")),
        ('approved', _("Approved")),
        ('processing', _("Processing")),
        ('completed', _("Completed")),
        ('failed', _("Failed")),
        ('cancelled', _("Cancelled")),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', _("Cash")),
        ('bank_transfer', _("Bank Transfer")),
        ('check', _("Check")),
        ('payroll', _("Added to Payroll")),
        ('other', _("Other")),
    ]

    reference = models.CharField(_("Reference"), max_length=50)

    # Staff — real FK + snapshot
    staff = models.ForeignKey(
        'staff.StaffMember', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_payouts',
        verbose_name=_("Staff Member")
    )
    staff_name = models.CharField(_("Staff Name"), max_length=200)

    # Period
    period_start = models.DateField(_("Period Start"))
    period_end = models.DateField(_("Period End"))

    # Amounts
    gross_amount = models.DecimalField(
        _("Gross Amount"), max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        _("Tax Withheld"), max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    adjustments_amount = models.DecimalField(
        _("Adjustments"), max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text=_("Manual adjustments (positive or negative)")
    )
    net_amount = models.DecimalField(
        _("Net Amount"), max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    transaction_count = models.PositiveIntegerField(_("Transaction Count"), default=0)

    # Status and payment
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES, default='draft'
    )
    payment_method = models.CharField(
        _("Payment Method"), max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True
    )
    payment_reference = models.CharField(
        _("Payment Reference"), max_length=100, blank=True,
        help_text=_("Check number, transfer ID, etc.")
    )

    # Workflow
    approved_at = models.DateTimeField(_("Approved At"), null=True, blank=True)
    approved_by = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_payouts',
        verbose_name=_("Approved By")
    )
    paid_at = models.DateTimeField(_("Paid At"), null=True, blank=True)
    paid_by = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='processed_payouts',
        verbose_name=_("Paid By")
    )
    notes = models.TextField(_("Notes"), blank=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'commissions_payout'
        verbose_name = _("Commission Payout")
        verbose_name_plural = _("Commission Payouts")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - {self.staff_name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        self.net_amount = self.gross_amount - self.tax_amount + self.adjustments_amount
        super().save(*args, **kwargs)

    def _generate_reference(self):
        prefix = f"PAY-{date.today().strftime('%Y%m')}-"
        existing = CommissionPayout.all_objects.filter(
            hub_id=self.hub_id, reference__startswith=prefix
        ).count()
        return f"{prefix}{existing + 1:04d}"

    @property
    def can_be_modified(self):
        return self.status in ['draft', 'pending']

    def recalculate_totals(self):
        agg = self.transactions.filter(
            status__in=['pending', 'approved', 'paid']
        ).aggregate(
            total_gross=Sum('commission_amount'),
            total_tax=Sum('tax_amount'),
            count=Count('id'),
        )
        self.gross_amount = agg['total_gross'] or Decimal('0')
        self.tax_amount = agg['total_tax'] or Decimal('0')
        self.transaction_count = agg['count'] or 0
        self.net_amount = self.gross_amount - self.tax_amount + self.adjustments_amount
        self.save()


# =============================================================================
# Adjustments
# =============================================================================

class CommissionAdjustment(HubBaseModel):
    """Manual commission adjustments."""

    TYPE_CHOICES = [
        ('bonus', _("Bonus")),
        ('correction', _("Correction")),
        ('deduction', _("Deduction")),
        ('refund_adjustment', _("Refund Adjustment")),
        ('other', _("Other")),
    ]

    # Staff — real FK + snapshot
    staff = models.ForeignKey(
        'staff.StaffMember', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commission_adjustments',
        verbose_name=_("Staff Member")
    )
    staff_name = models.CharField(_("Staff Name"), max_length=200)

    adjustment_type = models.CharField(
        _("Type"), max_length=20, choices=TYPE_CHOICES, default='correction'
    )
    amount = models.DecimalField(
        _("Amount"), max_digits=10, decimal_places=2,
        help_text=_("Positive for additions, negative for deductions")
    )
    reason = models.TextField(_("Reason"))

    payout = models.ForeignKey(
        CommissionPayout, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adjustments_list',
        verbose_name=_("Payout")
    )

    adjustment_date = models.DateField(_("Date"), default=date.today)
    created_by = models.ForeignKey(
        'accounts.LocalUser', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_adjustments',
        verbose_name=_("Created By")
    )

    class Meta(HubBaseModel.Meta):
        db_table = 'commissions_adjustment'
        verbose_name = _("Commission Adjustment")
        verbose_name_plural = _("Commission Adjustments")
        ordering = ['-adjustment_date', '-created_at']

    def __str__(self):
        return f"{self.staff_name}: {self.amount} ({self.get_adjustment_type_display()})"
