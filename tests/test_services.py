"""
Tests for commissions service layer.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from commissions.services import CommissionService
from commissions.models import (
    CommissionsConfig,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)


@pytest.mark.django_db
class TestCommissionServiceConfig:
    """Tests for config operations."""

    def test_get_config(self, commissions_config):
        """Test getting config."""
        config = CommissionService.get_config()
        assert config.pk == 1

    def test_get_config_creates_if_missing(self, db):
        """Test config is created if missing."""
        CommissionsConfig.objects.all().delete()
        config = CommissionService.get_config()
        assert config.pk == 1

    def test_update_config(self, commissions_config):
        """Test updating config."""
        success, error = CommissionService.update_config(
            default_commission_rate=Decimal('15.00'),
            calculation_basis='gross',
        )
        assert success is True
        assert error is None
        
        config = CommissionService.get_config()
        assert config.default_commission_rate == Decimal('15.00')
        assert config.calculation_basis == 'gross'


@pytest.mark.django_db
class TestCommissionServiceRules:
    """Tests for rule operations."""

    def test_get_rules(self, commission_rule, flat_rule):
        """Test getting all rules."""
        rules = CommissionService.get_rules()
        assert len(rules) == 2

    def test_get_rules_active_only(self, commission_rule, flat_rule):
        """Test getting active rules only."""
        flat_rule.is_active = False
        flat_rule.save()
        
        rules = CommissionService.get_rules(active_only=True)
        assert len(rules) == 1
        assert rules[0].name == 'Standard Commission'

    def test_get_rule(self, commission_rule):
        """Test getting single rule."""
        rule = CommissionService.get_rule(commission_rule.id)
        assert rule == commission_rule

    def test_get_rule_not_found(self, db):
        """Test getting non-existent rule."""
        rule = CommissionService.get_rule(99999)
        assert rule is None

    def test_create_rule(self, db):
        """Test creating rule."""
        rule, error = CommissionService.create_rule(
            name='New Rule',
            rule_type='percentage',
            rate=Decimal('12.50'),
            description='Test rule',
        )
        assert rule is not None
        assert error is None
        assert rule.name == 'New Rule'
        assert rule.rate == Decimal('12.50')

    def test_update_rule(self, commission_rule):
        """Test updating rule."""
        success, error = CommissionService.update_rule(
            commission_rule,
            name='Updated Rule',
            rate=Decimal('15.00'),
        )
        assert success is True
        commission_rule.refresh_from_db()
        assert commission_rule.name == 'Updated Rule'
        assert commission_rule.rate == Decimal('15.00')

    def test_delete_rule(self, commission_rule):
        """Test deleting unused rule."""
        rule_id = commission_rule.id
        success, error = CommissionService.delete_rule(commission_rule)
        assert success is True
        assert not CommissionRule.objects.filter(id=rule_id).exists()

    def test_delete_rule_with_transactions(self, commission_rule, commission_transaction):
        """Test cannot delete rule with transactions."""
        success, error = CommissionService.delete_rule(commission_rule)
        assert success is False
        assert 'transactions' in error.lower()

    def test_toggle_rule(self, commission_rule):
        """Test toggling rule status."""
        assert commission_rule.is_active is True
        
        is_active = CommissionService.toggle_rule(commission_rule)
        assert is_active is False
        
        is_active = CommissionService.toggle_rule(commission_rule)
        assert is_active is True


@pytest.mark.django_db
class TestCommissionCalculation:
    """Tests for commission calculation."""

    def test_calculate_percentage(self, commission_rule):
        """Test percentage commission calculation."""
        result = CommissionService.calculate_commission(
            Decimal('500.00'),
            commission_rule,
        )
        assert result == Decimal('50.00')

    def test_calculate_flat(self, flat_rule):
        """Test flat commission calculation."""
        result = CommissionService.calculate_commission(
            Decimal('500.00'),
            flat_rule,
        )
        assert result == Decimal('25.00')

    def test_calculate_with_tax(self, commissions_config):
        """Test commission with tax withholding."""
        net, tax = CommissionService.calculate_with_tax(
            Decimal('100.00'),
            commissions_config,
        )
        assert tax == Decimal('15.00')  # 15% tax
        assert net == Decimal('85.00')

    def test_calculate_no_tax(self, commissions_config):
        """Test commission without tax withholding."""
        commissions_config.apply_tax_withholding = False
        commissions_config.save()
        
        net, tax = CommissionService.calculate_with_tax(
            Decimal('100.00'),
            commissions_config,
        )
        assert tax == Decimal('0')
        assert net == Decimal('100.00')


@pytest.mark.django_db
class TestCommissionServiceTransactions:
    """Tests for transaction operations."""

    def test_get_transactions(self, commission_transaction, approved_transaction):
        """Test getting transactions."""
        transactions = CommissionService.get_transactions()
        assert len(transactions) == 2

    def test_get_transactions_by_status(self, commission_transaction, approved_transaction):
        """Test filtering transactions by status."""
        pending = CommissionService.get_transactions(status='pending')
        assert len(pending) == 1
        assert pending[0].status == 'pending'
        
        approved = CommissionService.get_transactions(status='approved')
        assert len(approved) == 1
        assert approved[0].status == 'approved'

    def test_get_transactions_by_staff(self, commission_transaction, commission_rule, commissions_config):
        """Test filtering transactions by staff."""
        # Create transaction for second staff
        CommissionTransaction.objects.create(
            staff_id=2,
            staff_name='Jane Smith',
            sale_amount=Decimal('100.00'),
            commission_rate=Decimal('10.00'),
            commission_amount=Decimal('10.00'),
            net_commission=Decimal('10.00'),
            rule=commission_rule,
            transaction_date=date.today(),
        )
        
        trans = CommissionService.get_transactions(staff_id=1)
        assert len(trans) == 1
        assert trans[0].staff_id == 1

    def test_create_transaction(self, commission_rule, commissions_config):
        """Test creating transaction."""
        trans, error = CommissionService.create_transaction(
            staff_id=1,
            staff_name='John Doe',
            sale_amount=Decimal('200.00'),
            commission_rate=Decimal('10.00'),
            commission_amount=Decimal('20.00'),
            rule=commission_rule,
            sale_reference='SALE-100',
        )
        assert trans is not None
        assert error is None
        assert trans.commission_amount == Decimal('20.00')
        assert trans.tax_amount == Decimal('3.00')  # 15% of 20

    def test_approve_transaction(self, commission_transaction):
        """Test approving transaction."""
        success, error = CommissionService.approve_transaction(commission_transaction)
        assert success is True
        commission_transaction.refresh_from_db()
        assert commission_transaction.status == 'approved'
        assert commission_transaction.approved_at is not None

    def test_approve_non_pending_fails(self, approved_transaction):
        """Test cannot approve non-pending transaction."""
        success, error = CommissionService.approve_transaction(approved_transaction)
        assert success is False
        assert 'approved' in error.lower()

    def test_reject_transaction(self, commission_transaction):
        """Test rejecting transaction."""
        success, error = CommissionService.reject_transaction(
            commission_transaction,
            reason='Invalid sale',
        )
        assert success is True
        commission_transaction.refresh_from_db()
        assert commission_transaction.status == 'cancelled'
        assert 'Invalid sale' in commission_transaction.notes

    def test_void_transaction(self, approved_transaction):
        """Test voiding transaction."""
        # Unlink from payout first
        approved_transaction.payout = None
        approved_transaction.save()
        
        success, error = CommissionService.void_transaction(
            approved_transaction,
            reason='Customer refund',
        )
        assert success is True
        approved_transaction.refresh_from_db()
        assert approved_transaction.status == 'cancelled'


@pytest.mark.django_db
class TestCommissionServicePayouts:
    """Tests for payout operations."""

    def test_get_payouts(self, commission_payout):
        """Test getting payouts."""
        payouts = CommissionService.get_payouts()
        assert len(payouts) == 1

    def test_get_payout(self, commission_payout):
        """Test getting single payout."""
        payout = CommissionService.get_payout(commission_payout.id)
        assert payout == commission_payout

    def test_create_payout(self, approved_transaction, commissions_config):
        """Test creating payout."""
        # Remove the payout link from the fixture
        approved_transaction.payout = None
        approved_transaction.save()
        
        payout, error = CommissionService.create_payout(
            staff_id=1,
            staff_name='John Doe',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
        )
        assert payout is not None
        assert error is None
        assert payout.transaction_count == 1

    def test_create_payout_no_transactions(self, commissions_config):
        """Test cannot create payout without transactions."""
        payout, error = CommissionService.create_payout(
            staff_id=999,  # Non-existent staff
            staff_name='Unknown',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
        )
        assert payout is None
        assert 'No approved' in error

    def test_approve_payout(self, commission_payout):
        """Test approving payout."""
        success, error = CommissionService.approve_payout(commission_payout)
        assert success is True
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'approved'

    def test_process_payout(self, commission_payout):
        """Test processing/paying payout."""
        success, error = CommissionService.process_payout(
            commission_payout,
            payment_method='bank_transfer',
            payment_reference='TXN-12345',
        )
        assert success is True
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'completed'
        assert commission_payout.paid_at is not None

    def test_cancel_payout(self, commission_payout, approved_transaction):
        """Test cancelling payout."""
        success, error = CommissionService.cancel_payout(
            commission_payout,
            reason='Employee left',
        )
        assert success is True
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'cancelled'
        
        # Transaction should be unlinked and back to approved
        approved_transaction.refresh_from_db()
        assert approved_transaction.payout is None
        assert approved_transaction.status == 'approved'


@pytest.mark.django_db
class TestCommissionServiceAdjustments:
    """Tests for adjustment operations."""

    def test_get_adjustments(self, commission_adjustment):
        """Test getting adjustments."""
        adjustments = CommissionService.get_adjustments()
        assert len(adjustments) == 1

    def test_create_adjustment(self, commissions_config):
        """Test creating adjustment."""
        adj, error = CommissionService.create_adjustment(
            staff_id=1,
            staff_name='John Doe',
            adjustment_type='bonus',
            amount=Decimal('50.00'),
            reason='Performance bonus',
        )
        assert adj is not None
        assert error is None
        assert adj.amount == Decimal('50.00')


@pytest.mark.django_db
class TestCommissionServiceReports:
    """Tests for reporting operations."""

    def test_get_staff_summary(self, commission_transaction, approved_transaction, commissions_config):
        """Test getting staff summary."""
        summary = CommissionService.get_staff_summary(1)  # staff_id=1
        assert summary['transaction_count'] == 2
        assert summary['total_commission'] == Decimal('70.00')  # 50 + 20

    def test_get_dashboard_stats(self, commission_transaction, approved_transaction, commissions_config):
        """Test getting dashboard stats."""
        stats = CommissionService.get_dashboard_stats()
        assert stats['transaction_count'] == 2
        assert stats['pending_transactions'] == 1

    def test_get_unpaid_balance(self, approved_transaction, commissions_config):
        """Test getting unpaid balance."""
        # Unlink from payout
        approved_transaction.payout = None
        approved_transaction.save()
        
        balance = CommissionService.get_unpaid_balance(1)  # staff_id=1
        assert balance == approved_transaction.net_commission
