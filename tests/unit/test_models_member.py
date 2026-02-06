"""
Unit tests for Member model.
Testing model creation, validation, and business logic.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from members.models import Member
from tests.utils.factories import MemberFactory, UserFactory


@pytest.mark.unit
class TestMemberModel:
    """Test cases for Member model."""

    def test_create_member_with_valid_data(self, db):
        """Test creating a member with valid data."""
        member = MemberFactory(
            first_name='John',
            last_name='Doe',
            phone_number='254712345678',
            email='john.doe@example.com'
        )

        assert member.id is not None
        assert member.first_name == 'John'
        assert member.last_name == 'Doe'
        assert member.phone_number == '254712345678'
        assert member.email == 'john.doe@example.com'
        assert member.is_active is True
        assert member.is_guest is False

    def test_member_full_name_property(self, db):
        """Test full_name property returns correct format."""
        member = MemberFactory(first_name='Jane', last_name='Smith')

        assert member.full_name == 'Jane Smith'

    def test_member_str_representation(self, db):
        """Test __str__ method returns correct format."""
        member = MemberFactory(
            first_name='John',
            last_name='Doe',
            member_number='000123'
        )

        assert str(member) == 'John Doe (000123)'

    def test_phone_number_must_be_unique(self, db):
        """Test that phone numbers must be unique."""
        MemberFactory(phone_number='254712345678')

        with pytest.raises(IntegrityError):
            MemberFactory(phone_number='254712345678')

    def test_member_number_must_be_unique(self, db):
        """Test that member numbers must be unique."""
        MemberFactory(member_number='000001')

        with pytest.raises(IntegrityError):
            MemberFactory(member_number='000001')

    def test_phone_number_validation_format(self, db):
        """Test phone number must be in correct format (254XXXXXXXXX)."""
        # Valid format
        member = MemberFactory(phone_number='254712345678')
        member.full_clean()  # Should not raise

        # Invalid formats should raise validation error
        invalid_phones = [
            '0712345678',  # Missing country code
            '254712',  # Too short
            '25471234567890',  # Too long
            '255712345678',  # Wrong country code
            'abcdefghijkl',  # Non-numeric
        ]

        for invalid_phone in invalid_phones:
            member = Member(
                first_name='Test',
                last_name='User',
                phone_number=invalid_phone,
                member_number=f'TEST{invalid_phone[:4]}'
            )
            with pytest.raises(ValidationError):
                member.full_clean()

    def test_member_number_auto_generation(self, db):
        """Test that member number is auto-generated if not provided."""
        # Clear any existing members
        Member.objects.all().delete()

        # Create member without member_number
        member1 = Member.objects.create(
            first_name='First',
            last_name='Member',
            phone_number='254712345678'
        )

        assert member1.member_number == '000001'

        # Create second member
        member2 = Member.objects.create(
            first_name='Second',
            last_name='Member',
            phone_number='254712345679'
        )

        assert member2.member_number == '000002'

    def test_guest_member_flag(self, db):
        """Test creating a guest member."""
        guest = MemberFactory(
            first_name='Guest',
            last_name='Member',
            is_guest=True
        )

        assert guest.is_guest is True
        assert guest.is_active is True

    def test_inactive_member(self, db):
        """Test creating an inactive member."""
        inactive = MemberFactory(is_active=False)

        assert inactive.is_active is False

    def test_member_with_linked_user(self, db):
        """Test member linked to Django User."""
        user = UserFactory(username='testuser')
        member = MemberFactory(user=user)

        assert member.user == user
        assert member.user.username == 'testuser'
        assert hasattr(user, 'member')
        assert user.member == member

    def test_member_without_user(self, db):
        """Test member can exist without linked user."""
        member = MemberFactory(user=None)

        assert member.user is None

    def test_email_is_optional(self, db):
        """Test that email is optional."""
        member = MemberFactory(email=None)

        assert member.email is None
        member.full_clean()  # Should not raise

    def test_import_batch_id_tracking(self, db):
        """Test import batch ID for tracking bulk imports."""
        batch_id = 'IMPORT_2026_02_06_001'
        member = MemberFactory(import_batch_id=batch_id)

        assert member.import_batch_id == batch_id

    def test_soft_delete_functionality(self, db):
        """Test soft delete (is_deleted flag)."""
        member = MemberFactory()

        # Soft delete
        member.is_deleted = True
        member.save()

        # Member still exists in database
        assert Member.objects.filter(id=member.id).exists()

        # But excluded from non-deleted queryset
        assert not Member.objects.filter(id=member.id, is_deleted=False).exists()

    def test_timestamps_are_set(self, db):
        """Test that created_at and updated_at are automatically set."""
        member = MemberFactory()

        assert member.created_at is not None
        assert member.updated_at is not None
        assert member.created_at <= member.updated_at

    def test_member_contributions_relationship(self, db):
        """Test reverse relationship to contributions."""
        from tests.utils.factories import ContributionFactory

        member = MemberFactory()
        contribution1 = ContributionFactory(member=member)
        contribution2 = ContributionFactory(member=member)

        assert member.contributions.count() == 2
        assert contribution1 in member.contributions.all()
        assert contribution2 in member.contributions.all()
