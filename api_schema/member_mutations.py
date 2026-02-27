"""
Member CRUD Mutations
Mutations for managing members (edit, deactivate, delete)
"""

import strawberry
from typing import Optional

from .types import MemberType
from members.models import Member
from members.roles import PermissionChecker


@strawberry.type
class MemberResponse:
    """Response type for member mutations"""
    success: bool
    message: str
    member: Optional[MemberType] = None


@strawberry.type
class MemberMutations:
    """Member management mutations"""

    @strawberry.mutation
    def update_member(
        self,
        info,
        member_id: strawberry.ID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> MemberResponse:
        """
        Update member details.
        Requires staff role (admin, treasurer, or pastor).
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return MemberResponse(success=False, message="Authentication required")
        if not PermissionChecker.can_manage_members(user):
            return MemberResponse(success=False, message="Requires admin or pastor role")

        try:
            member = Member.objects.get(id=member_id, is_deleted=False)
        except Member.DoesNotExist:
            return MemberResponse(success=False, message="Member not found")

        try:
            if first_name is not None:
                first_name = first_name.strip()
                if not first_name:
                    return MemberResponse(success=False, message="First name cannot be empty")
                if len(first_name) > 100:
                    return MemberResponse(success=False, message="First name too long (max 100)")
                member.first_name = first_name

            if last_name is not None:
                last_name = last_name.strip()
                if not last_name:
                    return MemberResponse(success=False, message="Last name cannot be empty")
                if len(last_name) > 100:
                    return MemberResponse(success=False, message="Last name too long (max 100)")
                member.last_name = last_name

            if email is not None:
                email = email.strip()
                if email and '@' not in email:
                    return MemberResponse(success=False, message="Invalid email format")
                member.email = email or None

            if phone_number is not None:
                from members.utils import normalize_phone_number
                try:
                    normalized = normalize_phone_number(phone_number)
                except ValueError as e:
                    return MemberResponse(success=False, message=str(e))

                # Check for duplicate phone
                if Member.objects.filter(
                    phone_number=normalized, is_deleted=False
                ).exclude(id=member.id).exists():
                    return MemberResponse(
                        success=False,
                        message=f"Phone number {normalized} is already registered to another member"
                    )
                member.phone_number = normalized

            member.save()

            # Also update linked User if exists
            if member.user:
                if first_name is not None:
                    member.user.first_name = member.first_name
                if last_name is not None:
                    member.user.last_name = member.last_name
                if email is not None:
                    member.user.email = member.email or ''
                member.user.save()

            return MemberResponse(
                success=True,
                message=f"Member '{member.full_name}' updated successfully",
                member=member
            )
        except Exception as e:
            return MemberResponse(success=False, message=f"Error updating member: {str(e)}")

    @strawberry.mutation
    def toggle_member_status(
        self,
        info,
        member_id: strawberry.ID,
    ) -> MemberResponse:
        """
        Activate or deactivate a member.
        Requires admin or pastor role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return MemberResponse(success=False, message="Authentication required")
        if not PermissionChecker.can_manage_members(user):
            return MemberResponse(success=False, message="Requires admin or pastor role")

        try:
            member = Member.objects.get(id=member_id, is_deleted=False)
        except Member.DoesNotExist:
            return MemberResponse(success=False, message="Member not found")

        try:
            member.is_active = not member.is_active
            member.save(update_fields=['is_active', 'updated_at'])

            status = "activated" if member.is_active else "deactivated"
            return MemberResponse(
                success=True,
                message=f"Member '{member.full_name}' {status}",
                member=member
            )
        except Exception as e:
            return MemberResponse(success=False, message=f"Error toggling member status: {str(e)}")

    @strawberry.mutation
    def delete_member(
        self,
        info,
        member_id: strawberry.ID,
    ) -> MemberResponse:
        """
        Soft-delete a member.
        Requires admin role.
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return MemberResponse(success=False, message="Authentication required")
        if not PermissionChecker.is_admin(user):
            return MemberResponse(success=False, message="Requires admin role")

        try:
            member = Member.objects.get(id=member_id, is_deleted=False)
        except Member.DoesNotExist:
            return MemberResponse(success=False, message="Member not found")

        # Check if member has contributions
        contribution_count = member.contributions.count()
        if contribution_count > 0:
            return MemberResponse(
                success=False,
                message=f"Cannot delete member '{member.full_name}' - has {contribution_count} contribution(s). Deactivate instead."
            )

        try:
            member_name = member.full_name
            member.is_deleted = True
            member.is_active = False
            member.save(update_fields=['is_deleted', 'is_active', 'updated_at'])
            return MemberResponse(
                success=True,
                message=f"Member '{member_name}' deleted successfully"
            )
        except Exception as e:
            return MemberResponse(success=False, message=f"Error deleting member: {str(e)}")
