"""
Multi-Category Contribution Service
Handles business logic for contributions spanning multiple categories in a single transaction.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid

from contributions.models import Contribution, ContributionCategory
from mpesa.models import MpesaTransaction
from mpesa.services import MpesaSTKService
from members.models import Member
from members.utils import normalize_phone_number


class MultiContributionService:
    """
    Service for handling multi-category contributions.
    Follows SRP: Only responsible for multi-contribution business logic.
    """

    def __init__(self):
        self.mpesa_service = MpesaSTKService()

    def validate_contributions(
        self,
        contributions: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[str], Optional[List[Dict]]]:
        """
        Validate contribution data.

        Args:
            contributions: List of dicts with 'categoryId' and 'amount'

        Returns:
            Tuple of (is_valid, error_message, validated_data)
        """
        if not contributions or len(contributions) == 0:
            return False, "At least one contribution is required", None

        if len(contributions) > 10:
            return False, "Maximum 10 categories allowed per transaction", None

        validated = []
        seen_categories = set()
        total = Decimal('0.00')

        for idx, contrib in enumerate(contributions):
            # Validate category_id
            category_id = contrib.get('categoryId') or contrib.get('category_id')
            if not category_id:
                return False, f"Category ID missing for contribution {idx + 1}", None

            # Check for duplicates
            if category_id in seen_categories:
                return False, f"Duplicate category detected", None
            seen_categories.add(category_id)

            # Validate category exists and is active
            try:
                category = ContributionCategory.objects.get(
                    id=category_id,
                    is_active=True,
                    is_deleted=False
                )
            except ContributionCategory.DoesNotExist:
                return False, f"Invalid or inactive category: {category_id}", None

            # Validate amount
            try:
                amount = Decimal(str(contrib.get('amount', '0')))
                if amount < Decimal('1.00'):
                    return False, f"Amount for {category.name} must be at least KES 1.00", None
            except (ValueError, TypeError):
                return False, f"Invalid amount format for {category.name}", None

            total += amount
            validated.append({
                'category': category,
                'amount': amount
            })

        return True, None, validated

    def calculate_total(self, validated_contributions: List[Dict]) -> Decimal:
        """Calculate total amount from validated contributions."""
        return sum(c['amount'] for c in validated_contributions)

    def create_multi_contribution(
        self,
        phone_number: str,
        contributions: List[Dict[str, Any]],
        member: Optional[Member] = None
    ) -> Dict[str, Any]:
        """
        Create multiple contribution records and initiate M-Pesa payment.

        Args:
            phone_number: Member's phone number
            contributions: List of dicts with 'categoryId' and 'amount'
            member: Optional Member instance (will be created/fetched if not provided)

        Returns:
            Dict with success status, message, and transaction details
        """
        try:
            # Normalize phone number
            try:
                normalized_phone = normalize_phone_number(phone_number)
            except ValueError as e:
                return {
                    'success': False,
                    'message': str(e)
                }

            # Validate contributions
            is_valid, error_msg, validated = self.validate_contributions(contributions)
            if not is_valid:
                return {
                    'success': False,
                    'message': error_msg
                }

            # Get or create member
            if not member:
                member, created = Member.objects.get_or_create(
                    phone_number=normalized_phone,
                    defaults={
                        'first_name': 'Guest',
                        'last_name': 'Member',
                        'is_active': True,
                        'is_guest': True
                    }
                )

            if not member.is_active:
                return {
                    'success': False,
                    'message': 'Member account is inactive'
                }

            # Calculate total
            total_amount = self.calculate_total(validated)

            # Create contribution group ID
            group_id = uuid.uuid4()

            # Build transaction description
            category_names = [v['category'].name for v in validated]
            if len(category_names) > 2:
                desc_categories = f"{category_names[0]}, {category_names[1]} +{len(category_names) - 2} more"
            else:
                desc_categories = ", ".join(category_names)

            transaction_desc = f"{desc_categories} - {member.full_name}"

            # Use first category code as account reference (or create combined code)
            account_reference = validated[0]['category'].code

            # Initiate M-Pesa STK Push
            stk_result = self.mpesa_service.initiate_stk_push(
                phone_number=normalized_phone,
                amount=total_amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc
            )

            if not stk_result['success']:
                return {
                    'success': False,
                    'message': stk_result['message']
                }

            mpesa_transaction = stk_result['transaction']

            # Create contribution records for each category
            # Wrapped in atomic block to ensure all-or-nothing DB writes.
            # NOTE: The STK push above is intentionally OUTSIDE this atomic block
            # because it's an external HTTP call that cannot be rolled back.
            contribution_records = []
            with transaction.atomic():
                for validated_contrib in validated:
                    contribution = Contribution.objects.create(
                        member=member,
                        category=validated_contrib['category'],
                        mpesa_transaction=mpesa_transaction,
                        contribution_group_id=group_id,
                        amount=validated_contrib['amount'],
                        status='pending',
                        entry_type='mpesa',
                        transaction_date=timezone.now(),
                        notes=f"Multi-category contribution - Group {group_id}"
                    )
                    contribution_records.append(contribution)

            return {
                'success': True,
                'message': stk_result['message'],
                'total_amount': total_amount,
                'contribution_group_id': str(group_id),
                'contributions': contribution_records,
                'mpesa_transaction': mpesa_transaction,
                'checkout_request_id': stk_result['checkout_request_id']
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Error processing multi-category contribution: {str(e)}"
            }

    def get_grouped_contributions(self, group_id: uuid.UUID) -> List[Contribution]:
        """
        Retrieve all contributions in a group.

        Args:
            group_id: UUID of the contribution group

        Returns:
            List of Contribution objects
        """
        return Contribution.objects.filter(
            contribution_group_id=group_id
        ).select_related('category', 'member', 'mpesa_transaction').order_by('category__name')
