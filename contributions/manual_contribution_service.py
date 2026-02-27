"""
Manual Contribution Service
Following SOLID principles:
- SRP: Only responsible for manual contribution entry logic
- DIP: Depends on model abstractions
"""

from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

from .models import Contribution, ContributionCategory
from members.models import Member
from members.utils import normalize_phone_number


class ManualContributionService:
    """
    Handles manual contribution entries.
    Following SRP: Only responsible for creating manual contributions.
    """

    def create_manual_contribution(
        self,
        phone_number: str,
        amount: Decimal,
        category_id: str,
        entry_type: str = 'manual',
        receipt_number: Optional[str] = None,
        transaction_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        entered_by_user: Optional[User] = None
    ) -> Dict:
        """
        Create a manual contribution entry.

        Args:
            phone_number: Member's phone number (will be normalized)
            amount: Contribution amount
            category_id: ID of contribution category
            entry_type: Type of entry ('manual', 'cash', 'envelope')
            receipt_number: Optional receipt number
            transaction_date: When the contribution was made (defaults to now)
            notes: Optional notes
            entered_by_user: User who is entering this contribution

        Returns:
            Dictionary with success status and contribution data or error message
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

            # Validate amount
            if amount < Decimal('1.00'):
                return {
                    'success': False,
                    'message': 'Amount must be at least KES 1.00'
                }

            # Validate entry type
            valid_entry_types = ['manual', 'cash', 'envelope']
            if entry_type not in valid_entry_types:
                return {
                    'success': False,
                    'message': f'Invalid entry type. Must be one of: {", ".join(valid_entry_types)}'
                }

            # Validate category
            try:
                category = ContributionCategory.objects.get(
                    id=category_id,
                    is_active=True,
                    is_deleted=False
                )
            except ContributionCategory.DoesNotExist:
                return {
                    'success': False,
                    'message': 'Invalid or inactive contribution category'
                }

            # Find or create member
            member, created = Member.objects.get_or_create(
                phone_number=normalized_phone,
                defaults={
                    'first_name': 'Guest',
                    'last_name': 'Member',
                    'is_active': True,
                    'is_guest': True
                }
            )

            # Use current time if transaction_date not provided
            if not transaction_date:
                transaction_date = timezone.now()

            # Create contribution in a transaction
            with transaction.atomic():
                contribution = Contribution.objects.create(
                    member=member,
                    category=category,
                    amount=amount,
                    entry_type=entry_type,
                    manual_receipt_number=receipt_number,
                    entered_by=entered_by_user,
                    status='completed',  # Manual entries are immediately completed
                    transaction_date=transaction_date,
                    notes=notes or '',
                    mpesa_transaction=None  # No M-Pesa transaction for manual entries
                )

            # Send receipt SMS (don't fail if SMS fails)
            sms_sent = False
            try:
                from contributions.receipt_service import ReceiptService
                receipt_service = ReceiptService()

                # Generate receipt number if not provided
                date_str = transaction_date.strftime('%Y%m%d')
                final_receipt_number = receipt_number or f"RCP-{date_str}-{contribution.id:04d}"

                # Update contribution with generated receipt number if needed
                if not receipt_number:
                    contribution.manual_receipt_number = final_receipt_number
                    contribution.save(update_fields=['manual_receipt_number'])

                # Send receipt SMS
                sms_result = receipt_service.send_receipt(
                    phone_number=member.phone_number,
                    member_name=member.full_name,
                    category_name=category.name,
                    amount=amount,
                    transaction_date=transaction_date,
                    receipt_number=final_receipt_number
                )

                sms_sent = sms_result.get('success', False)
            except Exception as e:
                # Log error but don't fail the contribution
                print(f"⚠️  Failed to send receipt SMS: {str(e)}")

            return {
                'success': True,
                'message': f'Contribution of KES {amount} recorded successfully',
                'contribution': contribution,
                'member_created': created,
                'is_guest': member.is_guest,
                'sms_sent': sms_sent
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating contribution: {str(e)}'
            }

    def lookup_member_by_phone(self, phone_number: str) -> Dict:
        """
        Look up a member by phone number.

        Args:
            phone_number: Phone number to search for

        Returns:
            Dictionary with member data or guest indicator
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

            # Try to find member
            try:
                member = Member.objects.get(phone_number=normalized_phone)
                return {
                    'success': True,
                    'found': True,
                    'member': member,
                    'is_guest': member.is_guest
                }
            except Member.DoesNotExist:
                return {
                    'success': True,
                    'found': False,
                    'message': 'Member not found - will be created as guest',
                    'phone_number': normalized_phone
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error looking up member: {str(e)}'
            }
