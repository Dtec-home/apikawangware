"""
GraphQL Context and Custom View
Adds authentication to GraphQL context
"""

import logging
from strawberry.django.views import GraphQLView as BaseGraphQLView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.request import Request
from django.http import HttpRequest

logger = logging.getLogger(__name__)


class AuthenticatedGraphQLView(BaseGraphQLView):
    """
    Custom GraphQL View that adds JWT authentication.
    """

    def get_context(self, request: HttpRequest, response):
        """
        Override to add JWT authentication to context.
        """
        # Create DRF request wrapper to use JWT authentication
        drf_request = Request(request)

        # Try to authenticate using JWT
        jwt_auth = JWTAuthentication()
        try:
            user_auth_tuple = jwt_auth.authenticate(drf_request)
            if user_auth_tuple is not None:
                request.user = user_auth_tuple[0]
        except (InvalidToken, TokenError) as e:
            logger.warning(f"JWT authentication failed: {e}")
        except Exception as e:
            logger.warning(f"Authentication error: {e}")

        context = super().get_context(request, response)
        return context
