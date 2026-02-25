"""
Tests for C2B confirmation endpoint and full processing flow.
Tests the complete flow: callback -> member match -> contribution creation -> receipt.
"""

import json
import pytest
from decimal import Decimal
from unittest.mock import patch

from django.test import Client

from contributions.models import Contribution
from members.models import Member
from mpesa.c2b_service import C2BContributionService
from mpesa.models import C2BTransaction, C2BCallback
from tests.utils.factories import (
    ContributionCategoryFactory,
    MemberFactory,
    C2BTransactionFactory,
)


def _make_confirmation_payload(
    trans_id='RKTQDM7W6S',
    amount='500.00',
    bill_ref='TITHE',
    msisdn='254708374149',
    first_name='John',
    last_name='Doe',
    trans_time='20240115143022'
):
    return {
        'TransactionType': 'Pay Bill',
        'TransID': trans_id,
        'TransTime': trans_time,
        'TransAmount': amount,
        'BusinessShortCode': '174379',
        'BillRefNumber': bill_ref,
        'MSISDN': msisdn,
        'FirstName': first_name,
        'MiddleName': '',
        'LastName': last_name,
        'OrgAccountBalance': '50000.00'
    }


@pytest.mark.django_db
class TestC2BConfirmation:
    """Tests for C2B payment confirmation processing."""

    @patch('mpesa.c2b_service.ReceiptService')
    def test_full_flow_existing_member(self, mock_receipt_cls):
        """Full flow: known member + valid category -> contribution created."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        member = MemberFactory(phone_number='254708374149', first_name='John', last_name='Doe')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(msisdn='254708374149')
        result = service.process_c2b_confirmation(payload)

        assert result['success'] is True

        # Verify C2BTransaction was created
        c2b_tx = C2BTransaction.objects.get(trans_id='RKTQDM7W6S')
        assert c2b_tx.trans_amount == Decimal('500.00')
        assert c2b_tx.msisdn == '254708374149'
        assert c2b_tx.status == 'processed'

        # Verify Contribution was created
        contribution = Contribution.objects.get(member=member)
        assert contribution.amount == Decimal('500.00')
        assert contribution.status == 'completed'
        assert contribution.entry_type == 'mpesa'
        assert contribution.category.code == 'TITHE'

    @patch('mpesa.c2b_service.ReceiptService')
    def test_guest_member_created_with_mpesa_names(self, mock_receipt_cls):
        """Unknown phone should create a guest member with M-Pesa provided names."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        ContributionCategoryFactory(name='Offering', code='OFFER', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(
            trans_id='GUEST001',
            msisdn='254799999999',
            first_name='Jane',
            last_name='Wanjiku',
            bill_ref='OFFER'
        )
        result = service.process_c2b_confirmation(payload)

        assert result['success'] is True

        # Verify guest member was created with M-Pesa names
        member = Member.objects.get(phone_number='254799999999')
        assert member.first_name == 'Jane'
        assert member.last_name == 'Wanjiku'
        assert member.is_guest is True
        assert member.is_active is True

        # Verify contribution was linked to guest member
        contribution = Contribution.objects.get(member=member)
        assert contribution.amount == Decimal('500.00')

    @patch('mpesa.c2b_service.ReceiptService')
    def test_idempotency_duplicate_trans_id(self, mock_receipt_cls):
        """Duplicate TransID should be ignored (idempotency)."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='DUP001')

        # First call should succeed
        result1 = service.process_c2b_confirmation(payload)
        assert result1['success'] is True

        # Second call with same TransID should be ignored
        result2 = service.process_c2b_confirmation(payload)
        assert result2['success'] is True
        assert 'already processed' in result2['message']

        # Only one C2BTransaction should exist
        assert C2BTransaction.objects.filter(trans_id='DUP001').count() == 1

        # Only one Contribution should exist
        assert Contribution.objects.count() == 1

    @patch('mpesa.c2b_service.ReceiptService')
    def test_unknown_category_fails_gracefully(self, mock_receipt_cls):
        """Payment with unknown BillRefNumber should fail but still record transaction."""
        MemberFactory(phone_number='254708374149')

        service = C2BContributionService()
        payload = _make_confirmation_payload(bill_ref='NOSUCHCAT', trans_id='NOCAT001')
        result = service.process_c2b_confirmation(payload)

        assert result['success'] is False
        assert 'Category not found' in result['message']

        # Transaction should still be recorded (but with failed status)
        c2b_tx = C2BTransaction.objects.get(trans_id='NOCAT001')
        assert c2b_tx.status == 'failed'

        # No contribution should be created
        assert Contribution.objects.count() == 0

    @patch('mpesa.c2b_service.ReceiptService')
    def test_receipt_sent_after_confirmation(self, mock_receipt_cls):
        """SMS receipt should be sent after successful confirmation."""
        mock_receipt_instance = mock_receipt_cls.return_value
        mock_receipt_instance.send_receipt.return_value = {'success': True}
        MemberFactory(phone_number='254708374149', first_name='John', last_name='Doe')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='RCPT001')
        service.process_c2b_confirmation(payload)

        # Verify receipt was sent
        mock_receipt_instance.send_receipt.assert_called_once()
        call_kwargs = mock_receipt_instance.send_receipt.call_args
        assert call_kwargs[1]['phone_number'] == '254708374149'
        assert call_kwargs[1]['member_name'] == 'John Doe'
        assert call_kwargs[1]['category_name'] == 'Tithe'
        assert call_kwargs[1]['amount'] == Decimal('500.00')
        assert call_kwargs[1]['mpesa_receipt'] == 'RCPT001'

    @patch('mpesa.c2b_service.ReceiptService')
    def test_confirmation_creates_audit_records(self, mock_receipt_cls):
        """Confirmation should create both C2BCallback and C2BTransaction records."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='AUDIT002')
        service.process_c2b_confirmation(payload)

        # C2BCallback audit record should exist
        callback = C2BCallback.objects.filter(trans_id='AUDIT002', callback_type='confirmation').first()
        assert callback is not None
        assert callback.processed is True
        assert callback.transaction is not None

    def test_confirmation_endpoint_returns_success(self):
        """POST to confirmation endpoint should always return ResultCode 0."""
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        client = Client()
        payload = _make_confirmation_payload(trans_id='EP001')

        with patch('mpesa.c2b_service.ReceiptService') as mock_cls:
            mock_cls.return_value.send_receipt.return_value = {'success': True}
            response = client.post(
                '/api/mpesa/c2b/confirmation/',
                data=json.dumps(payload),
                content_type='application/json'
            )

        assert response.status_code == 200
        data = response.json()
        assert data['ResultCode'] == 0

    def test_confirmation_endpoint_invalid_json(self):
        """POST with invalid JSON should return 400."""
        client = Client()

        response = client.post(
            '/api/mpesa/c2b/confirmation/',
            data='not json',
            content_type='application/json'
        )

        assert response.status_code == 400

    @patch('mpesa.c2b_service.ReceiptService')
    def test_case_insensitive_category_match(self, mock_receipt_cls):
        """BillRefNumber should match category code case-insensitively."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Building Fund', code='BUILD', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='CASE001', bill_ref='build')
        result = service.process_c2b_confirmation(payload)

        assert result['success'] is True
        contribution = Contribution.objects.first()
        assert contribution.category.code == 'BUILD'

    @patch('mpesa.c2b_service.ReceiptService')
    def test_org_account_balance_stored(self, mock_receipt_cls):
        """OrgAccountBalance from callback should be stored."""
        mock_receipt_cls.return_value.send_receipt.return_value = {'success': True}
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='BAL001')
        service.process_c2b_confirmation(payload)

        c2b_tx = C2BTransaction.objects.get(trans_id='BAL001')
        assert c2b_tx.org_account_balance == Decimal('50000.00')

    @patch('mpesa.c2b_service.ReceiptService')
    def test_receipt_failure_does_not_fail_processing(self, mock_receipt_cls):
        """If SMS receipt fails, the transaction should still be recorded."""
        mock_receipt_cls.return_value.send_receipt.side_effect = Exception('SMS API down')
        MemberFactory(phone_number='254708374149')
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)

        service = C2BContributionService()
        payload = _make_confirmation_payload(trans_id='SMSFAIL001')
        result = service.process_c2b_confirmation(payload)

        # Processing should still succeed
        assert result['success'] is True

        # Transaction and contribution should exist
        assert C2BTransaction.objects.filter(trans_id='SMSFAIL001').exists()
        assert Contribution.objects.count() == 1
