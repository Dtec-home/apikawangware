"""
Pytest configuration and shared fixtures.
This file is automatically loaded by pytest.
"""

import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
import responses

# Import factories
from tests.utils.factories import (
    MemberFactory,
    ContributionCategoryFactory,
    ContributionFactory,
    MpesaTransactionFactory,
    OTPFactory,
    UserFactory,
)


@pytest.fixture
def api_client():
    """
    Django test client for making requests.
    """
    from django.test import Client
    return Client()


@pytest.fixture
def graphql_client():
    """
    Helper for executing GraphQL queries/mutations.
    """
    from tests.utils.graphql_helpers import GraphQLClient
    return GraphQLClient()


@pytest.fixture
def authenticated_user(db):
    """
    Create an authenticated user with a linked member.
    """
    user = UserFactory(username='testuser')
    member = MemberFactory(user=user, phone_number='254712345678')
    return user, member


@pytest.fixture
def admin_user(db):
    """
    Create an admin user.
    """
    return UserFactory(username='admin', is_staff=True, is_superuser=True)


@pytest.fixture
def sample_member(db):
    """
    Create a sample member for testing.
    """
    return MemberFactory(
        first_name='John',
        last_name='Doe',
        phone_number='254712345678',
        is_active=True,
        is_guest=False
    )


@pytest.fixture
def guest_member(db):
    """
    Create a guest member for testing.
    """
    return MemberFactory(
        first_name='Guest',
        last_name='Member',
        phone_number='254798765432',
        is_active=True,
        is_guest=True
    )


@pytest.fixture
def active_categories(db):
    """
    Create standard active contribution categories.
    """
    return [
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True),
        ContributionCategoryFactory(name='Offering', code='OFFER', is_active=True),
        ContributionCategoryFactory(name='Building Fund', code='BUILD', is_active=True),
        ContributionCategoryFactory(name='Missions', code='MISSION', is_active=True),
    ]


@pytest.fixture
def inactive_category(db):
    """
    Create an inactive category for testing validation.
    """
    return ContributionCategoryFactory(
        name='Inactive Category',
        code='INACTIVE',
        is_active=False
    )


@pytest.fixture
def pending_mpesa_transaction(db, sample_member):
    """
    Create a pending M-Pesa transaction.
    """
    return MpesaTransactionFactory(
        phone_number=sample_member.phone_number,
        amount=Decimal('1000.00'),
        status='pending',
        account_reference='TITHE'
    )


@pytest.fixture
def completed_mpesa_transaction(db, sample_member):
    """
    Create a completed M-Pesa transaction.
    """
    return MpesaTransactionFactory(
        phone_number=sample_member.phone_number,
        amount=Decimal('1000.00'),
        status='completed',
        account_reference='TITHE',
        mpesa_receipt_number='ABC123XYZ',
        result_code='0'
    )


@pytest.fixture
def valid_otp(db):
    """
    Create a valid, unexpired OTP.
    """
    return OTPFactory(
        phone_number='254712345678',
        code='123456',
        is_verified=False,
        expires_at=timezone.now() + timezone.timedelta(minutes=10)
    )


@pytest.fixture
def expired_otp(db):
    """
    Create an expired OTP.
    """
    return OTPFactory(
        phone_number='254712345678',
        code='999999',
        is_verified=False,
        expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )


@pytest.fixture
def mock_mpesa_api():
    """
    Mock M-Pesa API responses using responses library.
    """
    with responses.RequestsMock() as rsps:
        # Mock auth endpoint
        rsps.add(
            responses.GET,
            'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            json={'access_token': 'test_access_token', 'expires_in': '3599'},
            status=200
        )

        # Mock STK push endpoint
        rsps.add(
            responses.POST,
            'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            json={
                'MerchantRequestID': 'test_merchant_123',
                'CheckoutRequestID': 'test_checkout_456',
                'ResponseCode': '0',
                'ResponseDescription': 'Success. Request accepted for processing',
                'CustomerMessage': 'Success. Request accepted for processing'
            },
            status=200
        )

        yield rsps


@pytest.fixture
def mock_sms_api():
    """
    Mock Mobitech SMS API responses.
    """
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            'https://app.mobitechtechnologies.com//sms/sendsms',
            json={
                'success': True,
                'message': 'SMS sent successfully',
                'messageId': 'test_msg_123'
            },
            status=200
        )

        yield rsps


@pytest.fixture
def mock_all_external_apis(mock_mpesa_api, mock_sms_api):
    """
    Mock all external APIs (M-Pesa and SMS).
    Useful for integration tests.
    """
    return {
        'mpesa': mock_mpesa_api,
        'sms': mock_sms_api
    }


# Pytest Django configuration
@pytest.fixture(scope='session')
def django_db_setup():
    """
    Configure test database settings.
    """
    from django.conf import settings

    # Use a separate test database
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_church_funds',
        'USER': settings.DATABASES['default'].get('USER', 'postgres'),
        'PASSWORD': settings.DATABASES['default'].get('PASSWORD', ''),
        'HOST': settings.DATABASES['default'].get('HOST', 'localhost'),
        'PORT': settings.DATABASES['default'].get('PORT', '5432'),
        'ATOMIC_REQUESTS': False,
        'AUTOCOMMIT': True,
        'CONN_MAX_AGE': 0,
        'OPTIONS': {},
        'TIME_ZONE': None,
        'TEST': {
            'NAME': 'test_church_funds',
        },
    }


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    """
    pass


# ============================================================================
# Database Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True, scope='function')
def cleanup_test_data(django_db_blocker):
    """Clean up test data after each test to prevent pollution."""
    with django_db_blocker.unblock():
        yield  # Run the test

        # Clean up in reverse order of dependencies
        from contributions.models import Contribution, ContributionCategory
        from mpesa.models import MpesaCallback, MpesaTransaction
        from members.models import Member
        from members.otp import OTP
        from django.contrib.auth.models import User

        try:
            # Delete contributions first (has foreign keys to members)
            Contribution.objects.all().delete()

            # Delete M-Pesa callbacks and transactions
            MpesaCallback.objects.all().delete()
            MpesaTransaction.objects.all().delete()

            # Delete OTPs
            OTP.objects.all().delete()

            # Delete test categories
            ContributionCategory.objects.exclude(
                code__in=['TITHE', 'OFFERING', 'BUILDING', 'MISSIONS', 'WELFARE', 'SPECIAL']
            ).delete()

            # Delete test members
            Member.objects.all().delete()

            # Delete test users
            User.objects.exclude(is_superuser=True).delete()
        except Exception as e:
            print(f"Cleanup warning: {e}")
