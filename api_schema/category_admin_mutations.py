"""
Category Admin Mutations
Mutations for managing category-specific admin roles
"""

import strawberry
from typing import Optional

from .types import CategoryAdminResponse, CategoryAdminType
from contributions.models import ContributionCategory, CategoryAdmin
from members.models import Member
from members.roles import PermissionChecker


@strawberry.type
class CategoryAdminMutations:
    """Category Admin related mutations"""

    @strawberry.mutation
    def assign_category_admin(
        self,
        info,
        member_id: strawberry.ID,
        category_id: strawberry.ID
    ) -> CategoryAdminResponse:
        """
        Assign a member as admin for a specific category.
        Requires staff role.

        Args:
            member_id: ID of member to assign
            category_id: ID of category to assign admin role for

        Returns:
            CategoryAdminResponse with success status and created admin
        """
        try:
            # Check permissions
            user = info.context.request.user
            if not user.is_authenticated:
                return CategoryAdminResponse(
                    success=False,
                    message="Authentication required"
                )
            if not PermissionChecker.is_staff(user):
                return CategoryAdminResponse(
                    success=False,
                    message="Requires staff privileges"
                )

            # Validate member exists
            try:
                member = Member.objects.get(
                    id=member_id,
                    is_active=True,
                    is_deleted=False
                )
            except Member.DoesNotExist:
                return CategoryAdminResponse(
                    success=False,
                    message="Member not found or inactive"
                )

            # Validate category exists
            try:
                category = ContributionCategory.objects.get(
                    id=category_id,
                    is_active=True,
                    is_deleted=False
                )
            except ContributionCategory.DoesNotExist:
                return CategoryAdminResponse(
                    success=False,
                    message="Category not found or inactive"
                )

            # Check if already an admin
            existing = CategoryAdmin.objects.filter(
                member=member,
                category=category
            ).first()

            if existing:
                if existing.is_active:
                    return CategoryAdminResponse(
                        success=False,
                        message=f"{member.full_name} is already an admin for {category.name}"
                    )
                else:
                    # Reactivate existing inactive assignment
                    existing.is_active = True
                    existing.assigned_by = user
                    existing.save()
                    return CategoryAdminResponse(
                        success=True,
                        message=f"{member.full_name} has been reassigned as admin for {category.name}",
                        category_admin=existing
                    )

            # Create new category admin
            category_admin = CategoryAdmin.objects.create(
                member=member,
                category=category,
                assigned_by=user,
                is_active=True
            )

            return CategoryAdminResponse(
                success=True,
                message=f"{member.full_name} has been assigned as admin for {category.name}",
                category_admin=category_admin
            )

        except Exception as e:
            return CategoryAdminResponse(
                success=False,
                message=f"Error assigning category admin: {str(e)}"
            )

    @strawberry.mutation
    def remove_category_admin(
        self,
        info,
        category_admin_id: strawberry.ID
    ) -> CategoryAdminResponse:
        """
        Remove a category admin role (soft delete by setting is_active=False).
        Requires staff role.

        Args:
            category_admin_id: ID of the category admin assignment to remove

        Returns:
            CategoryAdminResponse with success status
        """
        try:
            # Check permissions
            user = info.context.request.user
            if not user.is_authenticated:
                return CategoryAdminResponse(
                    success=False,
                    message="Authentication required"
                )
            if not PermissionChecker.is_staff(user):
                return CategoryAdminResponse(
                    success=False,
                    message="Requires staff privileges"
                )

            # Find the category admin assignment
            try:
                category_admin = CategoryAdmin.objects.select_related(
                    'member', 'category'
                ).get(id=category_admin_id)
            except CategoryAdmin.DoesNotExist:
                return CategoryAdminResponse(
                    success=False,
                    message="Category admin assignment not found"
                )

            if not category_admin.is_active:
                return CategoryAdminResponse(
                    success=False,
                    message="Category admin assignment is already inactive"
                )

            # Deactivate the assignment
            member_name = category_admin.member.full_name
            category_name = category_admin.category.name
            category_admin.is_active = False
            category_admin.save()

            return CategoryAdminResponse(
                success=True,
                message=f"{member_name} has been removed as admin for {category_name}"
            )

        except Exception as e:
            return CategoryAdminResponse(
                success=False,
                message=f"Error removing category admin: {str(e)}"
            )
