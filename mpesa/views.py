"""
M-Pesa API Views
Following SOLID principles:
- SRP: Each view has single responsibility
- DIP: Views depend on service abstractions
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import MpesaCallbackHandler
from .c2b_service import C2BContributionService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    Handle M-Pesa STK Push callbacks.
    Following SRP: Only responsible for receiving and delegating callback processing.

    M-Pesa sends callbacks here when a payment is completed, failed, or cancelled.
    """
    try:
        # Parse callback data
        callback_data = json.loads(request.body.decode('utf-8'))

        # Log callback for debugging
        logger.info(f"M-Pesa callback received: {callback_data}")

        # Process callback using service
        handler = MpesaCallbackHandler()
        result = handler.process_callback(callback_data)

        # M-Pesa expects a success response regardless
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in callback: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Internal error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def c2b_validation(request):
    """
    Handle M-Pesa C2B validation callbacks.
    Called by Safaricom BEFORE processing a Pay Bill payment.
    Returns ResultCode 0 to accept or 1 to reject the payment.
    """
    try:
        callback_data = json.loads(request.body.decode('utf-8'))
        logger.info(f"C2B validation callback received: {callback_data}")

        service = C2BContributionService()
        result = service.validate_c2b_payment(callback_data)

        if result['accept']:
            return JsonResponse({
                'ResultCode': 0,
                'ResultDesc': 'Accepted'
            })
        else:
            return JsonResponse({
                'ResultCode': 1,
                'ResultDesc': result['message']
            })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in C2B validation callback: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        logger.error(f"Error processing C2B validation: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Internal error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def c2b_confirmation(request):
    """
    Handle M-Pesa C2B confirmation callbacks.
    Called by Safaricom AFTER a Pay Bill payment is processed.
    Records the transaction, creates a contribution, and sends an SMS receipt.
    """
    try:
        callback_data = json.loads(request.body.decode('utf-8'))
        logger.info(f"C2B confirmation callback received: {callback_data}")

        service = C2BContributionService()
        result = service.process_c2b_confirmation(callback_data)

        # Always return success to Safaricom to acknowledge receipt
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in C2B confirmation callback: {str(e)}")
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        logger.error(f"Error processing C2B confirmation: {str(e)}")
        # Still return success so Safaricom doesn't retry
        return JsonResponse({
            'ResultCode': 0,
            'ResultDesc': 'Accepted'
        })
