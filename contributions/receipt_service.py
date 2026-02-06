"""
Contribution Receipt Service
Following SOLID principles:
- SRP: Single responsibility for generating and sending contribution receipts
- DIP: Depends on SMS service abstraction
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional
import logging

from members.otp import SMSService


class ReceiptService:
    """
    Service for generating and sending contribution receipts via SMS.
    Following SRP: Only responsible for receipt generation and delivery.
    """

    def __init__(self):
        self.sms_service = SMSService()
        self.logger = logging.getLogger(__name__)

    def format_receipt_message(
        self,
        member_name: str,
        category_name: str,
        amount: Decimal,
        transaction_date: datetime,
        receipt_number: Optional[str] = None,
        mpesa_receipt: Optional[str] = None
    ) -> str:
        """
        Format a contribution receipt message.

        Args:
            member_name: Name of the member who contributed
            category_name: Category of the contribution (e.g., Tithe, Offering)
            amount: Amount contributed
            transaction_date: Date and time of the transaction
            receipt_number: Manual receipt number (for manual/cash/envelope entries)
            mpesa_receipt: M-Pesa receipt number (for M-Pesa transactions)

        Returns:
            str: Formatted receipt message
        """
        # Format the date nicely
        date_str = transaction_date.strftime('%d/%m/%y %H:%M')

        # Determine which receipt number to use
        receipt = mpesa_receipt or receipt_number or 'N/A'

        # Use first word of category name
        category_short = category_name.split()[0]

        # Create concise receipt message
        message = (
            f"Thank you {member_name.split()[0]}!\n"
            f"{category_short}: KES {amount:,.0f}\n"
            f"Ref: {receipt}\n"
            f"{date_str}"
        )

        return message

    def send_receipt(
        self,
        phone_number: str,
        member_name: str,
        category_name: str,
        amount: Decimal,
        transaction_date: datetime,
        receipt_number: Optional[str] = None,
        mpesa_receipt: Optional[str] = None
    ) -> dict:
        """
        Send a contribution receipt via SMS.

        Args:
            phone_number: Phone number to send receipt to
            member_name: Name of the member
            category_name: Category of the contribution
            amount: Amount contributed
            transaction_date: Date and time of the transaction
            receipt_number: Manual receipt number (for manual/cash/envelope entries)
            mpesa_receipt: M-Pesa receipt number (for M-Pesa transactions)

        Returns:
            dict: Result with 'success' and 'message' keys
        """
        try:
            # Format the receipt message
            message = self.format_receipt_message(
                member_name=member_name,
                category_name=category_name,
                amount=amount,
                transaction_date=transaction_date,
                receipt_number=receipt_number,
                mpesa_receipt=mpesa_receipt
            )

            # Determine receipt type for logging
            receipt_type = "M-Pesa" if mpesa_receipt else "Manual"
            receipt_value = mpesa_receipt or receipt_number or "N/A"

            # Log receipt generation
            self.logger.info(
                f"Sending {receipt_type} receipt to {phone_number} for {category_name} "
                f"contribution of KES {amount}"
            )
            print(f"\n{'='*50}")
            print(f"📧 Generating {receipt_type} Receipt")
            print(f"   To: {member_name} ({phone_number})")
            print(f"   Category: {category_name}")
            print(f"   Amount: KES {amount:,.2f}")
            print(f"   Receipt: {receipt_value}")
            print(f"{'='*50}\n")

            # Send via SMS
            result = self.sms_service.send_sms(phone_number, message)

            if result.get('success'):
                self.logger.info(f"Receipt sent successfully to {phone_number}")
                print(f"✅ Receipt sent successfully!")
                return {
                    'success': True,
                    'message': 'Receipt sent successfully'
                }
            else:
                error_msg = result.get('message', 'Unknown error')
                self.logger.error(f"Failed to send receipt: {error_msg}")
                print(f"❌ Failed to send receipt: {error_msg}")
                return {
                    'success': False,
                    'message': f'Failed to send receipt: {error_msg}'
                }

        except Exception as e:
            self.logger.error(f"Error sending receipt: {str(e)}")
            print(f"❌ Error sending receipt: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Error sending receipt: {str(e)}'
            }

    def format_multi_category_receipt_message(
        self,
        member_name: str,
        contributions: list,
        total_amount: Decimal,
        transaction_date: datetime,
        mpesa_receipt: Optional[str] = None
    ) -> str:
        """
        Format a multi-category contribution receipt message.

        Args:
            member_name: Name of the member who contributed
            contributions: List of dicts with 'category_name' and 'amount'
            total_amount: Total amount contributed across all categories
            transaction_date: Date and time of the transaction
            mpesa_receipt: M-Pesa receipt number

        Returns:
            str: Formatted receipt message
        """
        # Format the date nicely
        date_str = transaction_date.strftime('%d/%m/%y %H:%M')

        # Build contribution breakdown - shortened format
        breakdown_lines = []
        for contrib in contributions:
            # Use first word of category name to save space
            category_short = contrib['category_name'].split()[0]
            amount = contrib['amount']
            breakdown_lines.append(f"{category_short} {amount:,.0f}")

        breakdown = ", ".join(breakdown_lines)

        # Create concise receipt message
        message = (
            f"Thank you {member_name.split()[0]}!\n"
            f"{breakdown}\n"
            f"Total: KES {total_amount:,.0f}\n"
            f"Ref: {mpesa_receipt or 'N/A'}\n"
            f"{date_str}"
        )

        return message

    def send_multi_category_receipt(
        self,
        phone_number: str,
        member_name: str,
        contributions: list,
        total_amount: Decimal,
        transaction_date: datetime,
        mpesa_receipt: Optional[str] = None
    ) -> dict:
        """
        Send a consolidated receipt for multi-category contributions via SMS.

        Args:
            phone_number: Phone number to send receipt to
            member_name: Name of the member
            contributions: List of dicts with 'category_name' and 'amount'
            total_amount: Total amount contributed
            transaction_date: Date and time of the transaction
            mpesa_receipt: M-Pesa receipt number

        Returns:
            dict: Result with 'success' and 'message' keys
        """
        try:
            # Format the receipt message
            message = self.format_multi_category_receipt_message(
                member_name=member_name,
                contributions=contributions,
                total_amount=total_amount,
                transaction_date=transaction_date,
                mpesa_receipt=mpesa_receipt
            )

            # Build category list for logging
            category_names = [c['category_name'] for c in contributions]
            categories_str = ", ".join(category_names)

            # Log receipt generation
            self.logger.info(
                f"Sending multi-category receipt to {phone_number} for {categories_str} "
                f"total KES {total_amount}"
            )
            print(f"\n{'='*50}")
            print(f"📧 Generating Multi-Category Receipt")
            print(f"   To: {member_name} ({phone_number})")
            print(f"   Categories: {categories_str}")
            print(f"   Total: KES {total_amount:,.2f}")
            print(f"   Receipt: {mpesa_receipt or 'N/A'}")
            print(f"{'='*50}\n")

            # Send via SMS
            result = self.sms_service.send_sms(phone_number, message)

            if result.get('success'):
                self.logger.info(f"Multi-category receipt sent successfully to {phone_number}")
                print(f"✅ Multi-category receipt sent successfully!")
                return {
                    'success': True,
                    'message': 'Multi-category receipt sent successfully'
                }
            else:
                error_msg = result.get('message', 'Unknown error')
                self.logger.error(f"Failed to send multi-category receipt: {error_msg}")
                print(f"❌ Failed to send multi-category receipt: {error_msg}")
                return {
                    'success': False,
                    'message': f'Failed to send receipt: {error_msg}'
                }

        except Exception as e:
            self.logger.error(f"Error sending multi-category receipt: {str(e)}")
            print(f"❌ Error sending multi-category receipt: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Error sending receipt: {str(e)}'
            }
