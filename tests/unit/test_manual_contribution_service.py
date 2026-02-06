"""
Unit tests for Manual Contribution Service.
"""

import pytest
import responses
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from contributions.manual_contribution_service import ManualContributionService
from contributions.models import Contribution
from tests.utils.factories import (
    MemberFactory,
    ContributionCategoryFactory,
    UserFactory
)
from tests.utils.mocks import setup_sms_mocks


@pytest.mark.unit
class TestManualContributionService:
    """Test cases for ManualContributionService."""

    @responses.activate
    def test_create_manual_contribution_existing_member(self, db):
        """Test creating manual contribution for existing member."""
        setup_sms_mocks(responses, scenario='success')

        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory(name='Tithe', is_active=True)
        admin_user = UserFactory(is_staff=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('5000.00'),
            category_id=str(category.id),
            entry_type='manual',
            receipt_number='MAN-001',
            notes='Cash payment',
            entered_by_user=admin_user
        )

        assert result['success'] is True
        assert result['member_created'] is False
        assert result['is_guest'] is False

        contribution = result['contribution']
        assert contribution.member == member
        assert contribution.category == category
        assert contribution.amount == Decimal('5000.00')
        assert contribution.status == 'completed'
        assert contribution.entry_type == 'manual'
        assert contribution.manual_receipt_number == 'MAN-001'
        assert contribution.entered_by == admin_user

    @responses.activate
    def test_create_manual_contribution_new_guest_member(self, db):
        """Test creating manual contribution creates guest member."""
        setup_sms_mocks(responses, scenario='success')

        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254798765432',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='cash'
        )

        assert result['success'] is True
        assert result['member_created'] is True
        assert result['is_guest'] is True

        # Verify guest member was created
        contribution = result['contribution']
        assert contribution.member.phone_number == '254798765432'
        assert contribution.member.is_guest is True
        assert contribution.member.first_name == 'Guest'

    def test_create_manual_contribution_invalid_amount(self, db):
        """Test validation for amount below minimum."""
        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('0.50'),  # Below minimum
            category_id=str(category.id),
            entry_type='manual'
        )

        assert result['success'] is False
        assert 'at least' in result['message'].lower()

    def test_create_manual_contribution_invalid_category(self, db):
        """Test validation for invalid category."""
        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id='99999',  # Non-existent
            entry_type='manual'
        )

        assert result['success'] is False
        assert 'category' in result['message'].lower()

    def test_create_manual_contribution_inactive_category(self, db):
        """Test validation for inactive category."""
        category = ContributionCategoryFactory(is_active=False)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='manual'
        )

        assert result['success'] is False
        assert 'inactive' in result['message'].lower()

    def test_create_manual_contribution_invalid_entry_type(self, db):
        """Test validation for invalid entry type."""
        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='invalid_type'
        )

        assert result['success'] is False
        assert 'entry type' in result['message'].lower()

    def test_create_manual_contribution_invalid_phone_format(self, db):
        """Test validation for invalid phone number format."""
        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='0712345678',  # Invalid format
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='manual'
        )

        assert result['success'] is False

    @responses.activate
    def test_create_manual_contribution_auto_receipt_number(self, db):
        """Test automatic receipt number generation."""
        setup_sms_mocks(responses, scenario='success')

        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='manual',
            receipt_number=None  # Should auto-generate
        )

        assert result['success'] is True
        contribution = result['contribution']
        assert contribution.manual_receipt_number is not None
        assert contribution.manual_receipt_number.startswith('MAN-')

    @responses.activate
    def test_create_manual_contribution_custom_transaction_date(self, db):
        """Test setting custom transaction date."""
        setup_sms_mocks(responses, scenario='success')

        category = ContributionCategoryFactory(is_active=True)
        custom_date = timezone.now() - timezone.timedelta(days=7)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='manual',
            transaction_date=custom_date
        )

        assert result['success'] is True
        contribution = result['contribution']
        assert contribution.transaction_date.date() == custom_date.date()

    def test_lookup_member_by_phone_existing(self, db):
        """Test looking up existing member."""
        member = MemberFactory(phone_number='254712345678')

        service = ManualContributionService()
        result = service.lookup_member_by_phone('254712345678')

        assert result['success'] is True
        assert result['found'] is True
        assert result['member'] == member
        assert result['is_guest'] == member.is_guest

    def test_lookup_member_by_phone_not_found(self, db):
        """Test looking up non-existent member."""
        service = ManualContributionService()
        result = service.lookup_member_by_phone('254798765432')

        assert result['success'] is True
        assert result['found'] is False
        assert 'guest' in result['message'].lower()

    def test_lookup_member_by_phone_invalid_format(self, db):
        """Test lookup with invalid phone format."""
        service = ManualContributionService()
        result = service.lookup_member_by_phone('0712345678')

        assert result['success'] is False

    @responses.activate
    def test_sms_failure_does_not_fail_contribution(self, db):
        """Test that SMS failure doesn't prevent contribution creation."""
        setup_sms_mocks(responses, scenario='failure')

        category = ContributionCategoryFactory(is_active=True)

        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number='254712345678',
            amount=Decimal('1000.00'),
            category_id=str(category.id),
            entry_type='manual'
        )

        # Contribution should still succeed
        assert result['success'] is True
        assert result['sms_sent'] is False
