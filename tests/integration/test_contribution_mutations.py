"""
Comprehensive Integration Tests for GraphQL API.
Tests the full stack from GraphQL mutations/queries to database.
"""

import pytest
import responses
import json
from decimal import Decimal
from django.test import Client
from tests.utils.factories import (
    MemberFactory,
    ContributionCategoryFactory,
    ContributionFactory,
    UserFactory,
    MpesaTransactionFactory
)
from tests.utils.mocks import setup_mpesa_mocks, setup_sms_mocks
from mpesa.models import MpesaTransaction
from contributions.models import Contribution
from members.models import Member


def graphql_query(client, query, variables=None):
    """Helper to execute GraphQL queries."""
    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    response = client.post(
        '/graphql/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    return json.loads(response.content)


@pytest.mark.integration
class TestContributionQueries:
    """Integration tests for contribution queries."""

    def test_contribution_categories_query(self, db):
        """Test querying contribution categories."""
        # Create categories
        ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        ContributionCategoryFactory(name='Offering', code='OFFER', is_active=True)
        ContributionCategoryFactory(name='Inactive', code='INACT', is_active=False)

        client = Client()
        query = '''
            query {
                contributionCategories(isActive: true) {
                    id
                    name
                    code
                    isActive
                }
            }
        '''

        response = graphql_query(client, query)

        assert 'errors' not in response
        categories = response['data']['contributionCategories']
        assert len(categories) >= 2
        assert all(cat['isActive'] for cat in categories)

    def test_my_contributions_query(self, db):
        """Test querying member contributions."""
        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory()

        # Create contributions
        ContributionFactory(
            member=member,
            category=category,
            amount=Decimal('1000.00'),
            status='completed'
        )
        ContributionFactory(
            member=member,
            category=category,
            amount=Decimal('500.00'),
            status='completed'
        )

        client = Client()
        query = '''
            query MyContributions($phoneNumber: String!) {
                myContributions(phoneNumber: $phoneNumber) {
                    id
                    amount
                    status
                    category {
                        name
                    }
                }
            }
        '''

        response = graphql_query(client, query, {
            'phoneNumber': '254712345678'
        })

        assert 'errors' not in response
        contributions = response['data']['myContributions']
        assert len(contributions) == 2
        assert float(contributions[0]['amount']) in [1000.00, 500.00]

    def test_payment_status_query(self, db):
        """Test querying payment status."""
        transaction = MpesaTransactionFactory(
            checkout_request_id='test_checkout_123',
            status='completed'
        )

        client = Client()
        query = '''
            query PaymentStatus($checkoutRequestId: String!) {
                paymentStatus(checkoutRequestId: $checkoutRequestId)
            }
        '''

        response = graphql_query(client, query, {
            'checkoutRequestId': 'test_checkout_123'
        })

        assert 'errors' not in response
        status = response['data']['paymentStatus']
        assert status == 'completed'


@pytest.mark.integration
class TestContributionMutations:
    """Integration tests for contribution mutations."""

    @responses.activate
    def test_initiate_contribution_success(self, db):
        """Test successful contribution initiation."""
        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        setup_mpesa_mocks(responses, scenario='success')

        client = Client()
        mutation = '''
            mutation InitiateContribution($phoneNumber: String!, $amount: String!, $categoryId: ID!) {
                initiateContribution(phoneNumber: $phoneNumber, amount: $amount, categoryId: $categoryId) {
                    success
                    message
                    checkoutRequestId
                    amount
                    phoneNumber
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'amount': '1000.00',
            'categoryId': str(category.id)
        })

        assert 'errors' not in response
        data = response['data']['initiateContribution']
        assert data['success'] is True
        assert data['phoneNumber'] == '254712345678'
        assert data['checkoutRequestId'] is not None

        # Verify database
        assert MpesaTransaction.objects.filter(
            phone_number='254712345678',
            status='pending'
        ).exists()

    def test_initiate_contribution_invalid_category(self, db):
        """Test contribution with invalid category."""
        client = Client()
        mutation = '''
            mutation InitiateContribution($phoneNumber: String!, $amount: String!, $categoryId: ID!) {
                initiateContribution(phoneNumber: $phoneNumber, amount: $amount, categoryId: $categoryId) {
                    success
                    message
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'amount': '1000.00',
            'categoryId': '99999'
        })

        # Should either have errors or success=false
        if 'errors' not in response:
            assert response['data']['initiateContribution']['success'] is False

    @responses.activate
    def test_initiate_contribution_creates_guest_member(self, db):
        """Test that new phone number creates guest member."""
        category = ContributionCategoryFactory(is_active=True)
        setup_mpesa_mocks(responses, scenario='success')

        # Ensure member doesn't exist
        assert not Member.objects.filter(phone_number='254798765432').exists()

        client = Client()
        mutation = '''
            mutation InitiateContribution($phoneNumber: String!, $amount: String!, $categoryId: ID!) {
                initiateContribution(phoneNumber: $phoneNumber, amount: $amount, categoryId: $categoryId) {
                    success
                    phoneNumber
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254798765432',
            'amount': '1000.00',
            'categoryId': str(category.id)
        })

        assert 'errors' not in response

        # Guest member should be created
        member = Member.objects.get(phone_number='254798765432')
        assert member.is_guest is True


@pytest.mark.integration
class TestMultiContributionMutations:
    """Integration tests for multi-category contributions."""

    @responses.activate
    def test_initiate_multi_contribution_success(self, db):
        """Test successful multi-category contribution."""
        member = MemberFactory(phone_number='254712345678')
        tithe = ContributionCategoryFactory(name='Tithe', code='TITHE', is_active=True)
        offering = ContributionCategoryFactory(name='Offering', code='OFFER', is_active=True)

        setup_mpesa_mocks(responses, scenario='success')

        client = Client()
        mutation = '''
            mutation InitiateMultiContribution($phoneNumber: String!, $contributions: [CategoryAmountInput!]!) {
                initiateMultiCategoryContribution(phoneNumber: $phoneNumber, contributions: $contributions) {
                    success
                    message
                    totalAmount
                    phoneNumber
                    contributions {
                        categoryId
                        categoryName
                        amount
                    }
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'contributions': [
                {'categoryId': str(tithe.id), 'amount': '1000.00'},
                {'categoryId': str(offering.id), 'amount': '500.00'}
            ]
        })

        assert 'errors' not in response
        data = response['data']['initiateMultiCategoryContribution']
        assert data['success'] is True
        assert float(data['totalAmount']) == 1500.00
        assert len(data['contributions']) == 2

    @responses.activate
    def test_multi_contribution_same_group_id(self, db):
        """Test that multi-category contributions share group ID."""
        member = MemberFactory(phone_number='254712345678')
        cat1 = ContributionCategoryFactory(is_active=True)
        cat2 = ContributionCategoryFactory(is_active=True)

        setup_mpesa_mocks(responses, scenario='success')

        client = Client()
        mutation = '''
            mutation InitiateMultiContribution($phoneNumber: String!, $contributions: [CategoryAmountInput!]!) {
                initiateMultiCategoryContribution(phoneNumber: $phoneNumber, contributions: $contributions) {
                    success
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'contributions': [
                {'categoryId': str(cat1.id), 'amount': '1000.00'},
                {'categoryId': str(cat2.id), 'amount': '500.00'}
            ]
        })

        assert 'errors' not in response

        # Check contributions have same group ID
        contributions = Contribution.objects.filter(member=member).order_by('-created_at')[:2]
        assert contributions.count() == 2
        assert contributions[0].contribution_group_id == contributions[1].contribution_group_id


@pytest.mark.integration
class TestManualContributionMutations:
    """Integration tests for manual contribution mutations."""

    def test_create_manual_contribution_existing_member(self, db):
        """Test creating manual contribution for existing member."""
        admin = UserFactory(is_staff=True, username='admin')
        member = MemberFactory(phone_number='254712345678')
        category = ContributionCategoryFactory(is_active=True)

        client = Client()
        client.force_login(admin)

        mutation = '''
            mutation CreateManualContribution(
                $phoneNumber: String!,
                $amount: String!,
                $categoryId: ID!,
                $entryType: String!,
                $receiptNumber: String
            ) {
                createManualContribution(
                    phoneNumber: $phoneNumber,
                    amount: $amount,
                    categoryId: $categoryId,
                    entryType: $entryType,
                    receiptNumber: $receiptNumber
                ) {
                    success
                    message
                    contribution {
                        id
                        amount
                        status
                        entryType
                    }
                    memberCreated
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'amount': '1000.00',
            'categoryId': str(category.id),
            'entryType': 'manual',
            'receiptNumber': 'MAN001'
        })

        assert 'errors' not in response
        data = response['data']['createManualContribution']
        assert data['success'] is True
        assert data['memberCreated'] is False
        assert float(data['contribution']['amount']) == 1000.00
        assert data['contribution']['status'] == 'completed'


@pytest.mark.integration
class TestAuthenticationMutations:
    """Integration tests for OTP authentication."""

    @responses.activate
    def test_request_otp_success(self, db):
        """Test requesting OTP for existing member."""
        member = MemberFactory(phone_number='254712345678')
        setup_sms_mocks(responses, scenario='success')

        client = Client()
        mutation = '''
            mutation RequestOTP($phoneNumber: String!) {
                requestOtp(phoneNumber: $phoneNumber) {
                    success
                    message
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678'
        })

        assert 'errors' not in response
        data = response['data']['requestOtp']
        assert data['success'] is True

    def test_verify_otp_success(self, db):
        """Test verifying OTP for existing member."""
        from members.otp import OTP
        from django.utils import timezone
        from datetime import timedelta

        member = MemberFactory(phone_number='254712345678')

        # Create valid OTP
        otp = OTP.objects.create(
            phone_number='254712345678',
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        client = Client()
        mutation = '''
            mutation VerifyOTP($phoneNumber: String!, $code: String!) {
                verifyOtp(phoneNumber: $phoneNumber, code: $code) {
                    success
                    message
                    member {
                        fullName
                        phoneNumber
                    }
                }
            }
        '''

        response = graphql_query(client, mutation, {
            'phoneNumber': '254712345678',
            'code': '123456'
        })

        assert 'errors' not in response
        data = response['data']['verifyOtp']
        assert data['success'] is True
        assert data['member']['phoneNumber'] == '254712345678'
