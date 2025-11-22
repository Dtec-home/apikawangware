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
