"""
M-Pesa Integration Services
Following SOLID principles:
- SRP: Each service class has a single responsibility
- DIP: Services depend on abstractions (can be mocked for testing)
"""

import base64
import logging
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from decouple import config
from django.utils import timezone
from django.utils.timezone import make_aware

from .models import MpesaTransaction, MpesaCallback, C2BTransaction, C2BCallback

logger = logging.getLogger(__name__)


class MpesaAuthService:
    """
    Handles M-Pesa authentication.
    Following SRP: Only responsible for obtaining access tokens.
    """

    def __init__(self):
        self.consumer_key = config('MPESA_CONSUMER_KEY')
        self.consumer_secret = config('MPESA_CONSUMER_SECRET')
        self.use_sandbox = config('MPESA_USE_SANDBOX', default=True, cast=bool)

        if self.use_sandbox:
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'

    def get_access_token(self) -> Optional[str]:
        """
        Get M-Pesa access token for API authentication.

        Returns:
            str: Access token if successful, None otherwise
        """
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"

            print("\n🔐 MPESA AUTHENTICATION")
            print(f"   URL: {url}")
            print(f"   Consumer Key: {self.consumer_key[:10]}...")
            print(f"   Consumer Secret: {self.consumer_secret[:10]}...")

            # Create base64 encoded credentials
            credentials = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }

            response = requests.get(url, headers=headers, timeout=30)
            print(f"   Auth Response Status: {response.status_code}")
            print(f"   Auth Response Body: {response.text}")

            response.raise_for_status()

            data = response.json()
            return data.get('access_token')

        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting M-Pesa access token: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response Status: {e.response.status_code}")
                print(f"   Response Body: {e.response.text}")
            return None


class MpesaSTKService:
    """
    Handles STK Push (Lipa Na M-Pesa Online) requests.
    Following SRP: Only responsible for initiating STK Push.
    Following DIP: Depends on MpesaAuthService abstraction.
    """

    def __init__(self):
        self.auth_service = MpesaAuthService()
        self.business_short_code = config('MPESA_BUSINESS_SHORT_CODE')
        self.lipa_na_mpesa_short_code = config('MPESA_LIPA_NA_MPESA_SHORT_CODE')
        self.passkey = config('MPESA_LIPA_NA_MPESA_PASSKEY')
        self.callback_url = config('MPESA_CALLBACK_URL')
        self.use_sandbox = config('MPESA_USE_SANDBOX', default=True, cast=bool)

        if self.use_sandbox:
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'

    def _generate_password(self, timestamp: str) -> str:
        """Generate password for STK push"""
        data = f"{self.lipa_na_mpesa_short_code}{self.passkey}{timestamp}"
        return base64.b64encode(data.encode()).decode()

    def initiate_stk_push(
        self,
        phone_number: str,
        amount: Decimal,
        account_reference: str,
        transaction_desc: str
    ) -> Dict:
        """
        Initiate STK Push to customer's phone.

        Args:
            phone_number: Customer phone number (254XXXXXXXXX format)
            amount: Amount to charge
            account_reference: Category code or reference
            transaction_desc: Description of the transaction

        Returns:
            dict: Contains success status and transaction data or error message
        """
        try:
            # Get access token
            print("=" * 80)
            print("MPESA STK PUSH - INITIATING")
            print("=" * 80)

            access_token = self.auth_service.get_access_token()
            if not access_token:
                print("❌ FAILED: Could not get access token")
                return {
                    'success': False,
                    'message': 'Failed to authenticate with M-Pesa'
                }

            print(f"✅ Access token obtained: {access_token[:20]}...")

            # Generate timestamp and password
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self._generate_password(timestamp)

            print(f"📅 Timestamp: {timestamp}")
            print(f"🔐 Password generated (length: {len(password)})")

            # Prepare request
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'BusinessShortCode': self.lipa_na_mpesa_short_code,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),  # M-Pesa requires integer
                'PartyA': phone_number,
                'PartyB': self.lipa_na_mpesa_short_code,
                'PhoneNumber': phone_number,
                'CallBackURL': self.callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }

            print("\n📤 REQUEST PAYLOAD:")
            print(f"   URL: {url}")
            print(f"   BusinessShortCode: {payload['BusinessShortCode']}")
            print(f"   TransactionType: {payload['TransactionType']}")
            print(f"   Amount: {payload['Amount']}")
            print(f"   PhoneNumber: {payload['PhoneNumber']}")
            print(f"   PartyA: {payload['PartyA']}")
            print(f"   PartyB: {payload['PartyB']}")
            print(f"   AccountReference: {payload['AccountReference']}")
            print(f"   TransactionDesc: {payload['TransactionDesc']}")
            print(f"   CallBackURL: {payload['CallBackURL']}")
            print(f"   Password length: {len(payload['Password'])}")
            print(f"   Timestamp: {payload['Timestamp']}")

            print("\n📡 Sending request to M-Pesa...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            print(f"📥 Response Status Code: {response.status_code}")
            print(f"📥 Response Body: {response.text}")

            response.raise_for_status()

            data = response.json()

            # Check if request was successful
            if data.get('ResponseCode') == '0':
                # Create transaction record
                transaction = MpesaTransaction.objects.create(
                    merchant_request_id=data.get('MerchantRequestID'),
                    checkout_request_id=data.get('CheckoutRequestID'),
                    phone_number=phone_number,
                    amount=amount,
                    account_reference=account_reference,
                    transaction_desc=transaction_desc,
                    status='pending'
                )

                return {
                    'success': True,
                    'message': data.get('CustomerMessage', 'STK Push sent successfully'),
                    'transaction': transaction,
                    'checkout_request_id': data.get('CheckoutRequestID')
                }
            else:
                return {
                    'success': False,
                    'message': data.get('ResponseDescription', 'Failed to initiate payment')
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error initiating payment: {str(e)}'
            }


class MpesaCallbackHandler:
    """
    Processes M-Pesa payment callbacks.
    Following SRP: Only responsible for processing callback data.
    """

    def _send_contribution_receipt(self, transaction: MpesaTransaction):
        """
        Send receipt SMS to contributor after successful payment.
        Following SRP: Separated concern for receipt delivery.
        Handles both single and multi-category contributions.
        """
        try:
            # Import receipt service
            from contributions.receipt_service import ReceiptService

            # Get all contributions associated with this transaction
            contributions = transaction.contributions.all()

            if not contributions.exists():
                print("⚠️  No contributions found for this transaction")
                return

            # Get member from first contribution (all should have same member)
            member = contributions.first().member
            receipt_service = ReceiptService()

            # Check if this is a multi-category contribution
            if contributions.count() > 1:
                # Multi-category contribution - send consolidated receipt
                print(f"📧 Sending multi-category receipt for {contributions.count()} categories")

                # Build contributions list for receipt
                contrib_list = []
                total_amount = Decimal('0.00')

                for contrib in contributions:
                    contrib_list.append({
                        'category_name': contrib.category.name,
                        'amount': contrib.amount
                    })
                    total_amount += contrib.amount

                # Send consolidated receipt
                result = receipt_service.send_multi_category_receipt(
                    phone_number=member.phone_number,
                    member_name=member.full_name,
                    contributions=contrib_list,
                    total_amount=total_amount,
                    mpesa_receipt=transaction.mpesa_receipt_number,
                    transaction_date=transaction.transaction_date
                )

                if result.get('success'):
                    print(f"✅ Multi-category receipt sent to {member.full_name}")
                else:
                    print(f"⚠️  Failed to send multi-category receipt: {result.get('message')}")
            else:
                # Single contribution - send regular receipt
                contribution = contributions.first()

                result = receipt_service.send_receipt(
                    phone_number=member.phone_number,
                    member_name=member.full_name,
                    category_name=contribution.category.name,
                    amount=contribution.amount,
                    mpesa_receipt=transaction.mpesa_receipt_number,
                    transaction_date=transaction.transaction_date
                )

                if result.get('success'):
                    print(f"✅ Receipt sent to {member.full_name}")
                else:
                    print(f"⚠️  Failed to send receipt: {result.get('message')}")

        except Exception as e:
            # Log error but don't fail the callback processing
            print(f"⚠️  Error sending receipt: {str(e)}")
            import traceback
            traceback.print_exc()

    def _update_contribution_status(self, transaction: MpesaTransaction, status: str):
        """
        Update contribution status when M-Pesa transaction is updated.
        Following SRP: Separated concern for contribution updates.
        Raises on failure so the caller can log/handle accordingly.
        """
        # Update all contributions linked to this transaction
        contributions = transaction.contributions.all()
        if contributions.exists():
            update_fields = {'status': status}
            if status == 'completed' and transaction.transaction_date:
                update_fields['transaction_date'] = transaction.transaction_date
            updated_count = contributions.update(**update_fields)
            print(f"✅ Updated {updated_count} contribution(s) to '{status}'")
            logger.info(
                f"Updated {updated_count} contribution(s) to '{status}' "
                f"for transaction {transaction.checkout_request_id}"
            )
        else:
            msg = (
                f"No contributions found for transaction {transaction.checkout_request_id}. "
                f"Contributions may not have been linked correctly."
            )
            print(f"⚠️  {msg}")
            logger.warning(msg)

    def process_callback(self, callback_data: Dict) -> Dict:
        """
        Process M-Pesa callback data.

        Args:
            callback_data: Raw callback data from M-Pesa

        Returns:
            dict: Processing result
        """
        try:
            # Extract data from callback
            body = callback_data.get('Body', {}).get('stkCallback', {})

            merchant_request_id = body.get('MerchantRequestID')
            checkout_request_id = body.get('CheckoutRequestID')
            result_code = str(body.get('ResultCode'))
            result_desc = body.get('ResultDesc')

            # Store callback for audit
            callback = MpesaCallback.objects.create(
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id,
                result_code=result_code,
                result_desc=result_desc,
                raw_data=callback_data
            )

            # Find associated transaction
            try:
                transaction = MpesaTransaction.objects.get(
                    checkout_request_id=checkout_request_id
                )

                # Link callback to transaction
                callback.transaction = transaction
                callback.save()

                # Update transaction based on result
                if result_code == '0':
                    # Success - extract payment details
                    callback_metadata = body.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])

                    # Extract metadata
                    metadata = {}
                    for item in items:
                        name = item.get('Name')
                        value = item.get('Value')
                        metadata[name] = value

                    # Update transaction
                    transaction.status = 'completed'
                    transaction.result_code = result_code
                    transaction.result_desc = result_desc
                    transaction.mpesa_receipt_number = metadata.get('MpesaReceiptNumber')

                    # Parse transaction date if available
                    # Use make_aware() so Django's USE_TZ=True is respected
                    if 'TransactionDate' in metadata:
                        trans_date_str = str(metadata['TransactionDate'])
                        # Format: 20231115143022
                        naive_dt = datetime.strptime(trans_date_str, '%Y%m%d%H%M%S')
                        transaction.transaction_date = make_aware(naive_dt)

                    transaction.save()

                    # Update associated contributions
                    try:
                        self._update_contribution_status(transaction, 'completed')
                    except Exception as contrib_err:
                        logger.error(
                            f"Failed to update contribution status for transaction "
                            f"{transaction.checkout_request_id}: {contrib_err}",
                            exc_info=True
                        )

                    # Send receipt SMS to contributor
                    self._send_contribution_receipt(transaction)

                    return {
                        'success': True,
                        'message': 'Payment completed successfully',
                        'transaction': transaction
                    }
                else:
                    # Payment failed or cancelled
                    transaction.status = 'failed'
                    transaction.result_code = result_code
                    transaction.result_desc = result_desc
                    transaction.save()

                    # Update associated contributions
                    try:
                        self._update_contribution_status(transaction, 'failed')
                    except Exception as contrib_err:
                        logger.error(
                            f"Failed to update contribution status to 'failed' for transaction "
                            f"{transaction.checkout_request_id}: {contrib_err}",
                            exc_info=True
                        )

                    return {
                        'success': False,
                        'message': result_desc,
                        'transaction': transaction
                    }

            except MpesaTransaction.DoesNotExist:
                return {
                    'success': False,
                    'message': 'Transaction not found'
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing callback: {str(e)}'
            }


class MpesaC2BService:
    """
    Handles M-Pesa C2B (Customer to Business) API operations.
    Following SRP: Only responsible for C2B URL registration and simulation.
    """

    def __init__(self):
        self.auth_service = MpesaAuthService()
        self.short_code = config('MPESA_C2B_SHORT_CODE', default=config('MPESA_BUSINESS_SHORT_CODE', default='174379'))
        self.use_sandbox = config('MPESA_USE_SANDBOX', default=True, cast=bool)

        if self.use_sandbox:
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'

    def register_urls(self, validation_url: str, confirmation_url: str) -> Dict:
        """
        Register C2B validation and confirmation URLs with Safaricom.
        This is a one-time setup per environment.

        Args:
            validation_url: URL for payment validation callbacks
            confirmation_url: URL for payment confirmation callbacks

        Returns:
            dict: Contains success status and response data
        """
        try:
            access_token = self.auth_service.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to authenticate with M-Pesa'
                }

            url = f"{self.base_url}/mpesa/c2b/v2/registerurl"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'ShortCode': self.short_code,
                'ResponseType': 'Completed',
                'ConfirmationURL': confirmation_url,
                'ValidationURL': validation_url
            }

            logger.info(f"Registering C2B URLs - Validation: {validation_url}, Confirmation: {confirmation_url}")
            print(f"\n{'='*60}")
            print(f"C2B URL REGISTRATION")
            print(f"   ShortCode: {self.short_code}")
            print(f"   Validation URL: {validation_url}")
            print(f"   Confirmation URL: {confirmation_url}")
            print(f"{'='*60}")

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            print(f"   Response Status: {response.status_code}")
            print(f"   Response Body: {response.text}")

            response.raise_for_status()
            data = response.json()

            if data.get('ResponseCode') == '0' or data.get('ResponseDescription', '').lower().startswith('success'):
                logger.info(f"C2B URLs registered successfully")
                return {
                    'success': True,
                    'message': data.get('ResponseDescription', 'URLs registered successfully'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'message': data.get('ResponseDescription', 'Failed to register URLs'),
                    'data': data
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error registering C2B URLs: {str(e)}")
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }

    def simulate_c2b(self, phone_number: str, amount: Decimal, bill_ref_number: str) -> Dict:
        """
        Simulate a C2B payment in the Daraja sandbox.
        Only works in sandbox mode.

        Args:
            phone_number: Customer phone number (254XXXXXXXXX)
            amount: Payment amount
            bill_ref_number: Account reference (maps to category code)

        Returns:
            dict: Contains success status and response data
        """
        if not self.use_sandbox:
            return {
                'success': False,
                'message': 'C2B simulation is only available in sandbox mode'
            }

        try:
            access_token = self.auth_service.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to authenticate with M-Pesa'
                }

            url = f"{self.base_url}/mpesa/c2b/v2/simulate"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                'ShortCode': self.short_code,
                'CommandID': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'Msisdn': phone_number,
                'BillRefNumber': bill_ref_number
            }

            logger.info(f"Simulating C2B: {phone_number} -> KES {amount} -> {bill_ref_number}")
            print(f"\n{'='*60}")
            print(f"C2B SIMULATION")
            print(f"   ShortCode: {self.short_code}")
            print(f"   Phone: {phone_number}")
            print(f"   Amount: KES {amount}")
            print(f"   BillRefNumber: {bill_ref_number}")
            print(f"{'='*60}")

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            print(f"   Response Status: {response.status_code}")
            print(f"   Response Body: {response.text}")

            response.raise_for_status()
            data = response.json()

            if data.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'message': data.get('ResponseDescription', 'Simulation successful'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'message': data.get('ResponseDescription', 'Simulation failed'),
                    'data': data
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error simulating C2B: {str(e)}")
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }