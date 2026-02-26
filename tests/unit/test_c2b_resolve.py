"""
Tests for admin resolution of unmatched C2B transactions.
Tests that staff users can assign a category to unmatched transactions,
creating the contribution and sending a receipt.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User

from contributions.models import Contribution
from mpesa.models import C2BTransaction
from members.roles import UserRole
from api_schema.c2b_mutations import C2BMutations

from tests.utils.factories import (
    ContributionCategoryFactory,
    MemberFactory,
    C2BTransactionFactory,
    UserFactory,
)


def _make_staff_info(user):
    """Create a mock GraphQL info object with an authenticated staff user."""
    info = MagicMock()
    info.context.request.user = user
    return info


def _make_anon_info():
    """Create a mock GraphQL info object with an anonymous user."""
    info = MagicMock()
    info.context.request.user = MagicMock(is_authenticated=False)
    return info


@pytest.mark.django_db
class TestResolveUnmatchedC2B:
    """Tests for the resolve_unmatched_c2b mutation."""

    @patch('api_schema.c2b_mutations.ReceiptService')
    def test_resolve_unmatched_creates_contribution(self, mock_receipt_cls):
        """Resolving an unmatched transaction should create a contribution."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}

        # Setup
        member = MemberFactory(phone_number='254708374149')
        category = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        c2b_tx = C2BTransactionFactory(
            trans_id='RESOLVE001',
            msisdn='254708374149',
            trans_amount=Decimal('1000.00'),
            bill_ref_number='TITH',
            status='unmatched',
        )
        user = UserFactory(username='treasurer1')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id=str(c2b_tx.id),
            category_id=str(category.id),
        )

        assert result.success is True

        # Verify contribution was created
        contribution = Contribution.objects.get(member=member)
        assert contribution.amount == Decimal('1000.00')
        assert contribution.status == 'completed'
        assert contribution.category == category
        assert contribution.entry_type == 'mpesa'
        assert 'manually resolved' in contribution.notes

        # Verify transaction was updated
        c2b_tx.refresh_from_db()
        assert c2b_tx.status == 'processed'
        assert c2b_tx.match_method == 'manual'
        assert c2b_tx.matched_category_code == 'TITHE'

    @patch('api_schema.c2b_mutations.ReceiptService')
    def test_resolve_sends_receipt(self, mock_receipt_cls):
        """Resolving should send an SMS receipt."""
        mock_receipt_instance = mock_receipt_cls.return_value
        mock_receipt_instance.send_receipt.return_value = {'success': True}

        member = MemberFactory(phone_number='254708374149', first_name='John', last_name='Doe')
        category = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        c2b_tx = C2BTransactionFactory(
            trans_id='RESOLVE002',
            msisdn='254708374149',
            trans_amount=Decimal('500.00'),
            bill_ref_number='TITH',
            status='unmatched',
        )
        user = UserFactory(username='treasurer2')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id=str(c2b_tx.id),
            category_id=str(category.id),
        )

        mock_receipt_instance.send_receipt.assert_called_once()
        call_kwargs = mock_receipt_instance.send_receipt.call_args[1]
        assert call_kwargs['phone_number'] == '254708374149'
        assert call_kwargs['category_name'] == 'Tithe'
        assert call_kwargs['amount'] == Decimal('500.00')

    def test_resolve_requires_authentication(self):
        """Unauthenticated user should be rejected."""
        info = _make_anon_info()
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id='1',
            category_id='1',
        )

        assert result.success is False
        assert 'Authentication required' in result.message

    def test_resolve_requires_staff_role(self):
        """Non-staff user should be rejected."""
        user = UserFactory(username='regular_user')
        # No staff role assigned
        info = _make_staff_info(user)

        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id='1',
            category_id='1',
        )

        assert result.success is False
        assert 'staff privileges' in result.message

    def test_resolve_rejects_non_unmatched_transaction(self):
        """Cannot resolve a transaction that is not unmatched."""
        member = MemberFactory(phone_number='254708374149')
        category = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        c2b_tx = C2BTransactionFactory(
            trans_id='RESOLVE003',
            msisdn='254708374149',
            status='processed',  # Already processed
        )
        user = UserFactory(username='treasurer3')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id=str(c2b_tx.id),
            category_id=str(category.id),
        )

        assert result.success is False
        assert 'not unmatched' in result.message

    def test_resolve_rejects_invalid_transaction_id(self):
        """Should fail gracefully for non-existent transaction ID."""
        user = UserFactory(username='treasurer4')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id='99999',
            category_id='1',
        )

        assert result.success is False
        assert 'not found' in result.message

    def test_resolve_rejects_invalid_category_id(self):
        """Should fail gracefully for non-existent category ID."""
        member = MemberFactory(phone_number='254708374149')
        c2b_tx = C2BTransactionFactory(
            trans_id='RESOLVE004',
            msisdn='254708374149',
            status='unmatched',
        )
        user = UserFactory(username='treasurer5')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id=str(c2b_tx.id),
            category_id='99999',
        )

        assert result.success is False
        assert 'not found' in result.message

    @patch('api_schema.c2b_mutations.ReceiptService')
    def test_resolve_receipt_failure_does_not_fail_resolution(self, mock_receipt_cls):
        """Receipt failure should not prevent the resolution."""
        mock_receipt_cls.return_value.send_receipt.side_effect = Exception('SMS down')

        member = MemberFactory(phone_number='254708374149')
        category = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        c2b_tx = C2BTransactionFactory(
            trans_id='RESOLVE005',
            msisdn='254708374149',
            trans_amount=Decimal('500.00'),
            status='unmatched',
        )
        user = UserFactory(username='treasurer6')
        UserRole.objects.create(user=user, role='treasurer', is_active=True)

        info = _make_staff_info(user)
        result = C2BMutations.resolve_unmatched_c2b(
            info,
            transaction_id=str(c2b_tx.id),
            category_id=str(category.id),
        )

        # Should still succeed
        assert result.success is True

        # Contribution and transaction should be updated
        assert Contribution.objects.count() == 1
        c2b_tx.refresh_from_db()
        assert c2b_tx.status == 'processed'
