"""
GraphQL Queries
Following SRP: Each query has single responsibility
"""

import strawberry
from typing import List, Optional
from django.db.models import Q
from django.utils import timezone
from datetime import date

from .types import (
    ContributionType,
    ContributionCategoryType,
    MemberType,
    AnnouncementType,
    DevotionalType,
    EventType,
    YouTubeVideoType,
    CategoryAdminType,
    CategoryAdminRoleType,
    UserRoleInfo,
)
from .admin_queries import (
    AdminQueries,
    PaginatedContributions,
    ContributionStats,
    DashboardStats,
    ContributionFilters,
    PaginationInput
)
from contributions.models import CategoryAdmin
from contributions.models import Contribution, ContributionCategory
from members.models import Member
from content.models import Announcement, Devotional, Event, YouTubeVideo


@strawberry.type
class Query:
    """Root Query type - combines public and admin queries"""

    # Admin queries - delegated to AdminQueries class
    all_contributions: PaginatedContributions = strawberry.field(resolver=AdminQueries.all_contributions)
    contribution_stats: ContributionStats = strawberry.field(resolver=AdminQueries.contribution_stats)
    dashboard_stats: DashboardStats = strawberry.field(resolver=AdminQueries.dashboard_stats)
    members_list: List[MemberType] = strawberry.field(resolver=AdminQueries.members_list)

    # Category admin queries - delegated to AdminQueries class
    category_admins: List[CategoryAdminType] = strawberry.field(resolver=AdminQueries.category_admins)
    my_category_admin_roles: List[CategoryAdminRoleType] = strawberry.field(resolver=AdminQueries.my_category_admin_roles)
    is_category_admin: bool = strawberry.field(resolver=AdminQueries.is_category_admin)
    current_user_role: UserRoleInfo = strawberry.field(resolver=AdminQueries.current_user_role)

    # Contribution queries
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
    def contributions_by_checkout_id(
        self,
        checkout_request_id: str
    ) -> List[ContributionType]:
        """
        Get all contributions associated with a specific M-Pesa checkout request ID.
        Used by the confirmation page for multi-category contributions where no
        single contribution ID is available.
        """
        from mpesa.models import MpesaTransaction
        try:
            transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
            return transaction.contributions.select_related(
                'member', 'category', 'mpesa_transaction'
            ).all()
        except MpesaTransaction.DoesNotExist:
            return []

    @strawberry.field
    def payment_status(
        self,
        checkout_request_id: str
    ) -> str:
        """
        Check the status of an M-Pesa payment by checkout request ID.
        Returns: 'pending', 'completed', 'failed', or 'not_found'
        """
        from mpesa.models import MpesaTransaction

        try:
            transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
            return transaction.status
        except MpesaTransaction.DoesNotExist:
            return 'not_found'

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

    # Content queries for landing page
    @strawberry.field
    def announcements(
        self,
        limit: Optional[int] = 5
    ) -> List[AnnouncementType]:
        """
        Get recent active announcements for the landing page.
        Ordered by priority and publish date.
        """
        now = timezone.now()
        return Announcement.objects.filter(
            is_active=True,
            is_deleted=False,
            publish_date__lte=now
        ).order_by('-priority', '-publish_date')[:limit]

    @strawberry.field
    def devotionals(
        self,
        limit: Optional[int] = 6,
        featured: Optional[bool] = None
    ) -> List[DevotionalType]:
        """
        Get published devotionals for the landing page.
        Can filter by featured status.
        """
        queryset = Devotional.objects.filter(
            is_published=True,
            is_deleted=False
        )

        if featured is not None:
            queryset = queryset.filter(is_featured=featured)

        return queryset.order_by('-publish_date')[:limit]

    @strawberry.field
    def devotional(
        self,
        id: strawberry.ID
    ) -> Optional[DevotionalType]:
        """
        Get a single devotional by ID for detail page.
        """
        try:
            return Devotional.objects.get(
                id=id,
                is_published=True,
                is_deleted=False
            )
        except Devotional.DoesNotExist:
            return None

    @strawberry.field
    def events(
        self,
        upcoming: Optional[bool] = True,
        limit: Optional[int] = 6
    ) -> List[EventType]:
        """
        Get events for the landing page.
        By default shows upcoming events.
        """
        queryset = Event.objects.filter(
            is_active=True,
            is_deleted=False
        )

        if upcoming is not None:
            today = date.today()
            if upcoming:
                queryset = queryset.filter(event_date__gte=today)
            else:
                queryset = queryset.filter(event_date__lt=today)

        return queryset.order_by('event_date', 'event_time')[:limit]

    @strawberry.field
    def event(
        self,
        id: strawberry.ID
    ) -> Optional[EventType]:
        """
        Get a single event by ID for detail page.
        """
        try:
            return Event.objects.get(
                id=id,
                is_active=True,
                is_deleted=False
            )
        except Event.DoesNotExist:
            return None

    @strawberry.field
    def youtube_videos(
        self,
        limit: Optional[int] = 6,
        featured: Optional[bool] = None,
        category: Optional[str] = None
    ) -> List[YouTubeVideoType]:
        """
        Get YouTube videos for the landing page.
        Can filter by featured status and category.
        """
        queryset = YouTubeVideo.objects.filter(is_deleted=False)

        if featured is not None:
            queryset = queryset.filter(is_featured=featured)

        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by('-publish_date')[:limit]