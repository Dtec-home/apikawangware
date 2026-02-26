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

from .types import (
    ContributionType,
    MemberType,
    ContributionCategoryType,
    CategoryAdminType,
    CategoryAdminRoleType,
    UserRoleInfo,
    C2BTransactionType,
)
from contributions.models import Contribution, ContributionCategory, CategoryAdmin
from members.models import Member
from members.roles import PermissionChecker
from mpesa.models import C2BTransaction


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
class C2BTransactionStats:
    """Statistics for C2B transactions"""
    total_amount: str
    total_count: int
    processed_count: int
    unmatched_count: int
    failed_count: int


@strawberry.type
class PaginatedC2BTransactions:
    """Paginated C2B transaction results"""
    items: List[C2BTransactionType]
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

        # Check if user is full staff or category admin
        is_full_staff = PermissionChecker.is_staff(user)
        is_category_admin = False
        allowed_category_ids = []

        if not is_full_staff:
            # Check if user is a category admin
            if hasattr(user, 'member') and user.member:
                admin_categories = CategoryAdmin.objects.filter(
                    member=user.member,
                    is_active=True
                ).values_list('category_id', flat=True)
                allowed_category_ids = list(admin_categories)
                is_category_admin = len(allowed_category_ids) > 0

        if not is_full_staff and not is_category_admin:
            raise PermissionError("Requires staff or category admin privileges")

        # Build queryset
        queryset = Contribution.objects.select_related(
            'member',
            'category',
            'mpesa_transaction'
        ).all()

        # Filter by category for category admins
        if is_category_admin and not is_full_staff:
            queryset = queryset.filter(category_id__in=allowed_category_ids)

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

        # Check if user is full staff or category admin
        is_full_staff = PermissionChecker.is_staff(user)
        is_category_admin = False
        allowed_category_ids = []

        if not is_full_staff:
            # Check if user is a category admin
            if hasattr(user, 'member') and user.member:
                admin_categories = CategoryAdmin.objects.filter(
                    member=user.member,
                    is_active=True
                ).values_list('category_id', flat=True)
                allowed_category_ids = list(admin_categories)
                is_category_admin = len(allowed_category_ids) > 0

        if not is_full_staff and not is_category_admin:
            raise PermissionError("Requires staff or category admin privileges")

        queryset = Contribution.objects.all()

        # Filter by category for category admins
        if is_category_admin and not is_full_staff:
            queryset = queryset.filter(category_id__in=allowed_category_ids)

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

        # Check if user is full staff or category admin
        is_full_staff = PermissionChecker.is_staff(user)
        is_category_admin = False
        allowed_category_ids = []

        if not is_full_staff:
            # Check if user is a category admin
            if hasattr(user, 'member') and user.member:
                admin_categories = CategoryAdmin.objects.filter(
                    member=user.member,
                    is_active=True
                ).values_list('category_id', flat=True)
                allowed_category_ids = list(admin_categories)
                is_category_admin = len(allowed_category_ids) > 0

        if not is_full_staff and not is_category_admin:
            raise PermissionError("Requires staff or category admin privileges")

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        # Base queryset for stats
        base_queryset = Contribution.objects.all()
        if is_category_admin and not is_full_staff:
            base_queryset = base_queryset.filter(category_id__in=allowed_category_ids)

        # Today's stats
        today_stats = base_queryset.filter(
            transaction_date__gte=today_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # This week's stats
        week_stats = base_queryset.filter(
            transaction_date__gte=week_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # This month's stats
        month_stats = base_queryset.filter(
            transaction_date__gte=month_start,
            status='completed'
        ).aggregate(
            amount=Sum('amount'),
            count=Count('id')
        )

        # Total stats
        total_stats = base_queryset.filter(
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

    @strawberry.field
    def category_admins(
        self,
        info,
        category_id: Optional[strawberry.ID] = None
    ) -> List[CategoryAdminType]:
        """
        Get all category admins, optionally filtered by category.
        Requires staff role.

        Args:
            category_id: Optional category ID to filter by

        Returns:
            List of category admins
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        queryset = CategoryAdmin.objects.filter(
            is_active=True
        ).select_related('member', 'category', 'assigned_by')

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return list(queryset.order_by('category__name', 'member__last_name'))

    @strawberry.field
    def my_category_admin_roles(
        self,
        info,
        member_id: strawberry.ID
    ) -> List[CategoryAdminRoleType]:
        """
        Get category admin roles for a specific member.
        Authenticated users can only view their own roles.

        Args:
            member_id: Member ID to get roles for

        Returns:
            List of category admin roles
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")

        # Get the member
        try:
            member = Member.objects.get(id=member_id, is_deleted=False)
        except Member.DoesNotExist:
            return []

        # Check if user is requesting their own roles or is staff
        is_own_roles = hasattr(user, 'member') and user.member and user.member.id == member.id
        is_staff = PermissionChecker.is_staff(user)

        if not is_own_roles and not is_staff:
            raise PermissionError("Cannot view other members' category admin roles")

        roles = CategoryAdmin.objects.filter(
            member=member,
            is_active=True
        ).select_related('category')

        return [
            CategoryAdminRoleType(
                id=strawberry.ID(str(role.id)),
                category=role.category,
                assigned_at=role.created_at,
                is_active=role.is_active
            )
            for role in roles
        ]

    @strawberry.field
    def is_category_admin(
        self,
        info,
        category_id: strawberry.ID,
        member_id: strawberry.ID
    ) -> bool:
        """
        Check if a member is admin for a specific category.
        Requires authentication.

        Args:
            category_id: Category ID to check
            member_id: Member ID to check

        Returns:
            True if member is admin for the category
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")

        return CategoryAdmin.is_category_admin(
            member_id=int(member_id),
            category_id=int(category_id)
        )

    @strawberry.field
    def c2b_transactions(
        self,
        info,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        pagination: Optional[PaginationInput] = None
    ) -> PaginatedC2BTransactions:
        """
        Get C2B transactions with optional filters and pagination.
        Requires staff role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        queryset = C2BTransaction.objects.all()

        if status:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        total = queryset.count()
        queryset = queryset.order_by('-created_at')

        if pagination:
            limit = pagination.limit
            offset = pagination.offset
            queryset = queryset[offset:offset + limit]
            has_more = (offset + limit) < total
        else:
            has_more = False

        return PaginatedC2BTransactions(
            items=list(queryset),
            total=total,
            has_more=has_more
        )

    @strawberry.field
    def c2b_transaction_stats(
        self,
        info,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> C2BTransactionStats:
        """
        Get aggregate statistics for C2B transactions.
        Requires staff role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")

        queryset = C2BTransaction.objects.all()

        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        total_stats = queryset.aggregate(
            total_amount=Sum('trans_amount'),
            total_count=Count('id')
        )
        processed_count = queryset.filter(status='processed').count()
        unmatched_count = queryset.filter(status='unmatched').count()
        failed_count = queryset.filter(status='failed').count()

        return C2BTransactionStats(
            total_amount=str(total_stats['total_amount'] or Decimal('0.00')),
            total_count=total_stats['total_count'] or 0,
            processed_count=processed_count,
            unmatched_count=unmatched_count,
            failed_count=failed_count
        )

    @strawberry.field
    def current_user_role(self, info) -> UserRoleInfo:
        """
        Get current user's role information and permissions.
        Used by frontend to determine navigation and access.

        Returns:
            UserRoleInfo with role flags and admin categories
        """
        user = info.context.request.user

        if not user.is_authenticated:
            return UserRoleInfo(
                is_authenticated=False,
                is_staff=False,
                is_category_admin=False,
                admin_category_ids=[],
                admin_categories=[]
            )

        is_staff = PermissionChecker.is_staff(user)

        # Get category admin info
        admin_categories = []
        admin_category_ids = []

        # Try to get member associated with user
        member = None
        if hasattr(user, 'member') and user.member:
            member = user.member
        else:
            # Try to find member by looking at the phone number in member table
            # that might be linked via other means
            try:
                member = Member.objects.filter(
                    user=user,
                    is_deleted=False
                ).first()
            except Exception:
                pass

        if member:
            category_admins = CategoryAdmin.objects.filter(
                member=member,
                is_active=True
            ).select_related('category')

            for ca in category_admins:
                admin_category_ids.append(str(ca.category.id))
                admin_categories.append(ca.category)

        is_category_admin = len(admin_category_ids) > 0

        return UserRoleInfo(
            is_authenticated=True,
            is_staff=is_staff,
            is_category_admin=is_category_admin,
            admin_category_ids=admin_category_ids,
            admin_categories=admin_categories
        )
