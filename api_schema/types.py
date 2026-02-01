"""
GraphQL Types for Church Funds System
Following DRY: Centralized type definitions
"""

import strawberry
from typing import List, Optional
from datetime import datetime, date, time
from decimal import Decimal

from members.models import Member
from contributions.models import Contribution, ContributionCategory, CategoryAdmin
from mpesa.models import MpesaTransaction
from content.models import Announcement, Devotional, Event, YouTubeVideo


@strawberry.django.type(Member)
class MemberType:
    """GraphQL type for Member model"""
    id: strawberry.ID
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[str]
    member_number: str
    is_active: bool
    created_at: datetime

    @strawberry.field
    def full_name(self) -> str:
        """Get member's full name"""
        return f"{self.first_name} {self.last_name}"


@strawberry.django.type(ContributionCategory)
class ContributionCategoryType:
    """GraphQL type for ContributionCategory model"""
    id: strawberry.ID
    name: str
    code: str
    description: str
    is_active: bool


@strawberry.django.type(MpesaTransaction)
class MpesaTransactionType:
    """GraphQL type for MpesaTransaction model"""
    id: strawberry.ID
    phone_number: str
    amount: str  # Decimal as string for GraphQL
    status: str
    checkout_request_id: str
    merchant_request_id: str
    mpesa_receipt_number: Optional[str]
    transaction_date: Optional[datetime]
    result_desc: Optional[str]


@strawberry.django.type(Contribution)
class ContributionType:
    """GraphQL type for Contribution model"""
    id: strawberry.ID
    member: MemberType
    category: ContributionCategoryType
    amount: str  # Decimal as string for GraphQL
    status: str
    transaction_date: datetime
    notes: str
    mpesa_transaction: Optional[MpesaTransactionType]

    @strawberry.field
    def is_completed(self) -> bool:
        """Check if contribution is completed"""
        return self.status == 'completed'


@strawberry.type
class ContributionResponse:
    """Response type for contribution mutation"""
    success: bool
    message: str
    contribution: Optional[ContributionType] = None
    checkout_request_id: Optional[str] = None


@strawberry.type
class ErrorType:
    """Generic error type for better error handling"""
    field: Optional[str]
    message: str


# Category Admin Types

@strawberry.type
class AssignedByType:
    """Simplified user type for assigned_by field"""
    id: strawberry.ID
    full_name: str


@strawberry.django.type(CategoryAdmin)
class CategoryAdminType:
    """GraphQL type for CategoryAdmin model"""
    id: strawberry.ID
    member: MemberType
    category: ContributionCategoryType
    is_active: bool
    created_at: datetime

    @strawberry.field
    def assigned_by(self) -> Optional[AssignedByType]:
        """Get the user who assigned this admin role"""
        if self.assigned_by_id:
            from django.contrib.auth.models import User
            user = User.objects.filter(id=self.assigned_by_id).first()
            if user:
                return AssignedByType(
                    id=strawberry.ID(str(user.id)),
                    full_name=f"{user.first_name} {user.last_name}".strip() or user.username
                )
        return None

    @strawberry.field
    def assigned_at(self) -> datetime:
        """Alias for created_at to match frontend expectations"""
        return self.created_at


@strawberry.type
class CategoryAdminRoleType:
    """Simplified category admin role for member's own view"""
    id: strawberry.ID
    category: ContributionCategoryType
    assigned_at: datetime
    is_active: bool


@strawberry.type
class CategoryAdminResponse:
    """Response type for category admin mutations"""
    success: bool
    message: str
    category_admin: Optional[CategoryAdminType] = None


@strawberry.type
class UserRoleInfo:
    """Information about user's role and permissions"""
    is_authenticated: bool
    is_staff: bool  # admin, treasurer, or pastor
    is_category_admin: bool
    admin_category_ids: List[str]  # IDs of categories user administers
    admin_categories: List[ContributionCategoryType]  # Full category objects


# Content Management Types

@strawberry.django.type(Announcement)
class AnnouncementType:
    """GraphQL type for Announcement model"""
    id: strawberry.ID
    title: str
    content: str
    publish_date: datetime
    is_active: bool
    priority: int
    created_at: datetime


@strawberry.django.type(Devotional)
class DevotionalType:
    """GraphQL type for Devotional model"""
    id: strawberry.ID
    title: str
    content: str
    author: str
    scripture_reference: str
    publish_date: datetime
    is_published: bool
    is_featured: bool
    featured_image_url: str
    created_at: datetime


@strawberry.django.type(Event)
class EventType:
    """GraphQL type for Event model"""
    id: strawberry.ID
    title: str
    description: str
    event_date: date
    event_time: time
    location: str
    registration_link: str
    is_active: bool
    featured_image_url: str
    created_at: datetime


@strawberry.django.type(YouTubeVideo)
class YouTubeVideoType:
    """GraphQL type for YouTubeVideo model"""
    id: strawberry.ID
    title: str
    video_id: str
    description: str
    category: str
    publish_date: datetime
    is_featured: bool
    created_at: datetime

    # YouTube API sync fields
    source: str
    channel_id: str
    playlist_id: str
    last_synced_at: Optional[datetime]
    youtube_published_at: Optional[datetime]
    duration: Optional[int]
    view_count: Optional[int]
    like_count: Optional[int]

    @strawberry.field
    def embed_url(self) -> str:
        """Get YouTube embed URL"""
        return f"https://www.youtube.com/embed/{self.video_id}"

    @strawberry.field
    def watch_url(self) -> str:
        """Get YouTube watch URL"""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @strawberry.field
    def thumbnail_url(self) -> str:
        """Get YouTube thumbnail URL"""
        return f"https://img.youtube.com/vi/{self.video_id}/maxresdefault.jpg"