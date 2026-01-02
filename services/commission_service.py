"""
Commission Service - Business logic for commission calculations and management.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from django.utils.crypto import get_random_string

from ..models import (
    CommissionsConfig,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)


class CommissionService:
    """Service class for commission operations."""

    # ==================== Config ====================

    @staticmethod
    def get_config() -> CommissionsConfig:
        """Get or create the singleton config."""
        return CommissionsConfig.get_config()

    @staticmethod
    def update_config(**kwargs) -> Tuple[bool, Optional[str]]:
        """Update commission configuration."""
        try:
            config = CommissionService.get_config()
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            config.save()
            return True, None
        except Exception as e:
            return False, str(e)

    # ==================== Rules ====================

    @staticmethod
    def get_rules(active_only: bool = False) -> List[CommissionRule]:
        """Get all commission rules."""
        qs = CommissionRule.objects.all().order_by('-priority', 'name')
        if active_only:
            qs = qs.filter(is_active=True)
        return list(qs)

    @staticmethod
    def get_rule(rule_id: int) -> Optional[CommissionRule]:
        """Get a specific rule by ID."""
        try:
            return CommissionRule.objects.get(pk=rule_id)
        except CommissionRule.DoesNotExist:
            return None

    @staticmethod
    def create_rule(
        name: str,
        rule_type: str = 'percentage',
        rate: Decimal = Decimal('0'),
        **kwargs
    ) -> Tuple[Optional[CommissionRule], Optional[str]]:
        """Create a new commission rule."""
        try:
            rule = CommissionRule.objects.create(
                name=name,
                rule_type=rule_type,
                rate=rate,
                **kwargs
            )
            return rule, None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def update_rule(rule: CommissionRule, **kwargs) -> Tuple[bool, Optional[str]]:
        """Update an existing rule."""
        try:
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            rule.save()
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete_rule(rule: CommissionRule) -> Tuple[bool, Optional[str]]:
        """Delete a commission rule."""
        try:
            # Check if rule has been used
            if CommissionTransaction.objects.filter(rule=rule).exists():
                return False, "Cannot delete rule that has been used in transactions"
            rule.delete()
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def toggle_rule(rule: CommissionRule) -> bool:
        """Toggle rule active status."""
        rule.is_active = not rule.is_active
        rule.save(update_fields=['is_active', 'updated_at'])
        return rule.is_active

    @staticmethod
    def get_applicable_rules(
        staff_id: Optional[int] = None,
        service_id: Optional[int] = None,
        category_id: Optional[int] = None,
        product_id: Optional[int] = None,
    ) -> List[CommissionRule]:
        """Get rules applicable to given criteria."""
        rules = CommissionRule.objects.filter(is_active=True)

        # Filter by date validity
        today = date.today()
        rules = rules.filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=today),
            Q(effective_until__isnull=True) | Q(effective_until__gte=today),
        )

        applicable = []
        for rule in rules.order_by('-priority'):
            # Check staff applicability
            if rule.staff_id and staff_id and rule.staff_id != staff_id:
                continue

            # Check product/service/category applicability
            if rule.product_id and product_id and rule.product_id != product_id:
                continue
            if rule.category_id and category_id and rule.category_id != category_id:
                continue
            if rule.service_id and service_id and rule.service_id != service_id:
                continue

            applicable.append(rule)

        return applicable

    # ==================== Commission Calculation ====================

    @staticmethod
    def calculate_commission(
        amount: Decimal,
        rule: CommissionRule,
        sales_volume: Decimal = None,
    ) -> Decimal:
        """Calculate commission amount based on rule type."""
        return rule.calculate_commission(amount, sales_volume)

    @staticmethod
    def calculate_with_tax(
        commission_amount: Decimal,
        config: Optional[CommissionsConfig] = None,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate commission with tax withholding."""
        if config is None:
            config = CommissionService.get_config()

        if not config.apply_tax_withholding or config.tax_withholding_rate <= 0:
            return commission_amount, Decimal('0')

        tax_amount = commission_amount * (config.tax_withholding_rate / Decimal('100'))
        tax_amount = tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net_amount = commission_amount - tax_amount

        return net_amount, tax_amount

    # ==================== Transactions ====================

    @staticmethod
    def get_transactions(
        staff_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[CommissionTransaction]:
        """Get commission transactions with filters."""
        qs = CommissionTransaction.objects.select_related('rule')

        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if status:
            qs = qs.filter(status=status)
        if start_date:
            qs = qs.filter(transaction_date__gte=start_date)
        if end_date:
            qs = qs.filter(transaction_date__lte=end_date)

        return list(qs.order_by('-transaction_date', '-created_at'))

    @staticmethod
    def get_transaction(transaction_id: int) -> Optional[CommissionTransaction]:
        """Get a specific transaction."""
        try:
            return CommissionTransaction.objects.select_related(
                'rule', 'payout'
            ).get(pk=transaction_id)
        except CommissionTransaction.DoesNotExist:
            return None

    @staticmethod
    def create_transaction(
        staff_id: int,
        staff_name: str,
        sale_amount: Decimal,
        commission_rate: Decimal,
        commission_amount: Decimal,
        rule: Optional[CommissionRule] = None,
        sale_id: Optional[int] = None,
        sale_reference: str = '',
        appointment_id: Optional[int] = None,
        transaction_date: Optional[date] = None,
        description: str = '',
        notes: str = '',
    ) -> Tuple[Optional[CommissionTransaction], Optional[str]]:
        """Create a new commission transaction."""
        try:
            config = CommissionService.get_config()

            # Calculate tax
            net_commission, tax_amount = CommissionService.calculate_with_tax(
                commission_amount, config
            )

            trans = CommissionTransaction.objects.create(
                staff_id=staff_id,
                staff_name=staff_name,
                sale_id=sale_id,
                sale_reference=sale_reference,
                appointment_id=appointment_id,
                sale_amount=sale_amount,
                commission_rate=commission_rate,
                commission_amount=commission_amount,
                tax_amount=tax_amount,
                net_commission=net_commission,
                rule=rule,
                transaction_date=transaction_date or date.today(),
                description=description,
                notes=notes,
                status='pending',
            )
            return trans, None
        except Exception as e:
            return None, str(e)

    @staticmethod
    def approve_transaction(
        transaction: CommissionTransaction,
        approved_by_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Approve a pending transaction."""
        if transaction.status != 'pending':
            return False, f"Transaction is {transaction.status}, cannot approve"

        transaction.status = 'approved'
        transaction.approved_by_id = approved_by_id
        transaction.approved_at = timezone.now()
        transaction.save(update_fields=['status', 'approved_by_id', 'approved_at', 'updated_at'])
        return True, None

    @staticmethod
    def reject_transaction(
        transaction: CommissionTransaction,
        reason: str = '',
    ) -> Tuple[bool, Optional[str]]:
        """Reject a pending transaction."""
        if transaction.status != 'pending':
            return False, f"Transaction is {transaction.status}, cannot reject"

        transaction.status = 'cancelled'
        if reason:
            transaction.notes = f"{transaction.notes}\nRejection reason: {reason}".strip()
        transaction.save(update_fields=['status', 'notes', 'updated_at'])
        return True, None

    @staticmethod
    def void_transaction(
        transaction: CommissionTransaction,
        reason: str = '',
    ) -> Tuple[bool, Optional[str]]:
        """Void an approved transaction."""
        if transaction.status == 'paid':
            return False, "Cannot void a paid transaction"
        if transaction.payout:
            return False, "Cannot void transaction that is part of a payout"

        transaction.status = 'cancelled'
        if reason:
            transaction.notes = f"{transaction.notes}\nVoid reason: {reason}".strip()
        transaction.save(update_fields=['status', 'notes', 'updated_at'])
        return True, None

    # ==================== Payouts ====================

    @staticmethod
    def get_payouts(
        staff_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[CommissionPayout]:
        """Get payouts with filters."""
        qs = CommissionPayout.objects.all()

        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if status:
            qs = qs.filter(status=status)
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_end__lte=end_date)

        return list(qs.order_by('-period_end', '-created_at'))

    @staticmethod
    def get_payout(payout_id: int) -> Optional[CommissionPayout]:
        """Get a specific payout."""
        try:
            return CommissionPayout.objects.prefetch_related(
                'transactions', 'adjustments_list'
            ).get(pk=payout_id)
        except CommissionPayout.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def create_payout(
        staff_id: int,
        staff_name: str,
        period_start: date,
        period_end: date,
        notes: str = '',
    ) -> Tuple[Optional[CommissionPayout], Optional[str]]:
        """Create a payout for approved transactions in a period."""
        # Get approved, unpaid transactions
        transactions = CommissionTransaction.objects.filter(
            staff_id=staff_id,
            status='approved',
            payout__isnull=True,
            transaction_date__gte=period_start,
            transaction_date__lte=period_end,
        )

        if not transactions.exists():
            return None, "No approved transactions found for this period"

        # Calculate totals
        trans_total = transactions.aggregate(
            total_gross=Sum('commission_amount'),
            total_tax=Sum('tax_amount'),
            count=Count('id'),
        )

        config = CommissionService.get_config()

        gross_amount = trans_total['total_gross'] or Decimal('0')
        tax_amount = trans_total['total_tax'] or Decimal('0')
        transaction_count = trans_total['count'] or 0

        # Check minimum payout
        if config.minimum_payout_amount > 0 and gross_amount < config.minimum_payout_amount:
            return None, f"Total amount {gross_amount} is below minimum payout {config.minimum_payout_amount}"

        # Create payout
        payout = CommissionPayout.objects.create(
            staff_id=staff_id,
            staff_name=staff_name,
            period_start=period_start,
            period_end=period_end,
            gross_amount=gross_amount,
            tax_amount=tax_amount,
            net_amount=gross_amount - tax_amount,
            transaction_count=transaction_count,
            notes=notes,
            status='pending',
        )

        # Link transactions
        transactions.update(payout=payout)

        return payout, None

    @staticmethod
    def approve_payout(
        payout: CommissionPayout,
        approved_by_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Approve a pending payout."""
        if payout.status not in ['draft', 'pending']:
            return False, f"Payout is {payout.status}, cannot approve"

        payout.status = 'approved'
        payout.approved_by_id = approved_by_id
        payout.approved_at = timezone.now()
        payout.save(update_fields=['status', 'approved_by_id', 'approved_at', 'updated_at'])
        return True, None

    @staticmethod
    def process_payout(
        payout: CommissionPayout,
        payment_method: str = '',
        payment_reference: str = '',
        paid_by_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Mark payout as paid."""
        if payout.status not in ['pending', 'approved']:
            return False, f"Payout is {payout.status}, cannot process"

        payout.status = 'completed'
        payout.payment_method = payment_method
        payout.payment_reference = payment_reference
        payout.paid_at = timezone.now()
        payout.paid_by_id = paid_by_id
        payout.save(update_fields=[
            'status', 'payment_method', 'payment_reference', 'paid_at', 'paid_by_id', 'updated_at'
        ])

        # Mark transactions as paid
        payout.transactions.update(status='paid')

        return True, None

    @staticmethod
    @transaction.atomic
    def cancel_payout(
        payout: CommissionPayout,
        reason: str = '',
    ) -> Tuple[bool, Optional[str]]:
        """Cancel a payout and release transactions."""
        if payout.status == 'completed':
            return False, "Cannot cancel a completed payout"

        # Unlink transactions - set them back to approved
        payout.transactions.update(payout=None, status='approved')

        payout.status = 'cancelled'
        if reason:
            payout.notes = f"{payout.notes}\nCancellation reason: {reason}".strip()
        payout.save(update_fields=['status', 'notes', 'updated_at'])

        return True, None

    # ==================== Adjustments ====================

    @staticmethod
    def get_adjustments(
        staff_id: Optional[int] = None,
        adjustment_type: Optional[str] = None,
    ) -> List[CommissionAdjustment]:
        """Get adjustments with filters."""
        qs = CommissionAdjustment.objects.all()

        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if adjustment_type:
            qs = qs.filter(adjustment_type=adjustment_type)

        return list(qs.order_by('-adjustment_date', '-created_at'))

    @staticmethod
    def get_adjustment(adjustment_id: int) -> Optional[CommissionAdjustment]:
        """Get a specific adjustment."""
        try:
            return CommissionAdjustment.objects.select_related('payout').get(pk=adjustment_id)
        except CommissionAdjustment.DoesNotExist:
            return None

    @staticmethod
    def create_adjustment(
        staff_id: int,
        staff_name: str,
        adjustment_type: str,
        amount: Decimal,
        reason: str = '',
        adjustment_date: Optional[date] = None,
        created_by_id: Optional[int] = None,
    ) -> Tuple[Optional[CommissionAdjustment], Optional[str]]:
        """Create a manual adjustment."""
        try:
            adj = CommissionAdjustment.objects.create(
                staff_id=staff_id,
                staff_name=staff_name,
                adjustment_type=adjustment_type,
                amount=amount,
                reason=reason,
                adjustment_date=adjustment_date or date.today(),
                created_by_id=created_by_id,
            )
            return adj, None
        except Exception as e:
            return None, str(e)

    # ==================== Reports & Analytics ====================

    @staticmethod
    def get_staff_summary(
        staff_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get commission summary for a staff member."""
        qs = CommissionTransaction.objects.filter(staff_id=staff_id)

        if start_date:
            qs = qs.filter(transaction_date__gte=start_date)
        if end_date:
            qs = qs.filter(transaction_date__lte=end_date)

        totals = qs.aggregate(
            total_sales=Sum('sale_amount'),
            total_commission=Sum('commission_amount'),
            total_net=Sum('net_commission'),
            total_tax=Sum('tax_amount'),
            count=Count('id'),
        )

        pending = qs.filter(status='pending').aggregate(
            amount=Sum('net_commission'),
            count=Count('id'),
        )

        paid = qs.filter(status='paid').aggregate(
            amount=Sum('net_commission'),
            count=Count('id'),
        )

        # Get adjustments
        adj_qs = CommissionAdjustment.objects.filter(staff_id=staff_id)
        if start_date:
            adj_qs = adj_qs.filter(adjustment_date__gte=start_date)
        if end_date:
            adj_qs = adj_qs.filter(adjustment_date__lte=end_date)

        adjustments = adj_qs.aggregate(
            total=Sum('amount'),
            count=Count('id'),
        )

        return {
            'total_sales': totals['total_sales'] or Decimal('0'),
            'total_commission': totals['total_commission'] or Decimal('0'),
            'total_net': totals['total_net'] or Decimal('0'),
            'total_tax': totals['total_tax'] or Decimal('0'),
            'transaction_count': totals['count'] or 0,
            'pending_amount': pending['amount'] or Decimal('0'),
            'pending_count': pending['count'] or 0,
            'paid_amount': paid['amount'] or Decimal('0'),
            'paid_count': paid['count'] or 0,
            'adjustment_total': adjustments['total'] or Decimal('0'),
            'adjustment_count': adjustments['count'] or 0,
        }

    @staticmethod
    def get_dashboard_stats(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get dashboard statistics."""
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()

        # Transaction stats
        trans_qs = CommissionTransaction.objects.filter(
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
        )

        trans_stats = trans_qs.aggregate(
            total_commission=Sum('commission_amount'),
            total_net=Sum('net_commission'),
            total_tax=Sum('tax_amount'),
            count=Count('id'),
        )

        # Pending approvals
        pending_trans = CommissionTransaction.objects.filter(status='pending').count()
        pending_payouts = CommissionPayout.objects.filter(status='pending').count()

        # Top earners
        top_earners = (
            trans_qs.filter(status__in=['approved', 'paid'])
            .values('staff_id', 'staff_name')
            .annotate(total=Sum('net_commission'))
            .order_by('-total')[:5]
        )

        # Payouts this period
        payout_stats = CommissionPayout.objects.filter(
            period_start__gte=start_date,
            period_end__lte=end_date,
        ).aggregate(
            total_paid=Sum('net_amount', filter=Q(status='completed')),
            paid_count=Count('id', filter=Q(status='completed')),
            pending_total=Sum('net_amount', filter=Q(status='pending')),
            pending_count=Count('id', filter=Q(status='pending')),
        )

        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_commission': trans_stats['total_commission'] or Decimal('0'),
            'total_net': trans_stats['total_net'] or Decimal('0'),
            'total_tax': trans_stats['total_tax'] or Decimal('0'),
            'transaction_count': trans_stats['count'] or 0,
            'pending_transactions': pending_trans,
            'pending_payouts': pending_payouts,
            'total_pending': pending_trans + pending_payouts,
            'top_earners': list(top_earners),
            'payouts_total_paid': payout_stats['total_paid'] or Decimal('0'),
            'payouts_paid_count': payout_stats['paid_count'] or 0,
            'payouts_pending_total': payout_stats['pending_total'] or Decimal('0'),
            'payouts_pending_count': payout_stats['pending_count'] or 0,
        }

    @staticmethod
    def get_unpaid_balance(staff_id: int) -> Decimal:
        """Get total unpaid commission balance for a staff member."""
        trans_total = CommissionTransaction.objects.filter(
            staff_id=staff_id,
            status='approved',
            payout__isnull=True,
        ).aggregate(total=Sum('net_commission'))['total'] or Decimal('0')

        adj_total = CommissionAdjustment.objects.filter(
            staff_id=staff_id,
            payout__isnull=True,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return trans_total + adj_total
