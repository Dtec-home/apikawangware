"""
Unit tests for M-Pesa services.
Tests MpesaAuthService, MpesaSTKService, and MpesaCallbackHandler.
"""

import pytest
import responses
from decimal import Decimal
from django.utils import timezone
from mpesa.services import MpesaAuthService, MpesaSTKService, MpesaCallbackHandler
from mpesa.models import MpesaTransaction, MpesaCallback
from tests.utils.factories import MpesaTransactionFactory, MemberFactory, ContributionCategoryFactory
from tests.utils.mocks import MockMpesaResponses, setup_mpesa_mocks


@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaAuthService:
    """Test cases for MpesaAuthService."""

    @responses.activate
    def test_get_access_token_success(self):
        """Test successful access token retrieval."""
        # Setup mock
        responses.add(
            responses.GET,
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json=MockMpesaResponses.auth_success(),
            status=200
        )

        service = MpesaAuthService()
        token = service.get_access_token()

        assert token == 'test_access_token_12345'

    @responses.activate
    def test_get_access_token_failure(self):
        """Test failed access token retrieval."""
        # Setup mock for failure
        responses.add(
            responses.GET,
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json=MockMpesaResponses.auth_failure(),
            status=401
        )

        service = MpesaAuthService()
        token = service.get_access_token()

        assert token is None


@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaSTKService:
    """Test cases for MpesaSTKService."""

    @responses.activate
    def test_initiate_stk_push_success(self, db):
        """Test successful STK push initiation."""
        # Setup mocks
        setup_mpesa_mocks(responses, scenario='success')

        service = MpesaSTKService()
        result = service.initiate_stk_push(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            account_reference='TITHE',
            transaction_desc='Test contribution'
        )

        assert result['success'] is True
        assert 'transaction' in result
        assert result['transaction'].phone_number == '254712345678'
        assert result['transaction'].amount == Decimal('1000.00')
        assert result['transaction'].status == 'pending'
        assert result['checkout_request_id'] == 'test_checkout_req_456'

    @responses.activate
    def test_initiate_stk_push_auth_failure(self, db):
        """Test STK push when authentication fails."""
        # Setup mock for auth failure
        setup_mpesa_mocks(responses, scenario='auth_failure')

        service = MpesaSTKService()
        result = service.initiate_stk_push(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            account_reference='TITHE',
            transaction_desc='Test contribution'
        )

        assert result['success'] is False
        assert 'message' in result

    @responses.activate
    def test_initiate_stk_push_api_failure(self, db):
        """Test STK push when API call fails."""
        # Setup mock for STK failure
        setup_mpesa_mocks(responses, scenario='stk_failure')

        service = MpesaSTKService()
        result = service.initiate_stk_push(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            account_reference='TITHE',
            transaction_desc='Test contribution'
        )

        assert result['success'] is False

    def test_password_generation(self):
        """Test M-Pesa password generation."""
        service = MpesaSTKService()
        timestamp = '20260206140530'

        password = service._generate_password(timestamp)

        assert password is not None
        assert isinstance(password, str)
        assert len(password) > 0


@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaCallbackHandler:
    """Test cases for MpesaCallbackHandler."""

    @responses.activate
    def test_process_successful_callback(self, db):
        """Test processing a successful payment callback."""
        # Create pending transaction
        transaction = MpesaTransactionFactory(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456',
            status='pending',
            phone_number='254712345678',
            amount=Decimal('1000.00')
        )

        # Create member and category for contribution
        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory(code='TITHE')

        # Mock SMS API
        responses.add(
            responses.POST,
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json={'success': True, 'messageId': 'test_msg_123'},
            status=200
        )

        # Create callback data
        callback_data = MockMpesaResponses.callback_success(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456',
            amount=Decimal('1000.00'),
            phone_number='254712345678',
            receipt_number='ABC123XYZ'
        )

        handler = MpesaCallbackHandler()
        result = handler.process_callback(callback_data)

        assert result['success'] is True

        # Verify transaction was updated
        transaction.refresh_from_db()
        assert transaction.status == 'completed'
        assert transaction.mpesa_receipt_number == 'ABC123XYZ'
        assert transaction.result_code == '0'

        # Verify callback was saved
        assert MpesaCallback.objects.filter(
            checkout_request_id='test_checkout_456'
        ).exists()

    @responses.activate
    def test_process_failed_callback(self, db):
        """Test processing a failed payment callback."""
        # Create pending transaction
        transaction = MpesaTransactionFactory(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456',
            status='pending'
        )

        # Create callback data for failure
        callback_data = MockMpesaResponses.callback_failure(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456'
        )

        handler = MpesaCallbackHandler()
        result = handler.process_callback(callback_data)

        # Payment failed — process_callback returns success:False to signal
        # the payment was not completed (distinct from a processing error).
        assert result['success'] is False

        # Verify transaction was updated to failed
        transaction.refresh_from_db()
        assert transaction.status == 'failed'
        assert transaction.result_code == '1032'

    def test_process_callback_transaction_not_found(self, db):
        """Test processing callback when transaction doesn't exist."""
        callback_data = MockMpesaResponses.callback_success(
            merchant_request_id='nonexistent_merchant',
            checkout_request_id='nonexistent_checkout'
        )

        handler = MpesaCallbackHandler()
        result = handler.process_callback(callback_data)

        # No transaction found → process_callback returns success:False
        assert result['success'] is False
        # Callback is still persisted for audit even without a matched transaction
        assert MpesaCallback.objects.filter(
            checkout_request_id='nonexistent_checkout'
        ).exists()

    @responses.activate
    def test_contribution_status_updated_on_success(self, db):
        """Test that contributions are marked completed when payment succeeds."""
        from contributions.models import Contribution

        # Create transaction with linked contribution
        transaction = MpesaTransactionFactory(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456',
            status='pending'
        )

        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory()

        contribution = Contribution.objects.create(
            member=member,
            category=category,
            mpesa_transaction=transaction,
            amount=Decimal('1000.00'),
            status='pending',
            transaction_date=timezone.now()
        )

        # Mock SMS
        responses.add(
            responses.POST,
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json={'success': True},
            status=200
        )

        # Process successful callback
        callback_data = MockMpesaResponses.callback_success(
            merchant_request_id='test_merchant_123',
            checkout_request_id='test_checkout_456'
        )

        handler = MpesaCallbackHandler()
        handler.process_callback(callback_data)

        # Verify contribution was marked completed
        contribution.refresh_from_db()
        assert contribution.status == 'completed'
