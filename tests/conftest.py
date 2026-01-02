"""
Fixtures for commissions module tests.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings


@pytest.fixture(autouse=True)
def disable_debug_toolbar(settings):
    """Disable debug toolbar for tests."""
    settings.DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda r: False}
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS = [
            app for app in settings.INSTALLED_APPS if app != 'debug_toolbar'
        ]
    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE if 'debug_toolbar' not in m
    ]


@pytest.fixture
def commissions_config(db):
    """Create commissions config."""
    from commissions.models import CommissionsConfig

    config, _ = CommissionsConfig.objects.get_or_create(
        pk=1,
        defaults={
            'calculation_basis': 'net',
            'default_commission_rate': Decimal('10.00'),
            'payout_frequency': 'monthly',
            'payout_day': 1,
            'minimum_payout_amount': Decimal('0'),  # No minimum for tests
            'apply_tax_withholding': True,
            'tax_withholding_rate': Decimal('15.00'),
        }
    )
    return config


@pytest.fixture
def commission_rule(db):
    """Create a percentage commission rule."""
    from commissions.models import CommissionRule
    
    return CommissionRule.objects.create(
        name='Standard Commission',
        rule_type='percentage',
        rate=Decimal('10.00'),
        is_active=True,
    )


@pytest.fixture
def flat_rule(db):
    """Create a flat commission rule."""
    from commissions.models import CommissionRule
    
    return CommissionRule.objects.create(
        name='Flat Bonus',
        rule_type='flat',
        rate=Decimal('25.00'),
        is_active=True,
    )


@pytest.fixture
def tiered_rule(db):
    """Create a tiered commission rule."""
    from commissions.models import CommissionRule
    
    return CommissionRule.objects.create(
        name='Tiered Sales',
        rule_type='tiered',
        tier_thresholds=[
            {'min_amount': 0, 'max_amount': 1000, 'rate': 5},
            {'min_amount': 1000, 'max_amount': 5000, 'rate': 7.5},
            {'min_amount': 5000, 'max_amount': None, 'rate': 10},
        ],
        is_active=True,
    )


@pytest.fixture
def commission_transaction(db, commission_rule, commissions_config):
    """Create a commission transaction."""
    from commissions.models import CommissionTransaction
    
    return CommissionTransaction.objects.create(
        staff_id=1,
        staff_name='John Doe',
        sale_id=100,
        sale_reference='SALE-001',
        sale_amount=Decimal('500.00'),
        commission_rate=Decimal('10.00'),
        commission_amount=Decimal('50.00'),
        tax_amount=Decimal('7.50'),
        net_commission=Decimal('42.50'),
        rule=commission_rule,
        transaction_date=date.today(),
        status='pending',
    )


@pytest.fixture
def approved_transaction(db, commission_rule, commissions_config):
    """Create an approved commission transaction."""
    from commissions.models import CommissionTransaction
    
    return CommissionTransaction.objects.create(
        staff_id=1,
        staff_name='John Doe',
        sale_id=101,
        sale_reference='SALE-002',
        sale_amount=Decimal('200.00'),
        commission_rate=Decimal('10.00'),
        commission_amount=Decimal('20.00'),
        tax_amount=Decimal('3.00'),
        net_commission=Decimal('17.00'),
        rule=commission_rule,
        transaction_date=date.today(),
        status='approved',
    )


@pytest.fixture
def commission_payout(db, approved_transaction):
    """Create a commission payout."""
    from commissions.models import CommissionPayout
    
    payout = CommissionPayout.objects.create(
        staff_id=1,
        staff_name='John Doe',
        period_start=date.today() - timedelta(days=30),
        period_end=date.today(),
        gross_amount=approved_transaction.commission_amount,
        tax_amount=approved_transaction.tax_amount,
        net_amount=approved_transaction.net_commission,
        transaction_count=1,
        status='pending',
    )
    
    # Link transaction
    approved_transaction.payout = payout
    approved_transaction.save()
    
    return payout


@pytest.fixture
def commission_adjustment(db, commissions_config):
    """Create a commission adjustment."""
    from commissions.models import CommissionAdjustment
    
    return CommissionAdjustment.objects.create(
        staff_id=1,
        staff_name='John Doe',
        adjustment_type='bonus',
        amount=Decimal('100.00'),
        reason='Monthly bonus',
        adjustment_date=date.today(),
    )


@pytest.fixture
def client_with_session(client, db):
    """Client with session for view tests."""
    from django.contrib.sessions.backends.db import SessionStore
    session = SessionStore()
    session.create()
    client.cookies['sessionid'] = session.session_key
    return client
