"""
GraphQL Mutations for Member Import
Following SRP: Only responsible for GraphQL mutation definitions
"""

import strawberry
from typing import List, Optional
from django.contrib.auth.models import User

from .types import MemberImportResponse
from members.member_import_service import MemberImportService


@strawberry.type
class MemberImportMutations:
    """Member import mutations"""

    @strawberry.mutation
    def import_members(
        self,
        info,
        csv_data: str,
        file_type: str = 'csv'
    ) -> 'MemberImportResponse':
        """
        Import members from CSV or Excel data.
        Requires admin authentication.

        Args:
            csv_data: CSV content as string or base64 encoded Excel
            file_type: 'csv' or 'excel'

        Returns:
            MemberImportResponse with import results
        """
        # Check authentication
        user = info.context.request.user
        if not user.is_authenticated:
            return MemberImportResponse(
                success=False,
                message="Authentication required",
                imported_count=0,
                skipped_count=0,
                error_count=0,
                errors=["User not authenticated"],
                duplicates=[]
            )

        # Check if user is staff/admin
        if not user.is_staff:
            return MemberImportResponse(
                success=False,
                message="Admin access required",
                imported_count=0,
                skipped_count=0,
                error_count=0,
                errors=["Insufficient permissions"],
                duplicates=[]
            )

        # Perform import
        import_service = MemberImportService()
        result = import_service.import_members(
            file_content=csv_data,
            file_type=file_type
        )

        return MemberImportResponse(
            success=result['success'],
            message=result['message'],
            imported_count=result['imported_count'],
            skipped_count=result['skipped_count'],
            error_count=result['error_count'],
            errors=result['errors'],
            duplicates=result['duplicates']
        )

    @strawberry.mutation
    def get_member_import_template(self) -> str:
        """
        Get CSV template for member import.

        Returns:
            CSV template as string
        """
        import_service = MemberImportService()
        return import_service.generate_csv_template()
