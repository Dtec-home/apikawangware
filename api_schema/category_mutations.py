"""
Category CRUD Mutations
Mutations for managing contribution categories
"""

import strawberry
from typing import Optional

from .types import ContributionCategoryType
from contributions.models import ContributionCategory
from members.roles import PermissionChecker


@strawberry.type
class CategoryResponse:
    """Response type for category mutations"""
    success: bool
    message: str
    category: Optional[ContributionCategoryType] = None


@strawberry.type
class CategoryMutations:
    """Contribution category management mutations"""

    @strawberry.mutation
    def create_category(
        self,
        info,
        name: str,
        code: str,
        description: str = '',
    ) -> CategoryResponse:
        """
        Create a new contribution category.
        Requires admin role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return CategoryResponse(success=False, message="Authentication required")
        if not PermissionChecker.is_admin(user):
            return CategoryResponse(success=False, message="Requires admin role")

        # Validate inputs
        name = name.strip()
        code = code.strip().upper()

        if not name:
            return CategoryResponse(success=False, message="Category name is required")
        if not code:
            return CategoryResponse(success=False, message="Category code is required")
        if len(code) > 20:
            return CategoryResponse(success=False, message="Category code must be 20 characters or less")

        # Check for duplicates
        if ContributionCategory.objects.filter(name__iexact=name, is_deleted=False).exists():
            return CategoryResponse(success=False, message=f"Category '{name}' already exists")
        if ContributionCategory.objects.filter(code__iexact=code, is_deleted=False).exists():
            return CategoryResponse(success=False, message=f"Category code '{code}' already exists")

        try:
            category = ContributionCategory.objects.create(
                name=name,
                code=code,
                description=description.strip(),
                is_active=True,
            )
            return CategoryResponse(
                success=True,
                message=f"Category '{name}' created successfully",
                category=category
            )
        except Exception as e:
            return CategoryResponse(success=False, message=f"Error creating category: {str(e)}")

    @strawberry.mutation
    def update_category(
        self,
        info,
        category_id: strawberry.ID,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> CategoryResponse:
        """
        Update an existing contribution category.
        Requires admin role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return CategoryResponse(success=False, message="Authentication required")
        if not PermissionChecker.is_admin(user):
            return CategoryResponse(success=False, message="Requires admin role")

        try:
            category = ContributionCategory.objects.get(id=category_id, is_deleted=False)
        except ContributionCategory.DoesNotExist:
            return CategoryResponse(success=False, message="Category not found")

        try:
            if name is not None:
                name = name.strip()
                if not name:
                    return CategoryResponse(success=False, message="Category name cannot be empty")
                if ContributionCategory.objects.filter(
                    name__iexact=name, is_deleted=False
                ).exclude(id=category.id).exists():
                    return CategoryResponse(success=False, message=f"Category '{name}' already exists")
                category.name = name

            if code is not None:
                code = code.strip().upper()
                if not code:
                    return CategoryResponse(success=False, message="Category code cannot be empty")
                if ContributionCategory.objects.filter(
                    code__iexact=code, is_deleted=False
                ).exclude(id=category.id).exists():
                    return CategoryResponse(success=False, message=f"Category code '{code}' already exists")
                category.code = code

            if description is not None:
                category.description = description.strip()

            if is_active is not None:
                category.is_active = is_active

            category.save()
            return CategoryResponse(
                success=True,
                message=f"Category '{category.name}' updated successfully",
                category=category
            )
        except Exception as e:
            return CategoryResponse(success=False, message=f"Error updating category: {str(e)}")

    @strawberry.mutation
    def delete_category(
        self,
        info,
        category_id: strawberry.ID,
    ) -> CategoryResponse:
        """
        Soft-delete a contribution category.
        Requires admin role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return CategoryResponse(success=False, message="Authentication required")
        if not PermissionChecker.is_admin(user):
            return CategoryResponse(success=False, message="Requires admin role")

        try:
            category = ContributionCategory.objects.get(id=category_id, is_deleted=False)
        except ContributionCategory.DoesNotExist:
            return CategoryResponse(success=False, message="Category not found")

        # Check if category has contributions
        contribution_count = category.contributions.count()
        if contribution_count > 0:
            return CategoryResponse(
                success=False,
                message=f"Cannot delete category '{category.name}' - it has {contribution_count} contribution(s). Deactivate it instead."
            )

        try:
            category_name = category.name
            category.is_deleted = True
            category.is_active = False
            category.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            return CategoryResponse(
                success=True,
                message=f"Category '{category_name}' deleted successfully"
            )
        except Exception as e:
            return CategoryResponse(success=False, message=f"Error deleting category: {str(e)}")
