"""
Admin-Only GraphQL Queries
Following SRP: Admin queries separated from public queries
Following DIP: Depends on permission abstractions
"""

import strawberry
from typing import List, Optional
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal

from .types import ContributionType, MemberType, ContributionCategoryType
from contributions.models import Contribution, ContributionCategory
from members.models import Member
from members.roles import PermissionChecker


@strawberry.type
class ContributionStats:
    """Statistics for contributions"""
    total_amount: str  # Decimal as string
    total_count: int
    completed_amount: str
    completed_count: int
    pending_amount: str
    pending_count: int
    failed_count: int


@strawberry.type
class DashboardStats:
    """Dashboard statistics"""
    today_total: str
    today_count: int
    week_total: str
    week_count: int
    month_total: str
    month_count: int
    total_amount: str
    total_count: int
    total_members: int
    active_members: int


@strawberry.input
class ContributionFilters:
    """Filters for contribution queries"""
    status: Optional[str] = None
    category_id: Optional[strawberry.ID] = None
    member_id: Optional[strawberry.ID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None  # Search by member name or phone


@strawberry.input
class PaginationInput:
    """Pagination parameters"""
    limit: int = 20
    offset: int = 0


@strawberry.type
class PaginatedContributions:
    """Paginated contribution results"""
    items: List[ContributionType]
    total: int
    has_more: bool


@strawberry.type
class AdminQueries:
    """Admin-only queries"""

    @strawberry.field
    def all_contributions(
        self,
        info,
        filters: Optional[ContributionFilters] = None,
        pagination: Optional[PaginationInput] = None
    ) -> PaginatedContributions:
        """
        Get all contributions with filters and pagination.
        Requires staff role (admin, treasurer, or pastor).

        Args:
            filters: Optional filters for contributions
            pagination: Pagination parameters

        Returns:
            PaginatedContributions with items and metadata
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        # Build queryset
        queryset = Contribution.objects.select_related(
            'member',
            'category',
            'mpesa_transaction'
        ).all()

        # Apply filters
        if filters:
            if filters.status:
                queryset = queryset.filter(status=filters.status)

            if filters.category_id:
                queryset = queryset.filter(category_id=filters.category_id)

            if filters.member_id:
                queryset = queryset.filter(member_id=filters.member_id)

            if filters.date_from:
                queryset = queryset.filter(transaction_date__gte=filters.date_from)

            if filters.date_to:
                queryset = queryset.filter(transaction_date__lte=filters.date_to)

            if filters.search:
                # Search by member name or phone
                queryset = queryset.filter(
                    Q(member__first_name__icontains=filters.search) |
                    Q(member__last_name__icontains=filters.search) |
                    Q(member__phone_number__icontains=filters.search)
                )

        # Get total count before pagination
        total = queryset.count()

        # Apply ordering and pagination
        queryset = queryset.order_by('-transaction_date')

        if pagination:
            limit = pagination.limit
            offset = pagination.offset
            queryset = queryset[offset:offset + limit]
            has_more = (offset + limit) < total
        else:
            has_more = False

        return PaginatedContributions(
            items=list(queryset),
            total=total,
            has_more=has_more
        )

    @strawberry.field
    def contribution_stats(
        self,
        info,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> ContributionStats:
        """
        Get contribution statistics.
        Requires staff role.

        Args:
            date_from: Optional start date
            date_to: Optional end date

        Returns:
            ContributionStats with aggregated data
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        queryset = Contribution.objects.all()

        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(transaction_date__lte=date_to)

        # Aggregate statistics
        total_stats = queryset.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )

        completed_stats = queryset.filter(status='completed').aggregate(
            completed_amount=Sum('amount'),
            completed_count=Count('id')
        )

        pending_stats = queryset.filter(status='pending').aggregate(
            pending_amount=Sum('amount'),
            pending_count=Count('id')
        )

        failed_count = queryset.filter(status='failed').count()

        return ContributionStats(
            total_amount=str(total_stats['total_amount'] or Decimal('0.00')),
            total_count=total_stats['total_count'] or 0,
            completed_amount=str(completed_stats['completed_amount'] or Decimal('0.00')),
            completed_count=completed_stats['completed_count'] or 0,
            pending_amount=str(pending_stats['pending_amount'] or Decimal('0.00')),
            pending_count=pending_stats['pending_count'] or 0,
            failed_count=failed_count
        )

    @strawberry.field
    def dashboard_stats(self, info) -> DashboardStats:
        """
        Get dashboard statistics (today, this week, this month, total).
        Requires staff role.

        Returns:
            DashboardStats with time-based aggregations
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        # Today's stats
        today_stats = Contribution.objects.filter(
            transaction_date__gte=today_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # This week's stats
        week_stats = Contribution.objects.filter(
            transaction_date__gte=week_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # This month's stats
        month_stats = Contribution.objects.filter(
            transaction_date__gte=month_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # Total stats
        total_stats = Contribution.objects.filter(
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # Member stats
        total_members = Member.objects.filter(is_deleted=False).count()
        active_members = Member.objects.filter(is_active=True, is_deleted=False).count()

        return DashboardStats(
            today_total=str(today_stats['amount'] or Decimal('0.00')),
            today_count=today_stats['count'] or 0,
            week_total=str(week_stats['amount'] or Decimal('0.00')),
            week_count=week_stats['count'] or 0,
            month_total=str(month_stats['amount'] or Decimal('0.00')),
            month_count=month_stats['count'] or 0,
            total_amount=str(total_stats['amount'] or Decimal('0.00')),
            total_count=total_stats['count'] or 0,
            total_members=total_members,
            active_members=active_members
        )

    @strawberry.field
    def members_list(
        self,
        info,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[MemberType]:
        """
        Get list of members.
        Requires staff role.

        Args:
            search: Search by name or phone
            is_active: Filter by active status
            limit: Number of results
            offset: Offset for pagination

        Returns:
            List of members
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        queryset = Member.objects.filter(is_deleted=False)

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(member_number__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        queryset = queryset.order_by('-created_at')[offset:offset + limit]

        return list(queryset)
