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
        mpesa_receipt: str,
        transaction_date: datetime
    ) -> str:
        """
        Format a contribution receipt message.

        Args:
            member_name: Name of the member who contributed
            category_name: Category of the contribution (e.g., Tithe, Offering)
            amount: Amount contributed
            mpesa_receipt: M-Pesa receipt number
            transaction_date: Date and time of the transaction

        Returns:
            str: Formatted receipt message
        """
        # Format the date nicely
        date_str = transaction_date.strftime('%d %b %Y, %I:%M %p')

        # Create receipt message
        message = (
            f"Dear {member_name},\n\n"
            f"Thank you for your contribution!\n\n"
            f"Category: {category_name}\n"
            f"Amount: KES {amount:,.2f}\n"
            f"Receipt: {mpesa_receipt}\n"
            f"Date: {date_str}\n\n"
            f"God bless you!\n"
            f"- Treasurer, SDA Church-Kawangware"
        )

        return message

    def send_receipt(
        self,
        phone_number: str,
        member_name: str,
        category_name: str,
        amount: Decimal,
        mpesa_receipt: str,
        transaction_date: datetime
    ) -> dict:
        """
        Send a contribution receipt via SMS.

        Args:
            phone_number: Phone number to send receipt to
            member_name: Name of the member
            category_name: Category of the contribution
            amount: Amount contributed
            mpesa_receipt: M-Pesa receipt number
            transaction_date: Date and time of the transaction

        Returns:
            dict: Result with 'success' and 'message' keys
        """
        try:
            # Format the receipt message
            message = self.format_receipt_message(
                member_name=member_name,
                category_name=category_name,
                amount=amount,
                mpesa_receipt=mpesa_receipt,
                transaction_date=transaction_date
            )

            # Log receipt generation
            self.logger.info(
                f"Sending receipt to {phone_number} for {category_name} "
                f"contribution of KES {amount}"
            )
            print(f"\n{'='*50}")
            print(f"📧 Generating Receipt")
            print(f"   To: {member_name} ({phone_number})")
            print(f"   Category: {category_name}")
            print(f"   Amount: KES {amount:,.2f}")
            print(f"   Receipt: {mpesa_receipt}")
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
