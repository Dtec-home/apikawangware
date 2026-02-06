"""
Unit tests for Contribution models - Fixed version.
Tests ContributionCategory and Contribution models.
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from django.db import IntegrityError
from contributions.models import Contribution, ContributionCategory
from tests.utils.factories import (
    ContributionCategoryFactory,
    ContributionFactory,
    MemberFactory,
    MpesaTransactionFactory,
    UserFactory
)


@pytest.mark.unit
class TestContributionCategoryModel:
    """Test cases for ContributionCategory model."""
    
    def test_create_category_with_factory(self, db):
        """Test creating category with factory."""
        category = ContributionCategoryFactory(
            name='Test Category',
            code='TEST',
            description='Test description'
        )
        
        assert category.name == 'Test Category'
        assert category.code == 'TEST'
        assert category.description == 'Test description'
        assert category.is_active is True
    
    def test_category_str_representation_factory(self, db):
        """Test __str__ method with factory."""
        category = ContributionCategoryFactory(name='Building Fund')
        
        assert 'Building Fund' in str(category)
    
    def test_category_deactivation(self, db):
        """Test category can be deactivated."""
        category = ContributionCategoryFactory(is_active=True)
        
        category.is_active = False
        category.save()
        
        assert category.is_active is False


@pytest.mark.unit  
class TestContributionModel:
    """Test cases for Contribution model."""
    
    def test_create_contribution_with_valid_data(self, db):
        """Test creating contribution with valid data."""
        member = MemberFactory()
        category = ContributionCategoryFactory()
        
        contribution = ContributionFactory(
            member=member,
            category=category,
            amount=Decimal('1000.00')
        )
        
        assert contribution.member == member
        assert contribution.category == category
        assert contribution.amount == Decimal('1000.00')
    
    def test_contribution_with_mpesa_transaction(self, db):
        """Test contribution linked to M-Pesa transaction."""
        member = MemberFactory()
        category = ContributionCategoryFactory()
        transaction = MpesaTransactionFactory(phone_number=member.phone_number)
        
        contribution = ContributionFactory(
            member=member,
            category=category,
            mpesa_transaction=transaction,
            entry_type='mpesa'
        )
        
        assert contribution.mpesa_transaction == transaction
        assert contribution.entry_type == 'mpesa'
    
    def test_manual_contribution_with_admin(self, db):
        """Test manual contribution with admin user."""
        admin = UserFactory(is_staff=True, username='testadmin')
        member = MemberFactory()
        category = ContributionCategoryFactory()
        
        contribution = ContributionFactory(
            member=member,
            category=category,
            entry_type='manual',
            entered_by=admin,
            manual_receipt_number='MAN001'
        )
        
        assert contribution.entry_type == 'manual'
        assert contribution.entered_by == admin
        assert contribution.manual_receipt_number == 'MAN001'
    
    def test_contribution_status_choices(self, db):
        """Test contribution status choices."""
        contribution = ContributionFactory(status='pending')
        assert contribution.status == 'pending'
        
        contribution.status = 'completed'
        contribution.save()
        assert contribution.status == 'completed'
    
    def test_timestamps_are_set(self, db):
        """Test that timestamps are automatically set."""
        contribution = ContributionFactory()
        
        assert contribution.created_at is not None
        assert contribution.updated_at is not None
