"""
Member Import Service
Following SOLID principles:
- SRP: Each class has a single responsibility
- OCP: Extensible for different file formats
- DIP: Depends on abstractions
"""

import csv
import io
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from openpyxl import load_workbook

from .models import Member
from .utils import normalize_phone_number


class MemberImportValidator:
    """
    Validates individual member records.
    Following SRP: Only responsible for validation logic.
    """

    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']
    OPTIONAL_FIELDS = ['email', 'member_number']

    @staticmethod
    def validate_member_data(data: Dict, row_number: int) -> Tuple[bool, Optional[str]]:
        """
        Validate a single member record.

        Args:
            data: Dictionary containing member data
            row_number: Row number in the import file (for error reporting)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        for field in MemberImportValidator.REQUIRED_FIELDS:
            if not data.get(field) or str(data.get(field)).strip() == '':
                return False, f"Row {row_number}: Missing required field '{field}'"

        # Validate phone number format
        try:
            phone = str(data['phone_number']).strip()
            normalized_phone = normalize_phone_number(phone)
            data['phone_number'] = normalized_phone  # Update with normalized version
        except ValueError as e:
            return False, f"Row {row_number}: {str(e)}"

        # Validate email if provided
        email = data.get('email', '').strip()
        if email and '@' not in email:
            return False, f"Row {row_number}: Invalid email format"

        # Validate names are not too long
        first_name = str(data['first_name']).strip()
        last_name = str(data['last_name']).strip()

        if len(first_name) > 100:
            return False, f"Row {row_number}: First name too long (max 100 characters)"
        if len(last_name) > 100:
            return False, f"Row {row_number}: Last name too long (max 100 characters)"

        return True, None


class MemberImportParser:
    """
    Parses CSV and Excel files.
    Following SRP: Only responsible for file parsing.
    Following OCP: Can be extended for other formats.
    """

    @staticmethod
    def parse_csv(file_content: str) -> List[Dict]:
        """
        Parse CSV content into list of dictionaries.

        Args:
            file_content: CSV file content as string

        Returns:
            List of dictionaries, one per row
        """
        records = []
        csv_file = io.StringIO(file_content)
        reader = csv.DictReader(csv_file)

        for row in reader:
            # Clean up field names and values
            cleaned_row = {
                key.strip().lower(): value.strip() if value else ''
                for key, value in row.items()
            }
            records.append(cleaned_row)

        return records

    @staticmethod
    def parse_excel(file_bytes: bytes) -> List[Dict]:
        """
        Parse Excel file into list of dictionaries.

        Args:
            file_bytes: Excel file content as bytes

        Returns:
            List of dictionaries, one per row
        """
        records = []
        workbook = load_workbook(io.BytesIO(file_bytes), read_only=True)
        sheet = workbook.active

        # Get header row
        headers = []
        for cell in sheet[1]:
            headers.append(str(cell.value).strip().lower() if cell.value else '')

        # Parse data rows
        for row in sheet.iter_rows(min_row=2, values_only=True):
            record = {}
            for i, value in enumerate(row):
                if i < len(headers):
                    record[headers[i]] = str(value).strip() if value else ''

            # Only add non-empty rows
            if any(record.values()):
                records.append(record)

        return records


class MemberImportService:
    """
    Orchestrates the member import process.
    Following SRP: Only responsible for coordinating import workflow.
    Following DIP: Depends on validator and parser abstractions.
    """

    def __init__(self):
        self.validator = MemberImportValidator()
        self.parser = MemberImportParser()

    def import_members(
        self,
        file_content: str,
        file_type: str = 'csv',
        batch_id: Optional[str] = None
    ) -> Dict:
        """
        Import members from CSV or Excel file.

        Args:
            file_content: File content (string for CSV, base64 for Excel)
            file_type: 'csv' or 'excel'
            batch_id: Optional batch identifier for tracking

        Returns:
            Dictionary with import results:
            {
                'success': bool,
                'imported_count': int,
                'skipped_count': int,
                'error_count': int,
                'errors': List[str],
                'duplicates': List[str]
            }
        """
        # Parse file based on type
        try:
            if file_type == 'csv':
                records = self.parser.parse_csv(file_content)
            elif file_type == 'excel':
                import base64
                file_bytes = base64.b64decode(file_content)
                records = self.parser.parse_excel(file_bytes)
            else:
                return {
                    'success': False,
                    'message': f"Unsupported file type: {file_type}",
                    'imported_count': 0,
                    'skipped_count': 0,
                    'error_count': 0,
                    'errors': [],
                    'duplicates': []
                }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error parsing file: {str(e)}",
                'imported_count': 0,
                'skipped_count': 0,
                'error_count': 0,
                'errors': [str(e)],
                'duplicates': []
            }

        # Generate batch ID if not provided
        if not batch_id:
            batch_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Process records
        return self._process_records(records, batch_id)

    def _process_records(self, records: List[Dict], batch_id: str) -> Dict:
        """
        Process and import member records with transaction support.

        Args:
            records: List of member data dictionaries
            batch_id: Batch identifier

        Returns:
            Import results dictionary
        """
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        duplicates = []

        # Get existing phone numbers for duplicate detection
        existing_phones = set(
            Member.objects.values_list('phone_number', flat=True)
        )

        # Validate all records first
        validated_records = []
        for i, record in enumerate(records, start=2):  # Start at 2 (row 1 is header)
            is_valid, error_msg = self.validator.validate_member_data(record, i)

            if not is_valid:
                errors.append(error_msg)
                error_count += 1
                continue

            # Check for duplicates
            phone = record['phone_number']
            if phone in existing_phones:
                duplicates.append(
                    f"Row {i}: Phone number {phone} already exists (skipped)"
                )
                skipped_count += 1
                continue

            # Add to existing phones to catch duplicates within the import file
            existing_phones.add(phone)
            validated_records.append(record)

        # Import validated records in a transaction
        imported_members = []
        try:
            with transaction.atomic():
                for record in validated_records:
                    member = self._create_member(record, batch_id)
                    imported_members.append(member)
                    imported_count += 1

            # Send welcome SMS to imported members (don't fail if SMS fails)
            sms_success_count = 0
            sms_failed_count = 0

            try:
                from members.otp import SMSService
                sms_service = SMSService()

                print(f"\n{'='*50}")
                print(f"📧 Sending Welcome Messages")
                print(f"   Total members: {len(imported_members)}")
                print(f"{'='*50}\n")

                for member in imported_members:
                    try:
                        # Format welcome message
                        message = (
                            f"Welcome to SDA Church-Kawangware, {member.first_name}!\n\n"
                            f"Your member number is: {member.member_number}\n\n"
                            f"You can now make contributions via M-Pesa.\n\n"
                            f"God bless you!"
                        )

                        # Send SMS
                        result = sms_service.send_sms(member.phone_number, message)

                        if result.get('success'):
                            sms_success_count += 1
                            print(f"✅ Welcome SMS sent to {member.full_name}")
                        else:
                            sms_failed_count += 1
                            print(f"⚠️  Failed to send SMS to {member.full_name}: {result.get('message')}")

                    except Exception as e:
                        sms_failed_count += 1
                        print(f"⚠️  Error sending SMS to {member.full_name}: {str(e)}")

                print(f"\n📊 SMS Summary: {sms_success_count} sent, {sms_failed_count} failed\n")

            except Exception as e:
                print(f"⚠️  Error in SMS sending process: {str(e)}")
                # Continue even if SMS fails

        except Exception as e:
            return {
                'success': False,
                'message': f"Error during import: {str(e)}",
                'imported_count': 0,
                'skipped_count': skipped_count,
                'error_count': error_count + len(validated_records),
                'errors': errors + [f"Transaction failed: {str(e)}"],
                'duplicates': duplicates
            }

        # Prepare response
        success = error_count == 0 and imported_count > 0
        message = self._generate_summary_message(
            imported_count, skipped_count, error_count
        )

        return {
            'success': success,
            'message': message,
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'error_count': error_count,
            'errors': errors,
            'duplicates': duplicates
        }

    def _create_member(self, record: Dict, batch_id: str) -> Member:
        """
        Create a member from validated record data.

        Args:
            record: Validated member data
            batch_id: Batch identifier

        Returns:
            Created Member instance
        """
        member = Member.objects.create(
            first_name=record['first_name'].strip(),
            last_name=record['last_name'].strip(),
            phone_number=record['phone_number'],
            email=record.get('email', '').strip() or None,
            member_number=record.get('member_number', '').strip() or None,
            is_active=True,
            is_guest=False,
            import_batch_id=batch_id
        )
        return member

    def _generate_summary_message(
        self,
        imported: int,
        skipped: int,
        errors: int
    ) -> str:
        """Generate human-readable summary message."""
        parts = []

        if imported > 0:
            parts.append(f"{imported} member{'s' if imported != 1 else ''} imported successfully")

        if skipped > 0:
            parts.append(f"{skipped} duplicate{'s' if skipped != 1 else ''} skipped")

        if errors > 0:
            parts.append(f"{errors} error{'s' if errors != 1 else ''}")

        if not parts:
            return "No members imported"

        return ", ".join(parts)

    @staticmethod
    def generate_csv_template() -> str:
        """
        Generate a CSV template for member import.

        Returns:
            CSV template as string
        """
        headers = ['first_name', 'last_name', 'phone_number', 'email']
        sample_data = [
            ['John', 'Doe', '0712345678', 'john@example.com'],
            ['Jane', 'Smith', '254723456789', 'jane@example.com'],
            ['Guest', 'Member', '0734567890', '']
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(sample_data)

        return output.getvalue()
