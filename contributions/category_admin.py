"""
Category Admin Model
Allows members to be assigned as administrators for specific contribution categories.
"""

from django.db import models
from django.contrib.auth.models import User
from core.models import TimeStampedModel


class CategoryAdmin(TimeStampedModel):
    """
    Category-specific admin assignment.
    Allows assigning members as administrators for specific contribution categories.
    """

    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='category_admin_roles',
        help_text="Member assigned as category admin"
    )
    category = models.ForeignKey(
        'contributions.ContributionCategory',
        on_delete=models.CASCADE,
        related_name='category_admins',
        help_text="Category this admin manages"
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_category_admins',
        help_text="User who assigned this admin role"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this admin assignment is active"
    )

    class Meta:
        unique_together = ['member', 'category']
        indexes = [
            models.Index(fields=['member', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_active', '-created_at']),
        ]
        verbose_name = 'Category Admin'
        verbose_name_plural = 'Category Admins'

    def __str__(self):
        return f"{self.member.full_name} - {self.category.name} Admin"

    @classmethod
    def is_category_admin(cls, member_id: int, category_id: int) -> bool:
        """Check if a member is an admin for a specific category"""
        return cls.objects.filter(
            member_id=member_id,
            category_id=category_id,
            is_active=True
        ).exists()

    @classmethod
    def get_admin_categories(cls, member_id: int):
        """Get all categories where member is an admin"""
        return cls.objects.filter(
            member_id=member_id,
            is_active=True
        ).select_related('category')

    @classmethod
    def get_category_admins(cls, category_id: int):
        """Get all admins for a specific category"""
        return cls.objects.filter(
            category_id=category_id,
            is_active=True
        ).select_related('member', 'assigned_by')
