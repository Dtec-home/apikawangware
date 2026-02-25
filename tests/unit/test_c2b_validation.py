"""
Tests for C2B validation endpoint and logic.
Tests that the validation endpoint correctly accepts/rejects payments
based on BillRefNumber and amount.
"""

import json
import pytest
from django.test import Client

from mpesa.c2b_service import C2BContributionService
from mpesa.models import C2BCallback
from tests.utils.factories import ContributionCategoryFactory


@pytest.mark.django_db
class TestC2BValidation:
    """Tests for C2B payment validation."""

    def _make_validation_payload(self, bill_ref='TITHE', amount='500.00', trans_id='VAL001'):
        return {
            'TransactionType': 'Pay Bill',
            'TransID': trans_id,
            'TransTime': '20240101120000',
            'TransAmount': amount,
            'BusinessShortCode': '174379',
            'BillRefNumber': bill_ref,
            'MSISDN': '254708374149',
            'FirstName': 'John',
            'MiddleName': '',
            'LastName': 'Doe'
        }

    def test_valid_bill_ref_accepted(self):
        """Payment with a valid, active category code should be accepted."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        service = C2BContributionService()
        payload = self._make_validation_payload(bill_ref='TITHE', amount='500.00')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is True

    def test_unknown_bill_ref_rejected(self):
        """Payment with an unknown BillRefNumber should be rejected."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        service = C2BContributionService()
        payload = self._make_validation_payload(bill_ref='UNKNOWN')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is False
        assert 'Unknown account reference' in result['message']

    def test_inactive_category_rejected(self):
        """Payment to an inactive category should be rejected."""
        ContributionCategoryFactory(name='Old Fund', code='OLDFUND', is_active=False)
        service = C2BContributionService()
        payload = self._make_validation_payload(bill_ref='OLDFUND')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is False

    def test_case_insensitive_bill_ref(self):
        """BillRefNumber matching should be case-insensitive."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        service = C2BContributionService()
        payload = self._make_validation_payload(bill_ref='tithe')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is True

    def test_amount_below_minimum_rejected(self):
        """Payment below KES 1.00 should be rejected."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        service = C2BContributionService()
        payload = self._make_validation_payload(amount='0.50')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is False
        assert 'below minimum' in result['message']

    def test_empty_bill_ref_rejected(self):
        """Payment with empty BillRefNumber should be rejected."""
        service = C2BContributionService()
        payload = self._make_validation_payload(bill_ref='')

        result = service.validate_c2b_payment(payload)

        assert result['accept'] is False
        assert 'required' in result['message']

    def test_validation_creates_audit_record(self):
        """Each validation should create a C2BCallback audit record."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        service = C2BContributionService()
        payload = self._make_validation_payload(trans_id='AUDIT001')

        service.validate_c2b_payment(payload)

        callback = C2BCallback.objects.filter(trans_id='AUDIT001').first()
        assert callback is not None
        assert callback.callback_type == 'validation'
        assert callback.raw_data == payload

    def test_validation_endpoint_accept(self):
        """POST to validation endpoint should return ResultCode 0 for valid payment."""
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        client = Client()
        payload = self._make_validation_payload()

        response = client.post(
            '/api/mpesa/c2b/validation/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['ResultCode'] == 0

    def test_validation_endpoint_reject(self):
        """POST to validation endpoint should return ResultCode 1 for invalid payment."""
        client = Client()
        payload = self._make_validation_payload(bill_ref='INVALID')

        response = client.post(
            '/api/mpesa/c2b/validation/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['ResultCode'] == 1

    def test_validation_endpoint_invalid_json(self):
        """POST with invalid JSON should return 400."""
        client = Client()

        response = client.post(
            '/api/mpesa/c2b/validation/',
            data='not json',
            content_type='application/json'
        )

        assert response.status_code == 400
