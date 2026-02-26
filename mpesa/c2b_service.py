"""
C2B Contribution Processing Service
Following SOLID principles:
- SRP: Only responsible for processing C2B callbacks into contributions
- DIP: Depends on service abstractions (ReceiptService, normalize_phone_number)
"""

import difflib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.db import transaction
from django.utils.timezone import make_aware

from contributions.models import Contribution, ContributionCategory
from contributions.receipt_service import ReceiptService
from members.models import Member
from members.utils import normalize_phone_number

from .models import C2BTransaction, C2BCallback

logger = logging.getLogger(__name__)


class C2BContributionService:
    """
    Processes C2B callbacks into contribution records.
    Handles member matching, category matching, contribution creation,
    and SMS receipt delivery.
    """

    def validate_c2b_payment(self, callback_data: Dict) -> Dict:
        """
        Validate an incoming C2B payment before it is processed by M-Pesa.
        Called by the validation endpoint.

        Policy: Never reject money. Always accept so the payment goes through.
        Unmatched BillRefNumbers will be flagged during confirmation for
        manual resolution by a treasurer.

        Only rejects if amount is below KES 1.00 (defensive check).

        Args:
            callback_data: Raw C2B validation callback payload

        Returns:
            dict with 'accept' (bool), 'message' (str)
        """
        bill_ref = callback_data.get('BillRefNumber', '').strip()
        amount_str = callback_data.get('TransAmount', '0')

        # Store audit record
        C2BCallback.objects.create(
            callback_type='validation',
            trans_id=callback_data.get('TransID', ''),
            raw_data=callback_data,
            processed=False
        )

        # Validate amount (only hard rejection rule)
        try:
            amount = Decimal(amount_str)
            if amount < Decimal('1.00'):
                logger.warning(f"C2B validation rejected: amount too low ({amount})")
                return {
                    'accept': False,
                    'message': f'Amount KES {amount} is below minimum of KES 1.00'
                }
        except Exception:
            logger.warning(f"C2B validation rejected: invalid amount ({amount_str})")
            return {
                'accept': False,
                'message': f'Invalid amount: {amount_str}'
            }

        # Always accept — unmatched BillRefNumbers handled during confirmation
        logger.info(f"C2B validation accepted: BillRefNumber='{bill_ref}', KES {amount}")
        return {
            'accept': True,
            'message': 'Accepted'
        }

    def process_c2b_confirmation(self, callback_data: Dict) -> Dict:
        """
        Process a C2B confirmation callback.
        Creates C2BTransaction, matches member & category, creates Contribution,
        and sends SMS receipt.

        Args:
            callback_data: Raw C2B confirmation callback payload

        Returns:
            dict with 'success' (bool), 'message' (str), optionally 'transaction', 'contribution'
        """
        trans_id = callback_data.get('TransID', '')

        # Store audit record
        callback_record = C2BCallback.objects.create(
            callback_type='confirmation',
            trans_id=trans_id,
            raw_data=callback_data,
            processed=False
        )

        # Idempotency check: prevent duplicate processing
        if C2BTransaction.objects.filter(trans_id=trans_id).exists():
            logger.warning(f"C2B duplicate callback ignored: {trans_id}")
            callback_record.processed = True
            callback_record.save(update_fields=['processed'])
            return {
                'success': True,
                'message': f'Transaction {trans_id} already processed (duplicate ignored)'
            }

        try:
            return self._process_confirmation(callback_data, callback_record)
        except Exception as e:
            logger.error(f"C2B confirmation processing error for {trans_id}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error processing confirmation: {str(e)}'
            }

    def _match_category(self, bill_ref_number: str) -> Tuple[Optional[ContributionCategory], str]:
        """
        Match a BillRefNumber to a ContributionCategory using a multi-step strategy:
        1. Exact match (case-insensitive)
        2. Fuzzy match using difflib (cutoff=0.6, only if exactly 1 match)
        3. No match → return None

        Args:
            bill_ref_number: The BillRefNumber from the M-Pesa callback

        Returns:
            Tuple of (category or None, match_method: 'exact'|'fuzzy'|'')
        """
        if not bill_ref_number:
            return None, ''

        # 1. Exact match (case-insensitive)
        category = ContributionCategory.objects.filter(
            code__iexact=bill_ref_number,
            is_active=True,
            is_deleted=False
        ).first()

        if category:
            return category, 'exact'

        # 2. Fuzzy match against all active category codes
        active_categories = ContributionCategory.objects.filter(
            is_active=True,
            is_deleted=False
        )
        code_map = {cat.code.upper(): cat for cat in active_categories}
        all_codes = list(code_map.keys())

        if not all_codes:
            return None, ''

        matches = difflib.get_close_matches(
            bill_ref_number.upper(),
            all_codes,
            n=1,
            cutoff=0.6
        )

        if len(matches) == 1:
            matched_code = matches[0]
            category = code_map[matched_code]
            logger.info(
                f"C2B fuzzy match: '{bill_ref_number}' -> '{matched_code}' ({category.name})"
            )
            return category, 'fuzzy'

        # 3. No match
        return None, ''

    def _process_confirmation(self, callback_data: Dict, callback_record: C2BCallback) -> Dict:
        """Internal method to process a confirmed C2B payment."""
        # Parse callback fields
        trans_id = callback_data.get('TransID', '')
        trans_time_str = callback_data.get('TransTime', '')
        trans_amount = Decimal(callback_data.get('TransAmount', '0'))
        business_short_code = callback_data.get('BusinessShortCode', '')
        bill_ref_number = callback_data.get('BillRefNumber', '').strip()
        msisdn = callback_data.get('MSISDN', '')
        first_name = callback_data.get('FirstName', '')
        middle_name = callback_data.get('MiddleName', '')
        last_name = callback_data.get('LastName', '')
        org_balance_str = callback_data.get('OrgAccountBalance', '')

        # Parse transaction time
        try:
            naive_dt = datetime.strptime(trans_time_str, '%Y%m%d%H%M%S')
            trans_time = make_aware(naive_dt)
        except (ValueError, TypeError):
            from django.utils import timezone
            trans_time = timezone.now()

        # Parse org balance
        org_balance = None
        if org_balance_str:
            try:
                org_balance = Decimal(org_balance_str)
            except Exception:
                pass

        # Normalize phone number
        try:
            normalized_phone = normalize_phone_number(msisdn)
        except ValueError:
            normalized_phone = msisdn

        # Match BillRefNumber to category (exact or fuzzy)
        category, match_method = self._match_category(bill_ref_number)

        with transaction.atomic():
            # Create C2BTransaction record
            c2b_transaction = C2BTransaction.objects.create(
                trans_id=trans_id,
                trans_time=trans_time,
                trans_amount=trans_amount,
                business_short_code=business_short_code,
                bill_ref_number=bill_ref_number,
                msisdn=normalized_phone,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                org_account_balance=org_balance,
                status='received',
                matched_category_code=category.code if category else '',
                match_method=match_method,
            )

            # Link callback to transaction
            callback_record.transaction = c2b_transaction
            callback_record.save(update_fields=['transaction'])

            # Always match/create member (even for unmatched payments)
            member = self._match_or_create_member(
                normalized_phone, first_name, middle_name, last_name
            )

            if not category:
                # No match (even after fuzzy) — flag as unmatched
                c2b_transaction.status = 'unmatched'
                c2b_transaction.save(update_fields=['status'])
                callback_record.processed = True
                callback_record.save(update_fields=['processed'])
                logger.warning(
                    f"C2B unmatched: BillRefNumber '{bill_ref_number}' has no match. "
                    f"Trans {trans_id}, KES {trans_amount}, {normalized_phone}. "
                    f"Awaiting manual resolution."
                )
                return {
                    'success': True,
                    'message': f'Payment accepted but category unmatched for reference: {bill_ref_number}',
                    'transaction': c2b_transaction
                }

            # Build contribution notes with match info
            if match_method == 'fuzzy':
                notes = (
                    f'C2B Pay Bill (fuzzy matched {bill_ref_number} → {category.code}) '
                    f'- Trans ID: {trans_id}'
                )
            else:
                notes = f'C2B Pay Bill - Trans ID: {trans_id}'

            # Create Contribution record
            contribution = Contribution.objects.create(
                member=member,
                category=category,
                amount=trans_amount,
                status='completed',
                entry_type='mpesa',
                transaction_date=trans_time,
                notes=notes,
            )

            # Update transaction status
            c2b_transaction.status = 'processed'
            c2b_transaction.save(update_fields=['status'])

            # Mark callback as processed
            callback_record.processed = True
            callback_record.save(update_fields=['processed'])

        # Send SMS receipt (outside transaction to not block on SMS failure)
        self._send_receipt(member, category, trans_amount, trans_time, trans_id)

        logger.info(
            f"C2B contribution recorded: {member.full_name} -> {category.name} "
            f"KES {trans_amount} (Trans: {trans_id}, match: {match_method})"
        )

        return {
            'success': True,
            'message': 'C2B payment processed successfully',
            'transaction': c2b_transaction,
            'contribution': contribution
        }

    def _match_or_create_member(
        self, phone_number: str, first_name: str, middle_name: str, last_name: str
    ) -> Member:
        """
        Match an MSISDN to an existing member, or create a guest member.
        Uses names from the M-Pesa callback instead of generic "Guest Member".
        """
        try:
            member = Member.objects.get(
                phone_number=phone_number,
                is_deleted=False
            )
            return member
        except Member.DoesNotExist:
            pass

        # Create guest member with M-Pesa provided names
        member_first = first_name.strip() or 'Guest'
        member_last = last_name.strip() or 'Member'

        member = Member.objects.create(
            phone_number=phone_number,
            first_name=member_first,
            last_name=member_last,
            is_active=True,
            is_guest=True
        )

        logger.info(f"C2B: Created guest member {member.full_name} ({phone_number})")
        return member

    def _send_receipt(
        self, member: Member, category: ContributionCategory,
        amount: Decimal, transaction_date, trans_id: str
    ):
        """Send SMS receipt for C2B contribution."""
        try:
            receipt_service = ReceiptService()
            result = receipt_service.send_receipt(
                phone_number=member.phone_number,
                member_name=member.full_name,
                category_name=category.name,
                amount=amount,
                transaction_date=transaction_date,
                mpesa_receipt=trans_id
            )

            if result.get('success'):
                print(f"C2B receipt sent to {member.full_name}")
            else:
                print(f"C2B receipt failed: {result.get('message')}")
        except Exception as e:
            logger.error(f"Error sending C2B receipt: {str(e)}")
