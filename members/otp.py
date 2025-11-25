"""
OTP (One-Time Password) Management with Africa's Talking
Following SOLID principles:
- SRP: Single responsibility for OTP generation and validation
- DIP: Depends on SMS service abstraction
"""

import random
import string
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
import logging

# Import africastalking at module level to avoid namespace conflict with local 'schema' directory
try:
    import africastalking
    AFRICASTALKING_AVAILABLE = True
except ImportError:
    AFRICASTALKING_AVAILABLE = False



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
    SMS Service using Africa's Talking.
    Following SRP: Only responsible for sending SMS.
    Singleton Pattern: Ensures we only initialize the SDK once.
    """
    _instance = None

    def __new__(cls):
        """
        Singleton Pattern: Ensures we only initialize the SDK once.
        """
        if cls._instance is None:
            cls._instance = super(SMSService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Africa's Talking SDK once"""
        self.logger = logging.getLogger(__name__)

        self.username = getattr(settings, 'AFRICASTALKING_USERNAME', None)
        self.api_key = getattr(settings, 'AFRICASTALKING_API_KEY', None)
        self.sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', None)

        # Debug logging
        print(f"\n{'='*50}")
        print(f"🔧 SMS Service Initialization")
        print(f"   Username: {self.username}")
        print(f"   API Key: {'*' * 10 if self.api_key else 'None'}")
        print(f"   Sender ID: {self.sender_id if self.sender_id else 'None (will use default)'}")
        print(f"{'='*50}\n")

        if not AFRICASTALKING_AVAILABLE:
            self.logger.warning("AfricasTalking SDK not installed.")
            self.sms = None
            return

        try:
            africastalking.initialize(self.username, self.api_key)
            self.sms = africastalking.SMS
            self.logger.info("AfricasTalking initialized successfully.")
            print("✅ AfricasTalking initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize AfricasTalking: {e}")
            print(f"❌ Failed to initialize AfricasTalking: {e}")
            self.sms = None

    def send_sms(self, phone_number: str, message: str) -> dict:
        """
        Send SMS using Africa's Talking API.

        Args:
            phone_number: Phone number in format +254XXXXXXXXX or 254XXXXXXXXX
            message: Message to send

        Returns:
            dict with 'success' and 'message'
        """
        # Development mode - just log and return success
        if settings.DEBUG and self.sms is None:
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
            # Format phone number (ensure it starts with +)
            if not phone_number.startswith('+'):
                phone_number = f'+{phone_number}'

            # Send SMS - only include sender_id if it's set
            sms_params = {
                'message': message,
                'recipients': [phone_number]
            }

            # Only add sender_id if it's configured and not None
            if self.sender_id:
                sms_params['sender_id'] = self.sender_id
                print(f"📤 Sending SMS WITH sender_id: {self.sender_id}")
            else:
                print(f"📤 Sending SMS WITHOUT sender_id (using default)")

            print(f"📤 SMS Params: {sms_params}")

            response = self.sms.send(**sms_params)

            self.logger.info(f"SMS Response: {response}")
            print(f"📱 SMS Response: {response}")

            # Check if SMS was sent successfully
            if response['SMSMessageData']['Recipients']:
                recipient = response['SMSMessageData']['Recipients'][0]
                if recipient['statusCode'] == 101:  # Success code
                    return {
                        'success': True,
                        'message': 'SMS sent successfully'
                    }
                else:
                    self.logger.error(f"SMS failed: {recipient['status']}")
                    return {
                        'success': False,
                        'message': f"SMS failed: {recipient['status']}"
                    }
            else:
                return {
                    'success': False,
                    'message': 'No recipients in response'
                }

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(f"Error sending SMS to {phone_number}: {e}\n{error_details}")
            print(f"❌ Error sending SMS: {str(e)}")
            print(f"❌ Full error details:\n{error_details}")
            # For development - still show the message
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
            message = f"Your Church Funds verification code is: {code}. Valid for {self.OTP_VALIDITY_MINUTES} minutes."

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
            # Find the most recent OTP for this phone number
            otp = OTP.objects.filter(
                phone_number=phone_number,
                code=code
            ).order_by('-created_at').first()

            if not otp:
                return {
                    'success': False,
                    'message': 'Invalid OTP code'
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

            # Verify code matches
            if otp.code != code:
                otp.increment_attempts()
                return {
                    'success': False,
                    'message': 'Invalid OTP code'
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

            # Link user to member if needed
            if not hasattr(member, 'user') or member.user is None or member.user != user:
                # Add user field to member model if it doesn't exist
                # This will be handled in the model migration

                print(f"✅ User authenticated: {user.username}")

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
