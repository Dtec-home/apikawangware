"""
Unit tests for OTP Service - Fixed version.
"""

import pytest
import responses
from django.utils import timezone
from datetime import timedelta
from members.otp import OTPService, SMSService, OTP
from members.models import Member
from tests.utils.factories import OTPFactory, MemberFactory
from tests.utils.mocks import setup_sms_mocks


@pytest.mark.unit
@pytest.mark.sms
class TestSMSService:
    """Test cases for SMSService."""
    
    @responses.activate
    def test_send_sms_success(self):
        """Test successful SMS sending."""
        setup_sms_mocks(responses, scenario='success')
        
        sms_service = SMSService()
        result = sms_service.send_sms('254712345678', 'Test message')
        
        assert result['success'] is True
    
    @responses.activate
    def test_send_sms_failure(self):
        """Test failed SMS sending."""
        setup_sms_mocks(responses, scenario='failure')
        
        sms_service = SMSService()
        result = sms_service.send_sms('254712345678', 'Test message')
        
        assert result['success'] is False
    
    def test_sms_service_singleton(self):
        """Test that SMSService is a singleton."""
        service1 = SMSService()
        service2 = SMSService()
        
        assert service1 is service2


@pytest.mark.unit
class TestOTPService:
    """Test cases for OTPService."""
    
    @responses.activate
    def test_create_otp_success(self, db):
        """Test successful OTP creation and SMS sending."""
        setup_sms_mocks(responses, scenario='success')
        
        service = OTPService()
        result = service.create_otp('254712345678')
        
        assert result['success'] is True
        assert 'message' in result
        
        # Verify OTP was created in database
        otp = OTP.objects.filter(phone_number='254712345678').first()
        assert otp is not None
        assert len(otp.code) == 6
        assert otp.is_verified is False
    
    @responses.activate
    def test_create_otp_invalidates_previous(self, db):
        """Test that creating new OTP invalidates previous ones."""
        setup_sms_mocks(responses, scenario='success')
        
        # Create first OTP
        service = OTPService()
        service.create_otp('254712345678')
        
        # Create second OTP
        service.create_otp('254712345678')
        
        # Should have 2 OTPs, but only the latest is valid
        otps = OTP.objects.filter(phone_number='254712345678').order_by('-created_at')
        assert otps.count() == 2
        
        latest_otp = otps.first()
        assert latest_otp.is_valid() is True
    
    def test_verify_otp_success_existing_member(self, db):
        """Test successful OTP verification for existing member."""
        # Create member
        member = MemberFactory(phone_number='254712345678')
        
        # Create valid OTP
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        service = OTPService()
        result = service.verify_otp('254712345678', '123456')
        
        assert result['success'] is True
        assert result['member'] == member
        assert result['user'] is not None
        
        # Verify OTP was marked as verified
        otp.refresh_from_db()
        assert otp.is_verified is True
    
    def test_verify_otp_no_member_found(self, db):
        """Test OTP verification fails when no member exists."""
        # Create valid OTP but no member
        otp = OTPFactory(
            phone_number='254798765432',
            code='123456',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        service = OTPService()
        result = service.verify_otp('254798765432', '123456')
        
        # Should fail because member doesn't exist
        assert result['success'] is False
        assert 'No active member found' in result['message']
    
    def test_verify_otp_invalid_code(self, db):
        """Test OTP verification with wrong code."""
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        
        service = OTPService()
        result = service.verify_otp('254712345678', '999999')  # Wrong code
        
        assert result['success'] is False
        assert 'Invalid OTP' in result['message']
    
    def test_verify_otp_expired(self, db):
        """Test OTP verification with expired OTP."""
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            expires_at=timezone.now() - timedelta(minutes=1)  # Expired
        )
        
        service = OTPService()
        result = service.verify_otp('254712345678', '123456')
        
        assert result['success'] is False
        assert 'expired' in result['message'].lower()
    
    def test_verify_otp_max_attempts(self, db):
        """Test OTP verification fails after max attempts."""
        otp = OTPFactory(
            phone_number='254712345678',
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=5),
            verification_attempts=3  # Max attempts reached
        )
        
        service = OTPService()
        result = service.verify_otp('254712345678', '123456')
        
        assert result['success'] is False
        assert 'attempts' in result['message'].lower()
    
    def test_verify_otp_no_otp_found(self, db):
        """Test OTP verification when no OTP exists."""
        service = OTPService()
        result = service.verify_otp('254712345678', '123456')
        
        assert result['success'] is False
        assert 'Invalid OTP' in result['message']
    
    def test_generate_code_format(self):
        """Test that generated OTP code is 6 digits."""
        service = OTPService()
        code = service.generate_code()
        
        assert len(code) == 6
        assert code.isdigit()
    
    def test_generate_code_uniqueness(self):
        """Test that generated codes are reasonably unique."""
        service = OTPService()
        codes = set()
        
        for _ in range(100):
            codes.add(service.generate_code())
        
        # Should have generated many unique codes
        assert len(codes) > 90  # Allow some duplicates due to randomness
