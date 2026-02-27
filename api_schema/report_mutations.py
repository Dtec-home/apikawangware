"""
Report Generation Mutations
Handles report generation with staff permissions
"""

import strawberry
from typing import Optional, List
from datetime import datetime
import base64

from members.roles import PermissionChecker
from reports.services import ReportService


@strawberry.type
class ReportResponse:
    """Response type for report generation"""
    success: bool
    message: str
    file_data: Optional[str] = None  # Base64 encoded file
    filename: Optional[str] = None
    content_type: Optional[str] = None


@strawberry.type
class ReportMutations:
    """
    Report generation mutations.
    All mutations require staff privileges.
    """

    @strawberry.mutation
    def generate_contribution_report(
        self,
        info,
        format: str,
        report_type: str = 'custom',
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        category_id: Optional[int] = None,
        category_ids: Optional[List[int]] = None,
        member_id: Optional[int] = None
    ) -> ReportResponse:
        """
        Generate contribution report.

        Args:
            format: Export format ('excel' or 'pdf')
            report_type: Type of report ('daily', 'weekly', 'monthly', 'custom')
            date_from: Start date (for custom reports)
            date_to: End date (for custom reports)
            category_id: Filter by single category (legacy, use category_ids instead)
            category_ids: Filter by multiple categories
            member_id: Filter by member

        Returns:
            ReportResponse with base64 encoded file data
        """
        # Check permissions
        user = info.context.request.user
        if not user.is_authenticated:
            return ReportResponse(
                success=False,
                message="Authentication required"
            )

        if not PermissionChecker.is_staff(user):
            return ReportResponse(
                success=False,
                message="Requires staff privileges to generate reports"
            )

        # Validate format
        if format.lower() not in ['excel', 'pdf']:
            return ReportResponse(
                success=False,
                message="Invalid format. Must be 'excel' or 'pdf'"
            )

        # Validate report type
        if report_type not in ['daily', 'weekly', 'monthly', 'custom']:
            return ReportResponse(
                success=False,
                message="Invalid report type. Must be 'daily', 'weekly', 'monthly', or 'custom'"
            )

        # Merge category_id into category_ids for backward compatibility
        merged_category_ids = list(category_ids) if category_ids else []
        if category_id and category_id not in merged_category_ids:
            merged_category_ids.append(category_id)

        # Generate report
        try:
            report_service = ReportService()
            file_buffer = report_service.generate_contribution_report(
                format=format,
                report_type=report_type,
                date_from=date_from,
                date_to=date_to,
                category_ids=merged_category_ids or None,
                member_id=member_id
            )

            # Encode file as base64
            file_data = base64.b64encode(file_buffer.read()).decode('utf-8')

            # Determine filename and content type
            file_extension = 'xlsx' if format.lower() == 'excel' else 'pdf'
            filename = f"contribution_report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"

            content_type = (
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                if format.lower() == 'excel'
                else 'application/pdf'
            )

            return ReportResponse(
                success=True,
                message="Report generated successfully",
                file_data=file_data,
                filename=filename,
                content_type=content_type
            )

        except Exception as e:
            return ReportResponse(
                success=False,
                message=f"Error generating report: {str(e)}"
            )
