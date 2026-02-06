"""
Factory classes for creating test data.
Using factory_boy for creating model instances with sensible defaults.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
import uuid

from members.models import Member
from contributions.models import Contribution, ContributionCategory
from mpesa.models import MpesaTransaction, MpesaCallback
from members.otp import OTP

fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for Django User model."""

    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user{10000 + n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False


class MemberFactory(DjangoModelFactory):
    """Factory for Member model."""

    class Meta:
        model = Member
        django_get_or_create = ('phone_number',)  # Get or create by phone number

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone_number = factory.Sequence(lambda n: f'2547{str(10000000 + n).zfill(8)}')
    email = factory.LazyAttribute(lambda obj: f'{obj.first_name.lower()}.{obj.last_name.lower()}@example.com')
    member_number = factory.Sequence(lambda n: str(100000 + n).zfill(6))
    is_active = True
    is_guest = False
    user = None  # Optional user link
    import_batch_id = None


class ContributionCategoryFactory(DjangoModelFactory):
    """Factory for ContributionCategory model."""

    class Meta:
        model = ContributionCategory
        django_get_or_create = ('code',)  # Get or create by code

    name = factory.Sequence(lambda n: f'Category {1000 + n}')
    code = factory.Sequence(lambda n: f'CAT{1000 + n}')
    description = factory.Faker('sentence')
    is_active = True


class MpesaTransactionFactory(DjangoModelFactory):
    """Factory for MpesaTransaction model."""

    class Meta:
        model = MpesaTransaction

    merchant_request_id = factory.LazyFunction(lambda: f'merchant_{uuid.uuid4().hex[:10]}')
    checkout_request_id = factory.LazyFunction(lambda: f'checkout_{uuid.uuid4().hex[:10]}')
    phone_number = factory.Sequence(lambda n: f'2547{str(n).zfill(8)}')
    amount = factory.LazyFunction(lambda: Decimal(str(fake.random_int(min=100, max=10000))))
    account_reference = 'TITHE'
    transaction_desc = 'Test contribution'
    status = 'pending'
    mpesa_receipt_number = None
    transaction_date = None
    result_desc = None
    result_code = None


class MpesaCallbackFactory(DjangoModelFactory):
    """Factory for MpesaCallback model."""

    class Meta:
        model = MpesaCallback

    merchant_request_id = factory.LazyFunction(lambda: f'merchant_{uuid.uuid4().hex[:10]}')
    checkout_request_id = factory.LazyFunction(lambda: f'checkout_{uuid.uuid4().hex[:10]}')
    result_code = '0'
    result_desc = 'The service request is processed successfully.'
    raw_data = factory.LazyFunction(lambda: {
        'Body': {
            'stkCallback': {
                'MerchantRequestID': 'test_merchant',
                'CheckoutRequestID': 'test_checkout',
                'ResultCode': 0,
                'ResultDesc': 'The service request is processed successfully.'
            }
        }
    })
    transaction = None


class ContributionFactory(DjangoModelFactory):
    """Factory for Contribution model."""

    class Meta:
        model = Contribution

    member = factory.SubFactory(MemberFactory)
    category = factory.SubFactory(ContributionCategoryFactory)
    mpesa_transaction = None
    contribution_group_id = factory.LazyFunction(uuid.uuid4)
    entry_type = 'mpesa'
    manual_receipt_number = None
    entered_by = None
    amount = factory.LazyFunction(lambda: Decimal(str(fake.random_int(min=100, max=10000))))
    status = 'pending'
    transaction_date = factory.LazyFunction(timezone.now)
    notes = ''


class OTPFactory(DjangoModelFactory):
    """Factory for OTP model."""

    class Meta:
        model = OTP

    phone_number = factory.Sequence(lambda n: f'2547{str(20000000 + n).zfill(8)}')
    code = factory.Sequence(lambda n: str(100000 + (n % 900000)).zfill(6))
    is_verified = False
    expires_at = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(minutes=10))
    verification_attempts = 0
