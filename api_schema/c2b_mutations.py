"""
C2B Transaction Mutations
Handles admin resolution of unmatched C2B transactions.
"""

import logging
from decimal import Decimal

import strawberry
from django.db import transaction

from contributions.models import Contribution, ContributionCategory
from contributions.receipt_service import ReceiptService
from members.models import Member
from members.roles import PermissionChecker
from mpesa.models import C2BTransaction

from .types import C2BResolveResponse

logger = logging.getLogger(__name__)


class C2BMutations:
    """Mutations for C2B transaction management."""

    @staticmethod
    def resolve_unmatched_c2b(
        info,
        transaction_id: strawberry.ID,
        category_id: strawberry.ID,
    ) -> C2BResolveResponse:
        """
        Resolve an unmatched C2B transaction by assigning a category.
        Creates the Contribution record and sends SMS receipt.

        Requires staff role (admin, treasurer, or pastor).

        Args:
            transaction_id: ID of the unmatched C2BTransaction
            category_id: ID of the ContributionCategory to assign

        Returns:
            C2BResolveResponse with success status and created records
        """
        user = info.context.request.user
        if not user.is_authenticated:
            return C2BResolveResponse(
                success=False,
                message='Authentication required'
            )

        if not PermissionChecker.is_staff(user):
            return C2BResolveResponse(
                success=False,
                message='Requires staff privileges'
            )

        # Fetch the transaction
        try:
            c2b_tx = C2BTransaction.objects.get(id=int(transaction_id))
        except C2BTransaction.DoesNotExist:
            return C2BResolveResponse(
                success=False,
                message=f'C2B transaction {transaction_id} not found'
            )

        if c2b_tx.status != 'unmatched':
            return C2BResolveResponse(
                success=False,
                message=f'Transaction is not unmatched (current status: {c2b_tx.status})'
            )

        # Fetch the category
        try:
            category = ContributionCategory.objects.get(
                id=int(category_id),
                is_active=True,
                is_deleted=False,
            )
        except ContributionCategory.DoesNotExist:
            return C2BResolveResponse(
                success=False,
                message=f'Category {category_id} not found or inactive'
            )

        # Find the member by phone number
        member = Member.objects.filter(
            phone_number=c2b_tx.msisdn,
            is_deleted=False,
        ).first()

        if not member:
            return C2BResolveResponse(
                success=False,
                message=f'Member with phone {c2b_tx.msisdn} not found'
            )

        try:
            with transaction.atomic():
                # Create Contribution
                contribution = Contribution.objects.create(
                    member=member,
                    category=category,
                    amount=c2b_tx.trans_amount,
                    status='completed',
                    entry_type='mpesa',
                    transaction_date=c2b_tx.trans_time,
                    notes=(
                        f'C2B Pay Bill (manually resolved: {c2b_tx.bill_ref_number} '
                        f'-> {category.code}) - Trans ID: {c2b_tx.trans_id}'
                    ),
                )

                # Update C2BTransaction
                c2b_tx.status = 'processed'
                c2b_tx.match_method = 'manual'
                c2b_tx.matched_category_code = category.code
                c2b_tx.save(update_fields=['status', 'match_method', 'matched_category_code'])

        except Exception as e:
            logger.error(f"Error resolving unmatched C2B {c2b_tx.trans_id}: {e}", exc_info=True)
            return C2BResolveResponse(
                success=False,
                message=f'Error creating contribution: {str(e)}'
            )

        # Send SMS receipt (outside transaction)
        try:
            receipt_service = ReceiptService()
            receipt_service.send_receipt(
                phone_number=member.phone_number,
                member_name=member.full_name,
                category_name=category.name,
                amount=c2b_tx.trans_amount,
                transaction_date=c2b_tx.trans_time,
                mpesa_receipt=c2b_tx.trans_id,
            )
        except Exception as e:
            logger.error(f"Error sending receipt for resolved C2B {c2b_tx.trans_id}: {e}")

        logger.info(
            f"C2B unmatched resolved: {c2b_tx.trans_id} -> {category.name} "
            f"by {user.username}, KES {c2b_tx.trans_amount}"
        )

        return C2BResolveResponse(
            success=True,
            message=f'Transaction resolved: {c2b_tx.bill_ref_number} -> {category.name}',
            transaction=c2b_tx,
            contribution=contribution,
        )
