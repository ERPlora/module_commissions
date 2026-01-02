"""
Tests for commissions models.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from commissions.models import (
    CommissionsConfig,
    CommissionRule,
    CommissionTransaction,
    CommissionPayout,
    CommissionAdjustment,
)


@pytest.mark.django_db
class TestCommissionsConfig:
    """Tests for CommissionsConfig model."""

    def test_create_config(self, commissions_config):
        """Test creating commission config."""
        assert commissions_config.pk == 1
        assert commissions_config.calculation_basis == 'net'

    def test_config_singleton(self, commissions_config):
        """Test config is singleton (pk=1)."""
        config2 = CommissionsConfig.objects.get(pk=1)
        assert config2.id == commissions_config.id

    def test_config_defaults(self, db):
        """Test config default values."""
        # Clean up first
        CommissionsConfig.objects.all().delete()
        config = CommissionsConfig.objects.create()
        assert config.pk == 1  # Always pk=1
        assert config.default_commission_rate == Decimal('10.00')
        assert config.payout_frequency == 'monthly'

    def test_config_str(self, commissions_config):
        """Test config string representation."""
        assert 'Commission' in str(commissions_config)

    def test_get_config_method(self, db):
        """Test get_config class method."""
        CommissionsConfig.objects.all().delete()
        config = CommissionsConfig.get_config()
        assert config.pk == 1


@pytest.mark.django_db
class TestCommissionRule:
    """Tests for CommissionRule model."""

    def test_create_percentage_rule(self, commission_rule):
        """Test creating percentage rule."""
        assert commission_rule.name == 'Standard Commission'
        assert commission_rule.rule_type == 'percentage'
        assert commission_rule.rate == Decimal('10.00')
        assert commission_rule.is_active is True

    def test_create_flat_rule(self, flat_rule):
        """Test creating flat rule."""
        assert flat_rule.rule_type == 'flat'
        assert flat_rule.rate == Decimal('25.00')

    def test_create_tiered_rule(self, tiered_rule):
        """Test creating tiered rule."""
        assert tiered_rule.rule_type == 'tiered'
        assert len(tiered_rule.tier_thresholds) == 3
        assert tiered_rule.tier_thresholds[0]['rate'] == 5

    def test_rule_str(self, commission_rule):
        """Test rule string representation."""
        assert commission_rule.name in str(commission_rule)

    def test_rule_ordering(self, db):
        """Test rules ordered by priority."""
        rule1 = CommissionRule.objects.create(name='Low', priority=1, is_active=True)
        rule2 = CommissionRule.objects.create(name='High', priority=10, is_active=True)
        rule3 = CommissionRule.objects.create(name='Medium', priority=5, is_active=True)
        
        rules = CommissionRule.objects.all().order_by('-priority')
        assert list(rules) == [rule2, rule3, rule1]

    def test_rule_date_validity(self, db):
        """Test rule date validity fields."""
        today = date.today()
        rule = CommissionRule.objects.create(
            name='Limited Time',
            rule_type='percentage',
            rate=Decimal('15.00'),
            effective_from=today - timedelta(days=7),
            effective_until=today + timedelta(days=7),
            is_active=True,
        )
        assert rule.effective_from < today < rule.effective_until

    def test_calculate_percentage_commission(self, commission_rule):
        """Test percentage commission calculation."""
        result = commission_rule.calculate_commission(Decimal('500.00'))
        assert result == Decimal('50.00')

    def test_calculate_flat_commission(self, flat_rule):
        """Test flat commission calculation."""
        result = flat_rule.calculate_commission(Decimal('500.00'))
        assert result == Decimal('25.00')

    def test_calculate_tiered_commission(self, tiered_rule):
        """Test tiered commission calculation."""
        # At $500 volume, should use 5% tier
        result = tiered_rule.calculate_commission(Decimal('100.00'), Decimal('500.00'))
        assert result == Decimal('5.00')  # 5% of 100
        
        # At $2000 volume, should use 7.5% tier
        result = tiered_rule.calculate_commission(Decimal('100.00'), Decimal('2000.00'))
        assert result == Decimal('7.50')  # 7.5% of 100

    def test_is_applicable_on(self, commission_rule):
        """Test date applicability check."""
        assert commission_rule.is_applicable_on(date.today()) is True
        
        # Set date range
        commission_rule.effective_from = date.today() + timedelta(days=1)
        commission_rule.save()
        assert commission_rule.is_applicable_on(date.today()) is False


@pytest.mark.django_db
class TestCommissionTransaction:
    """Tests for CommissionTransaction model."""

    def test_create_transaction(self, commission_transaction):
        """Test creating transaction."""
        assert commission_transaction.staff_id == 1
        assert commission_transaction.staff_name == 'John Doe'
        assert commission_transaction.sale_amount == Decimal('500.00')
        assert commission_transaction.commission_amount == Decimal('50.00')

    def test_transaction_status_default(self, db, commission_rule):
        """Test transaction default status."""
        trans = CommissionTransaction.objects.create(
            staff_id=1,
            staff_name='Test User',
            sale_amount=Decimal('100.00'),
            commission_rate=Decimal('10.00'),
            commission_amount=Decimal('10.00'),
            net_commission=Decimal('10.00'),
            rule=commission_rule,
            transaction_date=date.today(),
        )
        assert trans.status == 'pending'

    def test_transaction_str(self, commission_transaction):
        """Test transaction string representation."""
        assert 'John Doe' in str(commission_transaction)

    def test_transaction_with_tax(self, commission_transaction):
        """Test transaction tax calculation."""
        assert commission_transaction.tax_amount == Decimal('7.50')
        assert commission_transaction.net_commission == Decimal('42.50')

    def test_transaction_auto_net_calculation(self, db, commission_rule):
        """Test automatic net commission calculation."""
        trans = CommissionTransaction.objects.create(
            staff_id=1,
            staff_name='Test User',
            sale_amount=Decimal('100.00'),
            commission_rate=Decimal('10.00'),
            commission_amount=Decimal('10.00'),
            tax_amount=Decimal('1.50'),
            net_commission=None,  # Should be calculated
            rule=commission_rule,
            transaction_date=date.today(),
        )
        assert trans.net_commission == Decimal('8.50')


@pytest.mark.django_db
class TestCommissionPayout:
    """Tests for CommissionPayout model."""

    def test_create_payout(self, commission_payout):
        """Test creating payout."""
        assert commission_payout.staff_id == 1
        assert commission_payout.status == 'pending'
        assert commission_payout.transaction_count == 1

    def test_payout_period(self, commission_payout):
        """Test payout period dates."""
        assert commission_payout.period_start < commission_payout.period_end

    def test_payout_reference_auto_generated(self, db):
        """Test payout reference is auto-generated."""
        payout = CommissionPayout.objects.create(
            staff_id=1,
            staff_name='Test User',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('100.00'),
        )
        assert payout.reference.startswith('PAY-')

    def test_payout_str(self, commission_payout):
        """Test payout string representation."""
        assert 'John Doe' in str(commission_payout)

    def test_payout_status_choices(self, db):
        """Test payout status choices."""
        for status in ['draft', 'pending', 'approved', 'completed', 'cancelled']:
            payout = CommissionPayout.objects.create(
                staff_id=1,
                staff_name='Test User',
                period_start=date.today() - timedelta(days=30),
                period_end=date.today(),
                gross_amount=Decimal('100.00'),
                net_amount=Decimal('100.00'),
                status=status,
            )
            assert payout.status == status

    def test_payout_can_be_modified(self, commission_payout):
        """Test can_be_modified property."""
        assert commission_payout.can_be_modified is True
        
        commission_payout.status = 'completed'
        commission_payout.save()
        assert commission_payout.can_be_modified is False


@pytest.mark.django_db
class TestCommissionAdjustment:
    """Tests for CommissionAdjustment model."""

    def test_create_adjustment(self, commission_adjustment):
        """Test creating adjustment."""
        assert commission_adjustment.staff_id == 1
        assert commission_adjustment.adjustment_type == 'bonus'
        assert commission_adjustment.amount == Decimal('100.00')

    def test_adjustment_types(self, db):
        """Test different adjustment types."""
        for adj_type in ['bonus', 'correction', 'deduction', 'refund_adjustment', 'other']:
            adj = CommissionAdjustment.objects.create(
                staff_id=1,
                staff_name='Test User',
                adjustment_type=adj_type,
                amount=Decimal('50.00'),
                reason='Test',
                adjustment_date=date.today(),
            )
            assert adj.adjustment_type == adj_type

    def test_negative_adjustment(self, db):
        """Test negative adjustment (deduction)."""
        adj = CommissionAdjustment.objects.create(
            staff_id=1,
            staff_name='Test User',
            adjustment_type='deduction',
            amount=Decimal('-50.00'),
            reason='Overpayment correction',
            adjustment_date=date.today(),
        )
        assert adj.amount < 0

    def test_adjustment_str(self, commission_adjustment):
        """Test adjustment string representation."""
        assert 'John Doe' in str(commission_adjustment)
