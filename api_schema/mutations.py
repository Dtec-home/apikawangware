"""
GraphQL Mutations
Following SRP: Each mutation has single responsibility
Following DIP: Mutations depend on service abstractions
"""

import strawberry
from typing import Optional
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from .types import ContributionResponse
from .auth_mutations import AuthMutations, AuthResponse
from .report_mutations import ReportMutations, ReportResponse
from members.models import Member
from members.utils import normalize_phone_number
from contributions.models import Contribution, ContributionCategory
from mpesa.services import MpesaSTKService


@strawberry.type
class Mutation:
    """Root Mutation type - combines all mutations"""

    # Authentication mutations
    request_otp: AuthResponse = strawberry.field(resolver=AuthMutations.request_otp)
    verify_otp: AuthResponse = strawberry.field(resolver=AuthMutations.verify_otp)
    refresh_token: AuthResponse = strawberry.field(resolver=AuthMutations.refresh_token)
    logout: AuthResponse = strawberry.field(resolver=AuthMutations.logout)

    # Report mutations
    generate_contribution_report: ReportResponse = strawberry.field(resolver=ReportMutations.generate_contribution_report)

    @strawberry.mutation
    def initiate_contribution(
        self,
        phone_number: str,
        amount: str,  # Decimal as string from GraphQL
        category_id: strawberry.ID
    ) -> ContributionResponse:
        """
        Initiate a contribution via M-Pesa STK Push.
        Following Sprint 1 spec: initiate_contribution mutation.
        
        Flow:
        1. Validate member exists
        2. Validate category exists and is active
        3. Initiate M-Pesa STK Push
        4. Create contribution record
        5. Return response with checkout ID
        
        Args:
            phone_number: Member's M-Pesa phone number (various formats accepted)
            amount: Contribution amount in KES
            category_id: ID of contribution category

        Returns:
            ContributionResponse with success status and details
        """
        try:
            # Normalize phone number
            try:
                normalized_phone = normalize_phone_number(phone_number)
            except ValueError as e:
                return ContributionResponse(
                    success=False,
                    message=str(e)
                )

            # Validate and convert amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal < Decimal('1.00'):
                    return ContributionResponse(
                        success=False,
                        message="Amount must be at least KES 1.00"
                    )
            except (ValueError, TypeError):
                return ContributionResponse(
                    success=False,
                    message="Invalid amount format"
                )

            # Find or create member by phone number
            member, created = Member.objects.get_or_create(
                phone_number=normalized_phone,
                defaults={
                    'first_name': 'Guest',
                    'last_name': 'Member',
                    'is_active': True
                }
            )

            if not member.is_active:
                return ContributionResponse(
                    success=False,
                    message="Member account is inactive"
                )

            # Validate category
            try:
                category = ContributionCategory.objects.get(
                    id=category_id,
                    is_active=True,
                    is_deleted=False
                )
            except ContributionCategory.DoesNotExist:
                return ContributionResponse(
                    success=False,
                    message="Invalid or inactive contribution category"
                )

            # Initiate M-Pesa STK Push
            stk_service = MpesaSTKService()
            transaction_desc = f"{category.name} - {member.full_name}"

            result = stk_service.initiate_stk_push(
                phone_number=normalized_phone,
                amount=amount_decimal,
                account_reference=category.code,
                transaction_desc=transaction_desc
            )

            if not result['success']:
                return ContributionResponse(
                    success=False,
                    message=result['message']
                )

            # Create contribution record
            mpesa_transaction = result['transaction']
            contribution = Contribution.objects.create(
                member=member,
                category=category,
                mpesa_transaction=mpesa_transaction,
                amount=amount_decimal,
                status='pending',
                transaction_date=timezone.now(),
                notes=f"Initiated via STK Push - {result['checkout_request_id']}"
            )

            return ContributionResponse(
                success=True,
                message=result['message'],
                contribution=contribution,
                checkout_request_id=result['checkout_request_id']
            )

        except ValidationError as e:
            return ContributionResponse(
                success=False,
                message=str(e)
            )
        except Exception as e:
            return ContributionResponse(
                success=False,
                message=f"Error processing contribution: {str(e)}"
            )