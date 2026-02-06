"""
Mock helpers for external API responses.
"""

from decimal import Decimal
from typing import Dict, Any


class MockMpesaResponses:
    """Mock responses for M-Pesa API."""

    @staticmethod
    def auth_success() -> Dict[str, Any]:
        """Successful authentication response."""
        return {
            'access_token': 'test_access_token_12345',
            'expires_in': '3599'
        }

    @staticmethod
    def auth_failure() -> Dict[str, Any]:
        """Failed authentication response."""
        return {
            'errorCode': '400.002.02',
            'errorMessage': 'Bad Request - Invalid Credentials'
        }

    @staticmethod
    def stk_push_success(phone_number: str = '254712345678', amount: Decimal = Decimal('1000.00')) -> Dict[str, Any]:
        """Successful STK push response."""
        return {
            'MerchantRequestID': 'test_merchant_req_123',
            'CheckoutRequestID': 'test_checkout_req_456',
            'ResponseCode': '0',
            'ResponseDescription': 'Success. Request accepted for processing',
            'CustomerMessage': 'Success. Request accepted for processing'
        }

    @staticmethod
    def stk_push_failure() -> Dict[str, Any]:
        """Failed STK push response."""
        return {
            'requestId': 'test_req_789',
            'errorCode': '500.001.1001',
            'errorMessage': 'The balance is insufficient for the transaction'
        }

    @staticmethod
    def callback_success(
        merchant_request_id: str = 'test_merchant_123',
        checkout_request_id: str = 'test_checkout_456',
        amount: Decimal = Decimal('1000.00'),
        phone_number: str = '254712345678',
        receipt_number: str = 'ABC123XYZ'
    ) -> Dict[str, Any]:
        """Successful payment callback."""
        return {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': merchant_request_id,
                    'CheckoutRequestID': checkout_request_id,
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': float(amount)},
                            {'Name': 'MpesaReceiptNumber', 'Value': receipt_number},
                            {'Name': 'Balance'},
                            {'Name': 'TransactionDate', 'Value': 20260206140530},
                            {'Name': 'PhoneNumber', 'Value': int(phone_number)}
                        ]
                    }
                }
            }
        }

    @staticmethod
    def callback_failure(
        merchant_request_id: str = 'test_merchant_123',
        checkout_request_id: str = 'test_checkout_456'
    ) -> Dict[str, Any]:
        """Failed payment callback (user cancelled or insufficient funds)."""
        return {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': merchant_request_id,
                    'CheckoutRequestID': checkout_request_id,
                    'ResultCode': 1032,
                    'ResultDesc': 'Request cancelled by user'
                }
            }
        }


class MockSMSResponses:
    """Mock responses for Mobitech SMS API."""

    @staticmethod
    def send_success(message_id: str = 'test_msg_123') -> Dict[str, Any]:
        """Successful SMS send response matching Mobitech API format."""
        return {
            'status_code': '1000',  # Mobitech success code
            'status_desc': 'Success',
            'message_id': message_id,
            'message_cost': 0.35,
            'credit_balance': 100.00
        }

    @staticmethod
    def send_failure() -> Dict[str, Any]:
        """Failed SMS send response."""
        return {
            'status_code': '1002',
            'status_desc': 'Invalid phone number',
            'message_id': None
        }

    @staticmethod
    def insufficient_balance() -> Dict[str, Any]:
        """Insufficient balance response."""
        return {
            'status_code': '1003',
            'status_desc': 'Insufficient SMS balance',
            'message_id': None
        }


def setup_mpesa_mocks(rsps, scenario: str = 'success'):
    """
    Setup M-Pesa API mocks for different scenarios.

    Args:
        rsps: responses.RequestsMock instance
        scenario: 'success', 'auth_failure', 'stk_failure'
    """
    if scenario == 'success':
        # Mock auth
        rsps.add(
            'GET',
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json=MockMpesaResponses.auth_success(),
            status=200
        )
        # Mock STK push
        rsps.add(
            'POST',
            'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            json=MockMpesaResponses.stk_push_success(),
            status=200
        )

    elif scenario == 'auth_failure':
        rsps.add(
            'GET',
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json=MockMpesaResponses.auth_failure(),
            status=401
        )

    elif scenario == 'stk_failure':
        # Auth succeeds
        rsps.add(
            'GET',
            'https://safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json=MockMpesaResponses.auth_success(),
            status=200
        )
        # STK push fails
        rsps.add(
            'POST',
            'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            json=MockMpesaResponses.stk_push_failure(),
            status=500
        )


def setup_sms_mocks(rsps, scenario: str = 'success'):
    """
    Setup SMS API mocks for different scenarios.

    Args:
        rsps: responses.RequestsMock instance
        scenario: 'success', 'failure', 'insufficient_balance'
    """
    if scenario == 'success':
        rsps.add(
            'POST',
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json=MockSMSResponses.send_success(),
            status=200
        )
    elif scenario == 'failure':
        rsps.add(
            'POST',
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json=MockSMSResponses.send_failure(),
            status=400
        )
    elif scenario == 'insufficient_balance':
        rsps.add(
            'POST',
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json=MockSMSResponses.insufficient_balance(),
            status=402
        )
