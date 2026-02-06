"""
GraphQL test helpers.
"""

from typing import Dict, Any, Optional
from django.test import Client
from django.contrib.auth.models import User
import json


class GraphQLClient:
    """Helper class for executing GraphQL queries and mutations in tests."""

    def __init__(self):
        self.client = Client()
        self.token = None

    def authenticate(self, user: User):
        """
        Authenticate the client with a user's JWT token.

        Args:
            user: Django User instance
        """
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken.for_user(user)
        self.token = str(token)

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query/mutation string
            variables: Optional variables dict
            operation_name: Optional operation name

        Returns:
            Response data dict
        """
        payload = {
            'query': query,
        }

        if variables:
            payload['variables'] = variables

        if operation_name:
            payload['operationName'] = operation_name

        headers = {
            'CONTENT_TYPE': 'application/json',
        }

        if self.token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {self.token}'

        response = self.client.post(
            '/graphql/',
            data=json.dumps(payload),
            **headers
        )

        return response.json()

    def query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional variables dict

        Returns:
            Response data dict
        """
        return self.execute(query, variables)

    def mutate(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL mutation.

        Args:
            mutation: GraphQL mutation string
            variables: Optional variables dict

        Returns:
            Response data dict
        """
        return self.execute(mutation, variables)

    def assert_no_errors(self, response: Dict[str, Any]):
        """
        Assert that the GraphQL response has no errors.

        Args:
            response: GraphQL response dict
        """
        assert 'errors' not in response, f"GraphQL errors: {response.get('errors')}"

    def assert_has_errors(self, response: Dict[str, Any]):
        """
        Assert that the GraphQL response has errors.

        Args:
            response: GraphQL response dict
        """
        assert 'errors' in response, "Expected GraphQL errors but got none"

    def get_data(self, response: Dict[str, Any], path: str) -> Any:
        """
        Get data from a GraphQL response using dot notation.

        Args:
            response: GraphQL response dict
            path: Dot-separated path (e.g., 'data.myContributions.0.amount')

        Returns:
            Data at the specified path
        """
        self.assert_no_errors(response)

        data = response
        for key in path.split('.'):
            if key.isdigit():
                data = data[int(key)]
            else:
                data = data[key]

        return data


# Common GraphQL query/mutation strings
QUERIES = {
    'contribution_categories': '''
        query ContributionCategories($isActive: Boolean) {
            contributionCategories(isActive: $isActive) {
                id
                name
                code
                description
                isActive
            }
        }
    ''',

    'my_contributions': '''
        query MyContributions($phoneNumber: String!, $limit: Int, $categoryId: ID) {
            myContributions(phoneNumber: $phoneNumber, limit: $limit, categoryId: $categoryId) {
                id
                amount
                status
                transactionDate
                category {
                    id
                    name
                    code
                }
                member {
                    id
                    fullName
                    phoneNumber
                }
            }
        }
    ''',

    'payment_status': '''
        query PaymentStatus($checkoutRequestId: String!) {
            paymentStatus(checkoutRequestId: $checkoutRequestId)
        }
    ''',

    'member_by_phone': '''
        query MemberByPhone($phoneNumber: String!) {
            memberByPhone(phoneNumber: $phoneNumber) {
                id
                fullName
                phoneNumber
                isGuest
                isActive
            }
        }
    ''',
}

MUTATIONS = {
    'request_otp': '''
        mutation RequestOTP($phoneNumber: String!) {
            requestOtp(phoneNumber: $phoneNumber) {
                success
                message
            }
        }
    ''',

    'verify_otp': '''
        mutation VerifyOTP($phoneNumber: String!, $code: String!) {
            verifyOtp(phoneNumber: $phoneNumber, code: $code) {
                success
                message
                token
                user {
                    id
                    username
                }
                member {
                    id
                    fullName
                    phoneNumber
                }
            }
        }
    ''',

    'initiate_contribution': '''
        mutation InitiateContribution($phoneNumber: String!, $amount: String!, $categoryId: ID!) {
            initiateContribution(phoneNumber: $phoneNumber, amount: $amount, categoryId: $categoryId) {
                success
                message
                checkoutRequestId
                amount
                phoneNumber
            }
        }
    ''',

    'initiate_multi_contribution': '''
        mutation InitiateMultiContribution($phoneNumber: String!, $contributions: [CategoryAmountInput!]!) {
            initiateMultiCategoryContribution(phoneNumber: $phoneNumber, contributions: $contributions) {
                success
                message
                checkoutRequestId
                totalAmount
                phoneNumber
                contributions {
                    categoryId
                    categoryName
                    amount
                }
            }
        }
    ''',

    'create_manual_contribution': '''
        mutation CreateManualContribution(
            $phoneNumber: String!,
            $amount: String!,
            $categoryId: ID!,
            $entryType: String!,
            $receiptNumber: String,
            $notes: String
        ) {
            createManualContribution(
                phoneNumber: $phoneNumber,
                amount: $amount,
                categoryId: $categoryId,
                entryType: $entryType,
                receiptNumber: $receiptNumber,
                notes: $notes
            ) {
                success
                message
                contribution {
                    id
                    amount
                    status
                    entryType
                    manualReceiptNumber
                }
                memberCreated
                isGuest
                smsSent
            }
        }
    ''',
}
