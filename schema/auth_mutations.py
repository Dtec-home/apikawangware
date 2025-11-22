"""
GraphQL Authentication Mutations
Following SRP: Each mutation has single responsibility
Following DIP: Depends on OTPService abstraction
"""

import strawberry
from typing import Optional
from rest_framework_simplejwt.tokens import RefreshToken
from members.otp import OTPService


@strawberry.type
class AuthResponse:
    """Response for authentication operations"""
    success: bool
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[int] = None
    member_id: Optional[int] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    expires_in_minutes: Optional[int] = None
    otp_code: Optional[str] = None  # Only for development/testing


@strawberry.type
class AuthMutations:
    """Authentication mutations"""

    @strawberry.mutation
    def request_otp(self, phone_number: str) -> AuthResponse:
        """
        Request OTP for phone-based authentication.

        Args:
            phone_number: Phone number in format 254XXXXXXXXX

        Returns:
            AuthResponse with success status and message
        """
        # Validate phone number format
        if not phone_number.startswith('254') or len(phone_number) != 12:
            return AuthResponse(
                success=False,
                message='Invalid phone number format. Use 254XXXXXXXXX'
            )

        # Create OTP
        otp_service = OTPService()
        result = otp_service.create_otp(phone_number)

        if not result['success']:
            return AuthResponse(
                success=False,
                message=result['message']
            )

        response = AuthResponse(
            success=True,
            message=result['message'],
            expires_in_minutes=result.get('expires_in_minutes')
        )

        # Include OTP code in response for development only
        if 'otp_code' in result:
            response.otp_code = result['otp_code']

        return response

    @strawberry.mutation
    def verify_otp(self, phone_number: str, otp_code: str) -> AuthResponse:
        """
        Verify OTP and return JWT tokens.

        Args:
            phone_number: Phone number in format 254XXXXXXXXX
            otp_code: 6-digit OTP code

        Returns:
            AuthResponse with JWT tokens if successful
        """
        # Validate inputs
        if not phone_number or not otp_code:
            return AuthResponse(
                success=False,
                message='Phone number and OTP code are required'
            )

        if len(otp_code) != 6 or not otp_code.isdigit():
            return AuthResponse(
                success=False,
                message='OTP code must be 6 digits'
            )

        # Verify OTP
        otp_service = OTPService()
        result = otp_service.verify_otp(phone_number, otp_code)

        if not result['success']:
            return AuthResponse(
                success=False,
                message=result['message']
            )

        # Get user and member from result
        user = result['user']
        member = result['member']

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return AuthResponse(
            success=True,
            message='Authentication successful',
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            member_id=member.id,
            phone_number=member.phone_number,
            full_name=member.full_name
        )

    @strawberry.mutation
    def refresh_token(self, refresh_token: str) -> AuthResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: JWT refresh token

        Returns:
            AuthResponse with new access token
        """
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            return AuthResponse(
                success=True,
                message='Token refreshed successfully',
                access_token=access_token
            )

        except Exception as e:
            return AuthResponse(
                success=False,
                message=f'Invalid or expired refresh token: {str(e)}'
            )

    @strawberry.mutation
    def logout(self, refresh_token: str) -> AuthResponse:
        """
        Logout user by blacklisting refresh token.

        Args:
            refresh_token: JWT refresh token to blacklist

        Returns:
            AuthResponse with success status
        """
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return AuthResponse(
                success=True,
                message='Logged out successfully'
            )

        except Exception as e:
            return AuthResponse(
                success=False,
                message=f'Error logging out: {str(e)}'
            )
