"""
OTP (One-Time Password) Management with Mobitech SMS API
Following SOLID principles:
- SRP: Single responsibility for OTP generation and validation
- DIP: Depends on SMS service abstraction
"""

import random
import string
import requests
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
import logging



class OTP(models.Model):
    """
    OTP model for phone-based authentication.
    Following SRP: Only responsible for OTP storage and validation.
    """

    phone_number = models.CharField(
        max_length=12,
        db_index=True,
        help_text="Phone number this OTP was sent to"
    )
    code = models.CharField(
        max_length=6,
        help_text="6-digit OTP code"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this OTP has been used"
    )
    expires_at = models.DateTimeField(
        help_text="When this OTP expires"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Track attempts to prevent brute force
    verification_attempts = models.IntegerField(
        default=0,
        help_text="Number of failed verification attempts"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', '-created_at']),
            models.Index(fields=['code', 'is_verified']),
        ]
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'

    def __str__(self):
        return f"OTP for {self.phone_number} - {'Verified' if self.is_verified else 'Pending'}"

    def is_valid(self) -> bool:
        """Check if OTP is still valid (not expired and not used)"""
        return (
            not self.is_verified and
            self.expires_at > timezone.now() and
            self.verification_attempts < 3  # Max 3 attempts
        )

    def increment_attempts(self):
        """Increment verification attempts"""
        self.verification_attempts += 1
        self.save(update_fields=['verification_attempts'])


class SMSService:
    """
    SMS Service using Mobitech SMS API.
    Following SRP: Only responsible for sending SMS.
    Singleton Pattern: Ensures we only initialize the configuration once.
    """
    _instance = None

    def __new__(cls):
        """
        Singleton Pattern: Ensures we only initialize the configuration once.
        """
        if cls._instance is None:
            cls._instance = super(SMSService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Mobitech SMS API configuration"""
        self.logger = logging.getLogger(__name__)

        self.api_key = getattr(settings, 'MOBITECH_API_KEY', None)
        self.sender_name = getattr(settings, 'MOBITECH_SENDER_NAME', 'FULL_CIRCLE')
        self.service_id = getattr(settings, 'MOBITECH_SERVICE_ID', 0)
        self.api_url = getattr(settings, 'MOBITECH_API_URL', 'https://app.mobitechtechnologies.com//sms/sendsms')

        # Debug logging
        print(f"\n{'='*50}")
        print(f"🔧 Mobitech SMS Service Initialization")
        print(f"   API URL: {self.api_url}")
        print(f"   API Key: {'*' * 20}{self.api_key[-10:] if self.api_key else 'Not set'}")
        print(f"   Sender Name: {self.sender_name}")
        print(f"   Service ID: {self.service_id}")
        print(f"{'='*50}\n")

        if not self.api_key:
            self.logger.warning("Mobitech API key not configured.")
            print("⚠️  Warning: Mobitech API key not configured")

    def send_sms(self, phone_number: str, message: str) -> dict:
        """
        Send SMS using Mobitech SMS API.

        Args:
            phone_number: Phone number in format +254XXXXXXXXX, 254XXXXXXXXX, or 07XXXXXXXXX
            message: Message to send

        Returns:
            dict with 'success' and 'message'
        """
        # Development mode - just log and return success
        if settings.DEBUG and not self.api_key:
            print(f"\n{'='*50}")
            print(f"📱 [DEV MODE] SMS to {phone_number}:")
            print(f"   {message}")
            print(f"{'='*50}\n")
            self.logger.info(f"DEBUG mode: SMS to {phone_number}. Message: {message}")
            return {
                'success': True,
                'message': 'SMS sent (development mode)'
            }

        try:
            # Format phone number - Mobitech accepts multiple formats
            # Ensure it has country code
            if phone_number.startswith('0'):
                phone_number = f'+254{phone_number[1:]}'
            elif not phone_number.startswith('+'):
                if not phone_number.startswith('254'):
                    phone_number = f'+254{phone_number}'
                else:
                    phone_number = f'+{phone_number}'

            # Prepare request headers
            headers = {
                'h_api_key': self.api_key,
                'Content-Type': 'application/json'
            }

            # Prepare request payload
            payload = {
                'mobile': phone_number,
                'response_type': 'json',
                'sender_name': self.sender_name,
                'service_id': self.service_id,
                'message': message
            }

            print(f"\n{'='*50}")
            print(f"📤 Sending SMS via Mobitech")
            print(f"   To: {phone_number}")
            print(f"   From: {self.sender_name}")
            print(f"   Message: {message[:50]}..." if len(message) > 50 else f"   Message: {message}")
            print(f"{'='*50}\n")

            # Send request to Mobitech API
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            self.logger.info(f"Mobitech API Response Status: {response.status_code}")
            self.logger.info(f"Mobitech API Response: {response.text}")

            print(f"📥 Response Status: {response.status_code}")
            print(f"📥 Response Body: {response.text}")

            # Parse response
            response_data = response.json()

            # Mobitech API can return either a dict or a list
            # Handle both formats
            if isinstance(response_data, dict):
                result = response_data
            elif isinstance(response_data, list) and len(response_data) > 0:
                result = response_data[0]
            else:
                return {
                    'success': False,
                    'message': 'Unexpected response format from Mobitech API'
                }

            status_code = result.get('status_code')

            # Status code 1000 means success
            if status_code == '1000' or status_code == 1000:
                print(f"✅ SMS sent successfully!")
                print(f"   Message ID: {result.get('message_id')}")
                print(f"   Cost: KES {result.get('message_cost')}")
                print(f"   Balance: KES {result.get('credit_balance')}")

                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'message_id': result.get('message_id'),
                    'cost': result.get('message_cost'),
                    'balance': result.get('credit_balance')
                }
            else:
                error_msg = result.get('status_desc', 'Unknown error')
                self.logger.error(f"SMS failed: {error_msg}")
                print(f"❌ SMS failed: {error_msg}")

                return {
                    'success': False,
                    'message': f"SMS failed: {error_msg}",
                    'status_code': status_code
                }

        except requests.exceptions.RequestException as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(f"Network error sending SMS to {phone_number}: {e}\n{error_details}")
            print(f"❌ Network error sending SMS: {str(e)}")
            print(f"❌ Full error details:\n{error_details}")

            # For development - still show the message
            if settings.DEBUG:
                print(f"\n{'='*50}")
                print(f"📱 [DEV MODE] SMS to {phone_number}:")
                print(f"   {message}")
                print(f"{'='*50}\n")

            return {
                'success': False,
                'message': f'Network error sending SMS: {str(e)}'
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(f"Error sending SMS to {phone_number}: {e}\n{error_details}")
            print(f"❌ Error sending SMS: {str(e)}")
            print(f"❌ Full error details:\n{error_details}")

            # For development - still show the message
            if settings.DEBUG:
                print(f"\n{'='*50}")
                print(f"📱 [DEV MODE] SMS to {phone_number}:")
                print(f"   {message}")
                print(f"{'='*50}\n")

            return {
                'success': False,
                'message': f'Error sending SMS: {str(e)}'
            }


class OTPService:
    """
    Service for managing OTP generation and verification.
    Following SRP: Single responsibility for OTP business logic.
    Following DIP: Depends on SMSService abstraction.
    """

    OTP_LENGTH = 6
    OTP_VALIDITY_MINUTES = 10  # OTP valid for 10 minutes
    MAX_OTP_PER_HOUR = 5  # Prevent spam

    def __init__(self):
        self.sms_service = SMSService()

    def generate_code(self) -> str:
        """Generate a random 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=self.OTP_LENGTH))

    def create_otp(self, phone_number: str) -> dict:
        """
        Create a new OTP for a phone number and send via SMS.

        Returns:
            dict with 'success', 'message', and optionally 'otp_code' (dev only)
        """
        from django.db import transaction

        # Check if too many OTPs requested in last hour (rate limiting)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_otps = OTP.objects.filter(
            phone_number=phone_number,
            created_at__gte=one_hour_ago
        ).count()

        if recent_otps >= self.MAX_OTP_PER_HOUR:
            return {
                'success': False,
                'message': 'Too many OTP requests. Please try again later.'
            }

        # Generate new OTP
        code = self.generate_code()
        expires_at = timezone.now() + timedelta(minutes=self.OTP_VALIDITY_MINUTES)

        # Wrap database operations in transaction
        with transaction.atomic():
            # Invalidate any existing pending OTPs for this phone number
            OTP.objects.filter(
                phone_number=phone_number,
                is_verified=False
            ).update(is_verified=True)  # Mark as used to invalidate

            otp = OTP.objects.create(
                phone_number=phone_number,
                code=code,
                expires_at=expires_at
            )

            # Send SMS with OTP AFTER transaction commits
            message = f"Your SDA Church-Kawangware verification code is: {code}. Valid for {self.OTP_VALIDITY_MINUTES} minutes."

            # Use transaction.on_commit to ensure SMS is sent only after DB commit
            transaction.on_commit(
                lambda: self.sms_service.send_sms(phone_number, message)
            )

        # Print OTP in console for development
        print(f"\n{'='*50}")
        print(f"📱 OTP for {phone_number}: {code}")
        print(f"   Valid for {self.OTP_VALIDITY_MINUTES} minutes")
        print(f"{'='*50}\n")

        response = {
            'success': True,
            'message': f'OTP sent to {phone_number}',
            'expires_in_minutes': self.OTP_VALIDITY_MINUTES
        }

        # Only include OTP code in development mode
        if settings.DEBUG:
            response['otp_code'] = code  # For testing only

        return response

    def verify_otp(self, phone_number: str, code: str) -> dict:
        """
        Verify an OTP code for a phone number.

        Returns:
            dict with 'success', 'message', 'user', and 'member' if successful
        """
        try:
            # Find the most recent pending OTP for this phone number
            otp = OTP.objects.filter(
                phone_number=phone_number,
                is_verified=False
            ).order_by('-created_at').first()

            if not otp:
                return {
                    'success': False,
                    'message': 'No pending OTP found. Please request a new one.'
                }

            # Check if code matches (increment attempts on mismatch)
            if otp.code != code:
                otp.increment_attempts()
                remaining = max(0, 3 - otp.verification_attempts)
                if remaining == 0:
                    return {
                        'success': False,
                        'message': 'Too many failed attempts. Please request a new OTP.'
                    }
                return {
                    'success': False,
                    'message': f'Invalid OTP code. {remaining} attempt(s) remaining.'
                }

            # Check if OTP is valid
            if not otp.is_valid():
                if otp.is_verified:
                    message = 'OTP has already been used'
                elif otp.expires_at <= timezone.now():
                    message = 'OTP has expired. Please request a new one'
                else:
                    message = 'Too many failed attempts. Please request a new OTP'

                return {
                    'success': False,
                    'message': message
                }

            # Mark OTP as verified
            otp.is_verified = True
            otp.save(update_fields=['is_verified'])

            # Get or create user for this phone number
            from members.models import Member

            try:
                member = Member.objects.get(
                    phone_number=phone_number,
                    is_active=True,
                    is_deleted=False
                )
            except Member.DoesNotExist:
                return {
                    'success': False,
                    'message': 'No active member found with this phone number. Please contact church admin.'
                }

            # Get or create Django user linked to this member
            user, created = User.objects.get_or_create(
                username=phone_number,  # Use phone as username
                defaults={
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'email': member.email or '',
                }
            )

            # Set unusable password for newly created users (auth is OTP only)
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password'])

            # Link user to member if not already linked
            if member.user is None or member.user != user:
                member.user = user
                member.save(update_fields=['user'])

            return {
                'success': True,
                'message': 'OTP verified successfully',
                'user': user,
                'member': member
            }

        except Exception as e:
            print(f"❌ Error verifying OTP: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': 'An error occurred during verification'
            }
