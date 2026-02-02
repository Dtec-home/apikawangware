"""
GraphQL Mutations for Manual Contributions
Following SRP: Only responsible for GraphQL mutation definitions
"""

import strawberry
from typing import Optional
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

from .types import ContributionResponse, MemberLookupResponse
from contributions.manual_contribution_service import ManualContributionService


@strawberry.type
class ManualContributionMutations:
    """Manual contribution entry mutations"""

    @strawberry.mutation
    def create_manual_contribution(
        self,
        info,
        phone_number: str,
        amount: str,
        category_id: strawberry.ID,
        entry_type: str = 'manual',
        receipt_number: Optional[str] = None,
        transaction_date: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ContributionResponse:
        """
        Create a manual contribution entry.
        Requires admin authentication.

        Args:
            phone_number: Member's phone number
            amount: Contribution amount (as string)
            category_id: ID of contribution category
            entry_type: Type of entry ('manual', 'cash', 'envelope')
            receipt_number: Optional receipt number
            transaction_date: Optional transaction date (ISO format)
            notes: Optional notes

        Returns:
            ContributionResponse with contribution data
        """
        # Check authentication
        user = info.context.request.user
        if not user.is_authenticated:
            return ContributionResponse(
                success=False,
                message="Authentication required"
            )

        # Check if user is staff/admin
        if not user.is_staff:
            return ContributionResponse(
                success=False,
                message="Admin access required"
            )

        # Parse amount
        try:
            amount_decimal = Decimal(amount)
        except (ValueError, TypeError):
            return ContributionResponse(
                success=False,
                message="Invalid amount format"
            )

        # Parse transaction date if provided
        parsed_date = None
        if transaction_date:
            try:
                parsed_date = datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return ContributionResponse(
                    success=False,
                    message="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )

        # Create manual contribution
        service = ManualContributionService()
        result = service.create_manual_contribution(
            phone_number=phone_number,
            amount=amount_decimal,
            category_id=category_id,
            entry_type=entry_type,
            receipt_number=receipt_number,
            transaction_date=parsed_date,
            notes=notes,
            entered_by_user=user
        )

        if result['success']:
            return ContributionResponse(
                success=True,
                message=result['message'],
                contribution=result['contribution']
            )
        else:
            return ContributionResponse(
                success=False,
                message=result['message']
            )

    @strawberry.mutation
    def lookup_member_by_phone(
        self,
        info,
        phone_number: str
    ) -> 'MemberLookupResponse':
        """
        Look up a member by phone number.
        Requires admin authentication.

        Args:
            phone_number: Phone number to search for

        Returns:
            MemberLookupResponse with member data or guest indicator
        """
        # Check authentication
        user = info.context.request.user
        if not user.is_authenticated:
            return MemberLookupResponse(
                success=False,
                message="Authentication required",
                found=False
            )

        # Check if user is staff/admin
        if not user.is_staff:
            return MemberLookupResponse(
                success=False,
                message="Admin access required",
                found=False
            )

        # Lookup member
        service = ManualContributionService()
        result = service.lookup_member_by_phone(phone_number)

        if result['success']:
            if result['found']:
                return MemberLookupResponse(
                    success=True,
                    found=True,
                    member=result['member'],
                    is_guest=result['is_guest'],
                    message=f"Member found: {result['member'].full_name}"
                )
            else:
                return MemberLookupResponse(
                    success=True,
                    found=False,
                    message=result['message'],
                    phone_number=result['phone_number']
                )
        else:
            return MemberLookupResponse(
                success=False,
                found=False,
                message=result['message']
            )
