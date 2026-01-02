"""
Commissions module models.
Manages staff commissions, commission rules, and payouts.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal


class CommissionsConfig(models.Model):
    """
    Singleton configuration for commissions module.
    """
    # Commission calculation settings
    default_commission_rate = models.DecimalField(
        _("Default Commission Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )

    # Calculation basis
    CALCULATION_BASIS_CHOICES = [
        ('gross', _("Gross Sales")),
        ('net', _("Net Sales (after discounts)")),
        ('profit', _("Profit Margin")),
    ]
    calculation_basis = models.CharField(
        _("Calculation Basis"),
        max_length=20,
        choices=CALCULATION_BASIS_CHOICES,
        default='net',
        help_text=_("What the commission percentage is based on")
    )

    # Payout settings
    PAYOUT_FREQUENCY_CHOICES = [
        ('weekly', _("Weekly")),
        ('biweekly', _("Bi-weekly")),
        ('monthly', _("Monthly")),
        ('custom', _("Custom")),
    ]
    payout_frequency = models.CharField(
        _("Payout Frequency"),
        max_length=20,
        choices=PAYOUT_FREQUENCY_CHOICES,
        default='monthly'
    )
    payout_day = models.PositiveSmallIntegerField(
        _("Payout Day"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text=_("Day of month/week for payouts")
    )
    minimum_payout_amount = models.DecimalField(
        _("Minimum Payout Amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Minimum amount required for payout")
    )

    # Tax settings
    apply_tax_withholding = models.BooleanField(
        _("Apply Tax Withholding"),
        default=False
    )
    tax_withholding_rate = models.DecimalField(
        _("Tax Withholding Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )

    # Display settings
    show_commission_on_receipt = models.BooleanField(
        _("Show Commission on Receipt"),
        default=False
    )
    show_pending_commission = models.BooleanField(
        _("Show Pending Commission to Staff"),
        default=True
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commissions Configuration")
        verbose_name_plural = _("Commissions Configuration")

    def __str__(self):
        return "Commissions Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Get or create the singleton configuration."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class CommissionRule(models.Model):
    """
    Commission rules for different scenarios.
    Can apply to specific staff, services, categories, or products.
    """
    TYPE_CHOICES = [
        ('flat', _("Flat Amount")),
        ('percentage', _("Percentage")),
        ('tiered', _("Tiered (based on sales volume)")),
    ]

    name = models.CharField(_("Rule Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)

    # Rule type and value
    rule_type = models.CharField(
        _("Type"),
        max_length=20,
        choices=TYPE_CHOICES,
        default='percentage'
    )
    rate = models.DecimalField(
        _("Rate"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Percentage rate or flat amount")
    )

    # Applicability (all optional - if all null, applies globally)
    staff_id = models.PositiveIntegerField(
        _("Staff ID"),
        null=True,
        blank=True,
        help_text=_("Apply to specific staff member")
    )
    service_id = models.PositiveIntegerField(
        _("Service ID"),
        null=True,
        blank=True,
        help_text=_("Apply to specific service")
    )
    category_id = models.PositiveIntegerField(
        _("Category ID"),
        null=True,
        blank=True,
        help_text=_("Apply to specific category")
    )
    product_id = models.PositiveIntegerField(
        _("Product ID"),
        null=True,
        blank=True,
        help_text=_("Apply to specific product")
    )

    # Tiered thresholds (for tiered rules)
    tier_thresholds = models.JSONField(
        _("Tier Thresholds"),
        default=list,
        blank=True,
        help_text=_("List of {min_amount, max_amount, rate} for tiered rules")
    )

    # Date range (optional)
    effective_from = models.DateField(
        _("Effective From"),
        null=True,
        blank=True
    )
    effective_until = models.DateField(
        _("Effective Until"),
        null=True,
        blank=True
    )

    # Priority (higher = processed first)
    priority = models.PositiveIntegerField(
        _("Priority"),
        default=0,
        help_text=_("Higher priority rules are applied first")
    )

    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commission Rule")
        verbose_name_plural = _("Commission Rules")
        ordering = ['-priority', 'name']

    def __str__(self):
        return self.name

    def is_applicable_on(self, check_date: date) -> bool:
        """Check if rule is applicable on given date."""
        if not self.is_active:
            return False
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_until and check_date > self.effective_until:
            return False
        return True

    def calculate_commission(self, amount: Decimal, sales_volume: Decimal = None) -> Decimal:
        """
        Calculate commission for given amount.

        Args:
            amount: Sale amount
            sales_volume: Total sales volume (for tiered rules)

        Returns:
            Commission amount
        """
        if self.rule_type == 'flat':
            return self.rate

        elif self.rule_type == 'percentage':
            return amount * (self.rate / Decimal('100'))

        elif self.rule_type == 'tiered':
            if not self.tier_thresholds or sales_volume is None:
                return Decimal('0')

            # Find applicable tier
            for tier in sorted(self.tier_thresholds, key=lambda x: x.get('min_amount', 0)):
                min_amt = Decimal(str(tier.get('min_amount', 0)))
                max_amt = tier.get('max_amount')
                tier_rate = Decimal(str(tier.get('rate', 0)))

                if max_amt is None:
                    if sales_volume >= min_amt:
                        return amount * (tier_rate / Decimal('100'))
                else:
                    max_amt = Decimal(str(max_amt))
                    if min_amt <= sales_volume <= max_amt:
                        return amount * (tier_rate / Decimal('100'))

            return Decimal('0')

        return Decimal('0')


class CommissionTransaction(models.Model):
    """
    Individual commission transaction record.
    Created when a sale is completed by a staff member.
    """
    STATUS_CHOICES = [
        ('pending', _("Pending")),
        ('approved', _("Approved")),
        ('paid', _("Paid")),
        ('cancelled', _("Cancelled")),
        ('adjusted', _("Adjusted")),
    ]

    # Staff member
    staff_id = models.PositiveIntegerField(_("Staff ID"))
    staff_name = models.CharField(
        _("Staff Name"),
        max_length=200,
        help_text=_("Cached staff name")
    )

    # Source reference
    sale_id = models.PositiveIntegerField(
        _("Sale ID"),
        null=True,
        blank=True
    )
    sale_reference = models.CharField(
        _("Sale Reference"),
        max_length=100,
        blank=True
    )
    appointment_id = models.PositiveIntegerField(
        _("Appointment ID"),
        null=True,
        blank=True
    )

    # Transaction details
    sale_amount = models.DecimalField(
        _("Sale Amount"),
        max_digits=10,
        decimal_places=2
    )
    commission_rate = models.DecimalField(
        _("Commission Rate (%)"),
        max_digits=5,
        decimal_places=2
    )
    commission_amount = models.DecimalField(
        _("Commission Amount"),
        max_digits=10,
        decimal_places=2
    )

    # Tax withholding
    tax_amount = models.DecimalField(
        _("Tax Withheld"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    net_commission = models.DecimalField(
        _("Net Commission"),
        max_digits=10,
        decimal_places=2
    )

    # Rule that generated this commission
    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name=_("Rule")
    )

    # Status and payout
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payout = models.ForeignKey(
        'CommissionPayout',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name=_("Payout")
    )

    # Dates
    transaction_date = models.DateField(_("Transaction Date"), default=date.today)
    approved_at = models.DateTimeField(_("Approved At"), null=True, blank=True)
    approved_by_id = models.PositiveIntegerField(_("Approved By"), null=True, blank=True)

    # Notes
    description = models.TextField(_("Description"), blank=True)
    notes = models.TextField(_("Notes"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commission Transaction")
        verbose_name_plural = _("Commission Transactions")
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f"{self.staff_name}: {self.commission_amount} ({self.transaction_date})"

    def save(self, *args, **kwargs):
        # Calculate net commission if not set
        if self.net_commission is None:
            self.net_commission = self.commission_amount - self.tax_amount
        super().save(*args, **kwargs)


class CommissionPayout(models.Model):
    """
    Commission payout batch.
    Groups multiple transactions for payment.
    """
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

    # Reference
    reference = models.CharField(
        _("Reference"),
        max_length=50,
        unique=True
    )

    # Staff member
    staff_id = models.PositiveIntegerField(_("Staff ID"))
    staff_name = models.CharField(
        _("Staff Name"),
        max_length=200,
        help_text=_("Cached staff name")
    )

    # Period covered
    period_start = models.DateField(_("Period Start"))
    period_end = models.DateField(_("Period End"))

    # Amounts
    gross_amount = models.DecimalField(
        _("Gross Amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_amount = models.DecimalField(
        _("Tax Withheld"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    adjustments = models.DecimalField(
        _("Adjustments"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Manual adjustments (positive or negative)")
    )
    net_amount = models.DecimalField(
        _("Net Amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Transaction count
    transaction_count = models.PositiveIntegerField(
        _("Transaction Count"),
        default=0
    )

    # Status and payment
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    payment_method = models.CharField(
        _("Payment Method"),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True
    )
    payment_reference = models.CharField(
        _("Payment Reference"),
        max_length=100,
        blank=True,
        help_text=_("Check number, transfer ID, etc.")
    )

    # Approval workflow
    approved_at = models.DateTimeField(_("Approved At"), null=True, blank=True)
    approved_by_id = models.PositiveIntegerField(_("Approved By"), null=True, blank=True)

    # Completion
    paid_at = models.DateTimeField(_("Paid At"), null=True, blank=True)
    paid_by_id = models.PositiveIntegerField(_("Paid By"), null=True, blank=True)

    notes = models.TextField(_("Notes"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commission Payout")
        verbose_name_plural = _("Commission Payouts")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - {self.staff_name}"

    def save(self, *args, **kwargs):
        # Generate reference if not set
        if not self.reference:
            from django.utils.crypto import get_random_string
            self.reference = f"PAY-{date.today().strftime('%Y%m')}-{get_random_string(6).upper()}"

        # Calculate net amount
        self.net_amount = self.gross_amount - self.tax_amount + self.adjustments

        super().save(*args, **kwargs)

    @property
    def can_be_modified(self) -> bool:
        """Check if payout can be modified."""
        return self.status in ['draft', 'pending']

    def recalculate_totals(self):
        """Recalculate totals from transactions."""
        from django.db.models import Sum, Count

        aggregates = self.transactions.filter(
            status__in=['pending', 'approved', 'paid']
        ).aggregate(
            total_gross=Sum('commission_amount'),
            total_tax=Sum('tax_amount'),
            count=Count('id')
        )

        self.gross_amount = aggregates['total_gross'] or Decimal('0')
        self.tax_amount = aggregates['total_tax'] or Decimal('0')
        self.transaction_count = aggregates['count'] or 0
        self.net_amount = self.gross_amount - self.tax_amount + self.adjustments
        self.save()


class CommissionAdjustment(models.Model):
    """
    Manual commission adjustments.
    Can be bonuses, corrections, deductions, etc.
    """
    TYPE_CHOICES = [
        ('bonus', _("Bonus")),
        ('correction', _("Correction")),
        ('deduction', _("Deduction")),
        ('refund_adjustment', _("Refund Adjustment")),
        ('other', _("Other")),
    ]

    staff_id = models.PositiveIntegerField(_("Staff ID"))
    staff_name = models.CharField(
        _("Staff Name"),
        max_length=200,
        help_text=_("Cached staff name")
    )

    adjustment_type = models.CharField(
        _("Type"),
        max_length=20,
        choices=TYPE_CHOICES,
        default='correction'
    )

    amount = models.DecimalField(
        _("Amount"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Positive for additions, negative for deductions")
    )

    reason = models.TextField(_("Reason"))

    # Link to payout if already included
    payout = models.ForeignKey(
        CommissionPayout,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjustments_list',
        verbose_name=_("Payout")
    )

    adjustment_date = models.DateField(_("Date"), default=date.today)
    created_by_id = models.PositiveIntegerField(_("Created By"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commission Adjustment")
        verbose_name_plural = _("Commission Adjustments")
        ordering = ['-adjustment_date', '-created_at']

    def __str__(self):
        return f"{self.staff_name}: {self.amount} ({self.get_adjustment_type_display()})"
