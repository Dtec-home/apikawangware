"""
GraphQL Queries
Following SRP: Each query has single responsibility
"""

import strawberry
from typing import List, Optional
from django.db.models import Q

from .types import (
    ContributionType,
    ContributionCategoryType,
    MemberType
)
from contributions.models import Contribution, ContributionCategory
from members.models import Member


@strawberry.type
class Query:
    """Root Query type"""

    @strawberry.field
    def contribution_categories(
        self,
        is_active: Optional[bool] = None
    ) -> List[ContributionCategoryType]:
        """
        Get all contribution categories.
        Can filter by active status.
        """
        queryset = ContributionCategory.objects.filter(is_deleted=False)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        return queryset.order_by('name')

    @strawberry.field
    def contribution_category(
        self,
        id: Optional[strawberry.ID] = None,
        code: Optional[str] = None
    ) -> Optional[ContributionCategoryType]:
        """
        Get a single contribution category by ID or code.
        """
        try:
            if id:
                return ContributionCategory.objects.get(id=id, is_deleted=False)
            elif code:
                return ContributionCategory.objects.get(code=code, is_deleted=False)
            return None
        except ContributionCategory.DoesNotExist:
            return None

    @strawberry.field
    def my_contributions(
        self,
        phone_number: str,
        limit: Optional[int] = 20,
        category_id: Optional[strawberry.ID] = None
    ) -> List[ContributionType]:
        """
        Get contributions for a specific member by phone number.
        Following Sprint 1 spec: my_contributions query.
        
        Args:
            phone_number: Member's phone number
            limit: Maximum number of results (default 20)
            category_id: Optional filter by category
        """
        try:
            # Find member by phone number
            member = Member.objects.get(
                phone_number=phone_number,
                is_active=True,
                is_deleted=False
            )
            
            # Build query
            queryset = Contribution.objects.filter(
                member=member
            ).select_related(
                'member',
                'category',
                'mpesa_transaction'
            )
            
            # Filter by category if provided
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            # Order by transaction date (newest first) and limit
            return queryset.order_by('-transaction_date')[:limit]
            
        except Member.DoesNotExist:
            return []

    @strawberry.field
    def contribution(
        self,
        id: strawberry.ID
    ) -> Optional[ContributionType]:
        """
        Get a single contribution by ID.
        """
        try:
            return Contribution.objects.select_related(
                'member',
                'category',
                'mpesa_transaction'
            ).get(id=id)
        except Contribution.DoesNotExist:
            return None

    @strawberry.field
    def member_by_phone(
        self,
        phone_number: str
    ) -> Optional[MemberType]:
        """
        Find a member by phone number.
        Useful for validation before creating contribution.
        """
        try:
            return Member.objects.get(
                phone_number=phone_number,
                is_active=True,
                is_deleted=False
            )
        except Member.DoesNotExist:
            return None