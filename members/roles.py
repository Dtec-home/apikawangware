"""
Role-Based Access Control
Following SOLID principles:
- SRP: Each class has single responsibility
- OCP: Open for extension (can add new roles)
"""

from django.db import models
from django.contrib.auth.models import User
from enum import Enum


class RoleType(str, Enum):
    """Enum for user roles"""
    ADMIN = "admin"
    TREASURER = "treasurer"
    PASTOR = "pastor"
    MEMBER = "member"


class UserRole(models.Model):
    """
    User role assignment.
    Following SRP: Only responsible for storing user-role relationships.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='roles'
    )
    role = models.CharField(
        max_length=20,
        choices=[(role.value, role.value.title()) for role in RoleType],
        help_text="User's role in the system"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this role assignment is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'role']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['role', 'is_active']),
        ]
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class PermissionChecker:
    """
    Base permission checker.
    Following OCP: Open for extension, closed for modification.
    """

    @staticmethod
    def has_role(user: User, role: RoleType) -> bool:
        """Check if user has a specific role"""
        if not user or not user.is_authenticated:
            return False

        return UserRole.objects.filter(
            user=user,
            role=role.value,
            is_active=True
        ).exists()

    @staticmethod
    def has_any_role(user: User, roles: list[RoleType]) -> bool:
        """Check if user has any of the specified roles"""
        if not user or not user.is_authenticated:
            return False

        return UserRole.objects.filter(
            user=user,
            role__in=[role.value for role in roles],
            is_active=True
        ).exists()

    @staticmethod
    def is_admin(user: User) -> bool:
        """Check if user is an admin"""
        return PermissionChecker.has_role(user, RoleType.ADMIN)

    @staticmethod
    def is_treasurer(user: User) -> bool:
        """Check if user is a treasurer"""
        return PermissionChecker.has_role(user, RoleType.TREASURER)

    @staticmethod
    def is_pastor(user: User) -> bool:
        """Check if user is a pastor"""
        return PermissionChecker.has_role(user, RoleType.PASTOR)

    @staticmethod
    def is_staff(user: User) -> bool:
        """Check if user is admin, treasurer, or pastor"""
        return PermissionChecker.has_any_role(user, [
            RoleType.ADMIN,
            RoleType.TREASURER,
            RoleType.PASTOR
        ])

    @staticmethod
    def can_view_all_contributions(user: User) -> bool:
        """Check if user can view all contributions"""
        return PermissionChecker.is_staff(user)

    @staticmethod
    def can_manage_members(user: User) -> bool:
        """Check if user can manage members"""
        return PermissionChecker.has_any_role(user, [
            RoleType.ADMIN,
            RoleType.PASTOR
        ])

    @staticmethod
    def can_generate_reports(user: User) -> bool:
        """Check if user can generate reports"""
        return PermissionChecker.is_staff(user)


from functools import wraps


def require_authentication(func):
    """Decorator to require authentication"""
    @wraps(func)
    def wrapper(self, info, **kwargs):
        if not info.context.request.user.is_authenticated:
            raise PermissionError("Authentication required")
        return func(self, info, **kwargs)
    return wrapper


def require_role(role: RoleType):
    """Decorator to require specific role"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, info, **kwargs):
            user = info.context.request.user
            if not user.is_authenticated:
                raise PermissionError("Authentication required")
            if not PermissionChecker.has_role(user, role):
                raise PermissionError(f"Requires {role.value} role")
            return func(self, info, **kwargs)
        return wrapper
    return decorator


def require_staff(func):
    """Decorator to require staff role (admin, treasurer, or pastor)"""
    @wraps(func)
    def wrapper(self, info, **kwargs):
        user = info.context.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required")
        if not PermissionChecker.is_staff(user):
            raise PermissionError("Requires staff privileges")
        return func(self, info, **kwargs)
    return wrapper
