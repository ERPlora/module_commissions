"""
Tests for commissions views.
Note: View rendering tests are skipped when templates are not available.
These tests focus on POST actions and API endpoints which don't require templates.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


@pytest.mark.django_db
class TestTransactionActions:
    """Tests for transaction action views."""

    def test_transaction_approve(self, client_with_session, commission_transaction, commissions_config):
        """Test approving transaction."""
        response = client_with_session.post(
            f'/modules/commissions/transactions/{commission_transaction.id}/approve/'
        )
        assert response.status_code in [200, 302]
        commission_transaction.refresh_from_db()
        assert commission_transaction.status == 'approved'

    def test_transaction_reject(self, client_with_session, commission_transaction, commissions_config):
        """Test rejecting transaction."""
        response = client_with_session.post(
            f'/modules/commissions/transactions/{commission_transaction.id}/reject/',
            {'reason': 'Invalid'}
        )
        assert response.status_code in [200, 302]
        commission_transaction.refresh_from_db()
        assert commission_transaction.status == 'cancelled'


@pytest.mark.django_db
class TestPayoutActions:
    """Tests for payout action views."""

    def test_payout_approve(self, client_with_session, commission_payout, commissions_config):
        """Test approving payout."""
        response = client_with_session.post(
            f'/modules/commissions/payouts/{commission_payout.id}/approve/'
        )
        assert response.status_code == 302
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'approved'

    def test_payout_process(self, client_with_session, commission_payout, commissions_config):
        """Test processing payout."""
        response = client_with_session.post(
            f'/modules/commissions/payouts/{commission_payout.id}/process/',
            {'payment_method': 'cash', 'payment_reference': 'REF-001'}
        )
        assert response.status_code == 302
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'completed'

    def test_payout_cancel(self, client_with_session, commission_payout, commissions_config):
        """Test cancelling payout."""
        response = client_with_session.post(
            f'/modules/commissions/payouts/{commission_payout.id}/cancel/',
            {'reason': 'Cancelled by admin'}
        )
        assert response.status_code == 302
        commission_payout.refresh_from_db()
        assert commission_payout.status == 'cancelled'


@pytest.mark.django_db
class TestRuleActions:
    """Tests for rule action views."""

    def test_rule_toggle(self, client_with_session, commission_rule, commissions_config):
        """Test toggling rule status."""
        assert commission_rule.is_active is True
        
        response = client_with_session.post(f'/modules/commissions/rules/{commission_rule.id}/toggle/')
        assert response.status_code in [200, 302]
        
        commission_rule.refresh_from_db()
        assert commission_rule.is_active is False

    def test_rule_delete(self, client_with_session, commission_rule, commissions_config):
        """Test deleting rule."""
        rule_id = commission_rule.id
        response = client_with_session.post(f'/modules/commissions/rules/{rule_id}/delete/')
        assert response.status_code == 302
        
        from commissions.models import CommissionRule
        assert not CommissionRule.objects.filter(id=rule_id).exists()


@pytest.mark.django_db
class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_calculate_commission_api(self, client_with_session, commission_rule, commissions_config):
        """Test commission calculation API."""
        response = client_with_session.post('/modules/commissions/api/calculate/', {
            'amount': '500.00',
            'rule_id': commission_rule.id,
        })
        assert response.status_code == 200
        data = response.json()
        # Check the value is correct (50.00), regardless of decimal places
        assert Decimal(data['commission_amount']) == Decimal('50.00')

    def test_calculate_commission_api_missing_rule(self, client_with_session, commissions_config):
        """Test API with missing rule."""
        response = client_with_session.post('/modules/commissions/api/calculate/', {
            'amount': '500.00',
        })
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    def test_calculate_commission_api_invalid_rule(self, client_with_session, commissions_config):
        """Test API with invalid rule ID."""
        response = client_with_session.post('/modules/commissions/api/calculate/', {
            'amount': '500.00',
            'rule_id': 99999,
        })
        assert response.status_code == 404
        data = response.json()
        assert 'error' in data

    def test_staff_summary_api(self, client_with_session, commission_transaction, commissions_config):
        """Test staff summary API."""
        response = client_with_session.get('/modules/commissions/api/staff/1/summary/')
        assert response.status_code == 200
        data = response.json()
        assert 'total_commission' in data
        assert 'pending_count' in data

    def test_staff_summary_api_with_dates(self, client_with_session, commission_transaction, commissions_config):
        """Test staff summary API with date range."""
        today = date.today().isoformat()
        response = client_with_session.get(
            f'/modules/commissions/api/staff/1/summary/?start_date={today}&end_date={today}'
        )
        assert response.status_code == 200
        data = response.json()
        assert 'total_commission' in data
