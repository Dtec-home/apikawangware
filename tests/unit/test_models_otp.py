"""
Unit tests for OTP model.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from members.otp import OTP
from tests.utils.factories import OTPFactory


@pytest.mark.unit
class TestOTPModel:
    """Test cases for OTP model."""

    def test_create_otp_with_valid_data(self, db):
        """Test creating an OTP with valid data."""
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            is_verified=False
        )

        assert otp.id is not None
        assert otp.phone_number == '254712345678'
        assert otp.code == '123456'
        assert otp.is_verified is False
        assert otp.verification_attempts == 0

    def test_otp_str_representation(self, db):
        """Test __str__ method returns correct format."""
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            is_verified=False
        )

        assert str(otp) == 'OTP for 254712345678 - Pending'

    def test_is_valid_for_unexpired_otp(self, db):
        """Test is_valid returns True for unexpired, unverified OTP."""
        otp = OTPFactory(
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=5)
        )

        assert otp.is_valid() is True

    def test_is_valid_for_expired_otp(self, db):
        """Test is_valid returns False for expired OTP."""
        otp = OTPFactory(
            is_verified=False,
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        assert otp.is_valid() is False

    def test_is_valid_for_verified_otp(self, db):
        """Test is_valid returns False for already verified OTP."""
        otp = OTPFactory(
            is_verified=True,
            expires_at=timezone.now() + timedelta(minutes=5)
        )

        assert otp.is_valid() is False

    def test_is_valid_for_expired_and_verified_otp(self, db):
        """Test is_valid returns False for expired and verified OTP."""
        otp = OTPFactory(
            is_verified=True,
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        assert otp.is_valid() is False

    def test_increment_attempts(self, db):
        """Test increment_attempts increases verification_attempts."""
        otp = OTPFactory(verification_attempts=0)

        otp.increment_attempts()
        assert otp.verification_attempts == 1

        otp.increment_attempts()
        assert otp.verification_attempts == 2

        otp.increment_attempts()
        assert otp.verification_attempts == 3

    def test_verification_attempts_default_to_zero(self, db):
        """Test verification_attempts defaults to 0."""
        otp = OTPFactory()

        assert otp.verification_attempts == 0

    def test_multiple_otps_same_phone_number(self, db):
        """Test multiple OTPs can exist for same phone number."""
        phone = '254712345678'

        otp1 = OTPFactory(phone_number=phone, code='111111')
        otp2 = OTPFactory(phone_number=phone, code='222222')

        assert OTP.objects.filter(phone_number=phone).count() == 2

    def test_otp_ordering(self, db):
        """Test OTPs are ordered by created_at descending."""
        old = OTPFactory()
        old.created_at = timezone.now() - timedelta(hours=1)
        old.save()

        recent = OTPFactory()

        otps = list(OTP.objects.all())

        assert otps[0] == recent
        assert otps[1] == old

    def test_otp_expiration_time(self, db):
        """Test OTP expiration is set correctly."""
        now = timezone.now()
        expires_at = now + timedelta(minutes=10)

        otp = OTPFactory(expires_at=expires_at)

        # Should be valid now
        assert otp.is_valid() is True

        # Simulate time passing
        otp.expires_at = now - timedelta(seconds=1)
        otp.save()

        # Should be invalid after expiration
        assert otp.is_valid() is False

    def test_timestamps_are_set(self, db):
        """Test that created_at is automatically set."""
        otp = OTPFactory()

        assert otp.created_at is not None
