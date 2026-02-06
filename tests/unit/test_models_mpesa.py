"""
Unit tests for M-Pesa models (MpesaTransaction and MpesaCallback).
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from mpesa.models import MpesaTransaction, MpesaCallback
from tests.utils.factories import MpesaTransactionFactory, MpesaCallbackFactory


@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaTransactionModel:
    """Test cases for MpesaTransaction model."""

    def test_create_transaction_with_valid_data(self, db):
        """Test creating an M-Pesa transaction with valid data."""
        transaction = MpesaTransactionFactory(
            merchant_request_id='merchant_123',
            checkout_request_id='checkout_456',
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            account_reference='TITHE',
            status='pending'
        )

        assert transaction.id is not None
        assert transaction.merchant_request_id == 'merchant_123'
        assert transaction.checkout_request_id == 'checkout_456'
        assert transaction.phone_number == '254712345678'
        assert transaction.amount == Decimal('1000.00')
        assert transaction.account_reference == 'TITHE'
        assert transaction.status == 'pending'

    def test_transaction_str_representation(self, db):
        """Test __str__ method returns correct format."""
        transaction = MpesaTransactionFactory(
            phone_number='254712345678',
            amount=Decimal('5000.00'),
            status='completed'
        )

        assert str(transaction) == '254712345678 - KES 5000.00 - completed'

    def test_merchant_request_id_must_be_unique(self, db):
        """Test that merchant_request_id must be unique."""
        MpesaTransactionFactory(merchant_request_id='merchant_123')

        with pytest.raises(IntegrityError):
            MpesaTransactionFactory(merchant_request_id='merchant_123')

    def test_checkout_request_id_must_be_unique(self, db):
        """Test that checkout_request_id must be unique."""
        MpesaTransactionFactory(checkout_request_id='checkout_456')

        with pytest.raises(IntegrityError):
            MpesaTransactionFactory(checkout_request_id='checkout_456')

    def test_transaction_status_choices(self, db):
        """Test different transaction statuses."""
        statuses = ['pending', 'completed', 'failed', 'cancelled']

        for status in statuses:
            transaction = MpesaTransactionFactory(status=status)
            assert transaction.status == status

    def test_is_successful_property_for_completed(self, db):
        """Test is_successful property for completed transaction."""
        transaction = MpesaTransactionFactory(
            status='completed',
            result_code='0'
        )

        assert transaction.is_successful is True

    def test_is_successful_property_for_failed(self, db):
        """Test is_successful property for failed transaction."""
        transaction = MpesaTransactionFactory(
            status='failed',
            result_code='1032'
        )

        assert transaction.is_successful is False

    def test_is_successful_property_for_pending(self, db):
        """Test is_successful property for pending transaction."""
        transaction = MpesaTransactionFactory(
            status='pending',
            result_code=None
        )

        assert transaction.is_successful is False

    def test_phone_number_validation_format(self, db):
        """Test phone number must be in correct format."""
        transaction = MpesaTransactionFactory(phone_number='254712345678')
        transaction.full_clean()  # Should not raise

        # Invalid format
        invalid_transaction = MpesaTransaction(
            merchant_request_id='test_merchant',
            checkout_request_id='test_checkout',
            phone_number='0712345678',  # Invalid format
            amount=Decimal('1000.00'),
            account_reference='TITHE',
            transaction_desc='Test'
        )

        with pytest.raises(ValidationError):
            invalid_transaction.full_clean()

    def test_mpesa_receipt_number_must_be_unique(self, db):
        """Test that mpesa_receipt_number must be unique when set."""
        MpesaTransactionFactory(mpesa_receipt_number='ABC123XYZ')

        with pytest.raises(IntegrityError):
            MpesaTransactionFactory(mpesa_receipt_number='ABC123XYZ')

    def test_mpesa_receipt_number_can_be_null(self, db):
        """Test that mpesa_receipt_number can be null for pending transactions."""
        transaction = MpesaTransactionFactory(mpesa_receipt_number=None)

        assert transaction.mpesa_receipt_number is None

    def test_transaction_date_can_be_null(self, db):
        """Test that transaction_date can be null for pending transactions."""
        transaction = MpesaTransactionFactory(transaction_date=None)

        assert transaction.transaction_date is None

    def test_result_fields_for_completed_transaction(self, db):
        """Test result fields are set for completed transaction."""
        transaction = MpesaTransactionFactory(
            status='completed',
            result_code='0',
            result_desc='The service request is processed successfully.',
            mpesa_receipt_number='ABC123XYZ',
            transaction_date=timezone.now()
        )

        assert transaction.result_code == '0'
        assert transaction.result_desc == 'The service request is processed successfully.'
        assert transaction.mpesa_receipt_number == 'ABC123XYZ'
        assert transaction.transaction_date is not None

    def test_transaction_ordering(self, db):
        """Test transactions are ordered by created_at descending."""
        from datetime import timedelta

        old = MpesaTransactionFactory()
        old.created_at = timezone.now() - timedelta(hours=1)
        old.save()

        recent = MpesaTransactionFactory()

        transactions = list(MpesaTransaction.objects.all())

        assert transactions[0] == recent
        assert transactions[1] == old

    def test_transaction_callbacks_relationship(self, db):
        """Test reverse relationship to callbacks."""
        transaction = MpesaTransactionFactory()
        callback1 = MpesaCallbackFactory(transaction=transaction)
        callback2 = MpesaCallbackFactory(transaction=transaction)

        assert transaction.callbacks.count() == 2


@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaCallbackModel:
    """Test cases for MpesaCallback model."""

    def test_create_callback_with_valid_data(self, db):
        """Test creating an M-Pesa callback with valid data."""
        callback = MpesaCallbackFactory(
            merchant_request_id='merchant_123',
            checkout_request_id='checkout_456',
            result_code='0',
            result_desc='Success',
            raw_data={'test': 'data'}
        )

        assert callback.id is not None
        assert callback.merchant_request_id == 'merchant_123'
        assert callback.checkout_request_id == 'checkout_456'
        assert callback.result_code == '0'
        assert callback.result_desc == 'Success'
        assert callback.raw_data == {'test': 'data'}

    def test_callback_str_representation(self, db):
        """Test __str__ method returns correct format."""
        callback = MpesaCallbackFactory(
            checkout_request_id='checkout_456',
            result_code='0'
        )

        assert str(callback) == 'Callback - checkout_456 - 0'

    def test_callback_with_linked_transaction(self, db):
        """Test callback linked to transaction."""
        transaction = MpesaTransactionFactory()
        callback = MpesaCallbackFactory(transaction=transaction)

        assert callback.transaction == transaction
        assert callback in transaction.callbacks.all()

    def test_callback_without_transaction(self, db):
        """Test callback can exist without linked transaction."""
        callback = MpesaCallbackFactory(transaction=None)

        assert callback.transaction is None

    def test_callback_raw_data_json_field(self, db):
        """Test raw_data stores complex JSON data."""
        complex_data = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'test_merchant',
                    'CheckoutRequestID': 'test_checkout',
                    'ResultCode': 0,
                    'ResultDesc': 'Success',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 1000.00},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123XYZ'}
                        ]
                    }
                }
            }
        }

        callback = MpesaCallbackFactory(raw_data=complex_data)

        assert callback.raw_data == complex_data
        assert callback.raw_data['Body']['stkCallback']['ResultCode'] == 0

    def test_callback_ordering(self, db):
        """Test callbacks are ordered by created_at descending."""
        from datetime import timedelta

        old = MpesaCallbackFactory()
        old.created_at = timezone.now() - timedelta(hours=1)
        old.save()

        recent = MpesaCallbackFactory()

        callbacks = list(MpesaCallback.objects.all())

        assert callbacks[0] == recent
        assert callbacks[1] == old

    def test_multiple_callbacks_same_transaction(self, db):
        """Test multiple callbacks can reference same transaction."""
        transaction = MpesaTransactionFactory()

        callback1 = MpesaCallbackFactory(
            transaction=transaction,
            result_code='0'
        )
        callback2 = MpesaCallbackFactory(
            transaction=transaction,
            result_code='1032'
        )

        assert callback1.transaction == callback2.transaction
        assert transaction.callbacks.count() == 2
