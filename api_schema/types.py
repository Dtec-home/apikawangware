"""
GraphQL Types for Church Funds System
Following DRY: Centralized type definitions
"""

import strawberry
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from members.models import Member
from contributions.models import Contribution, ContributionCategory
from mpesa.models import MpesaTransaction


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