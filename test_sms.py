#!/usr/bin/env python
"""
Simple script to test Africa's Talking SMS integration
Run this from the church_BE directory: python test_sms.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_BE.settings')
django.setup()

from members.otp import OTPService, SMSService


def test_sms_service():
    """Test SMS service directly"""
    print("\n" + "="*60)
    print("Testing Africa's Talking SMS Service")
    print("="*60 + "\n")

    sms_service = SMSService()

    # Print configuration
    print("📋 Configuration:")
    print(f"   Username: {sms_service.username}")
    print(f"   API Key: {'*' * 20}{sms_service.api_key[-10:] if sms_service.api_key else 'Not set'}")
    print(f"   Sender ID: {sms_service.sender_id or 'None (will use default)'}")
    print()

    # Test phone number (replace with your actual test number)
    phone_number = input("Enter test phone number (e.g., 254712345678): ").strip()

    if not phone_number:
        print("❌ Phone number is required")
        return

    # Ensure phone number starts with +
    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'

    # Test message
    test_message = "Test message from Church Funds System. Your verification code is: 123456"

    print(f"\n📤 Sending test SMS to {phone_number}...")
    print(f"   Message: {test_message}")
    print()

    result = sms_service.send_sms(phone_number, test_message)

    print("\n" + "="*60)
    if result['success']:
        print("✅ SMS sent successfully!")
    else:
        print("❌ SMS failed!")
    print(f"   {result['message']}")
    print("="*60 + "\n")


def test_otp_service():
    """Test OTP service (which uses SMS service internally)"""
    print("\n" + "="*60)
    print("Testing OTP Service")
    print("="*60 + "\n")

    otp_service = OTPService()

    # Test phone number
    phone_number = input("Enter test phone number (e.g., 254712345678): ").strip()

    if not phone_number:
        print("❌ Phone number is required")
        return

    # Ensure phone number starts with +
    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'

    print(f"\n📤 Creating OTP for {phone_number}...")

    result = otp_service.create_otp(phone_number)

    print("\n" + "="*60)
    if result['success']:
        print("✅ OTP created successfully!")
        print(f"   {result['message']}")
        print(f"   Valid for: {result['expires_in_minutes']} minutes")

        if 'otp_code' in result:
            print(f"\n   🔑 OTP Code (DEV MODE): {result['otp_code']}")
            print("   Note: In production, this won't be in the response")
    else:
        print("❌ OTP creation failed!")
        print(f"   {result['message']}")
    print("="*60 + "\n")


def main():
    """Main test menu"""
    while True:
        print("\n" + "="*60)
        print("Africa's Talking SMS Test Menu")
        print("="*60)
        print("1. Test SMS Service (direct SMS)")
        print("2. Test OTP Service (OTP generation + SMS)")
        print("3. Exit")
        print("="*60)

        choice = input("\nSelect option (1-3): ").strip()

        if choice == '1':
            test_sms_service()
        elif choice == '2':
            test_otp_service()
        elif choice == '3':
            print("\n👋 Goodbye!\n")
            break
        else:
            print("\n❌ Invalid choice. Please select 1, 2, or 3.\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted. Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        import traceback
        traceback.print_exc()
