"""
PayPal Service Module
Handles PayPal payment processing for the cinema management system
"""

import logging
from flask import current_app
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest

# Configure logging
logger = logging.getLogger(__name__)

class PayPalService:
    """PayPal service for processing payments"""
    
    def __init__(self):
        self.client_id = current_app.config.get('PAYPAL_CLIENT_ID')
        self.client_secret = current_app.config.get('PAYPAL_CLIENT_SECRET')
        self.mode = current_app.config.get('PAYPAL_MODE', 'sandbox')
        
        # Initialize PayPal environment
        if self.mode == 'live':
            self.environment = LiveEnvironment(client_id=self.client_id, client_secret=self.client_secret)
        else:
            self.environment = SandboxEnvironment(client_id=self.client_id, client_secret=self.client_secret)
        
        self.client = PayPalHttpClient(self.environment)
    
    def create_order(self, amount, currency="USD", description="Cinema Booking Payment"):
        """
        Create a PayPal order
        
        Args:
            amount (float): Payment amount
            currency (str): Currency code (default: USD)
            description (str): Order description
            
        Returns:
            dict: PayPal order response or None if error
        """
        try:
            request = OrdersCreateRequest()
            request.prefer("return=representation")
            request.request_body({
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'reference_id': f"cinema_booking_{amount}",
                    'description': description,
                    'amount': {
                        'currency_code': currency,
                        'value': f"{amount:.2f}"
                    }
                }]
            })
            
            response = self.client.execute(request)
            logger.info(f"PayPal order created: {response.result.id}")
            return response.result
            
        except Exception as e:
            logger.error(f"Error creating PayPal order: {str(e)}")
            return None
    
    def capture_order(self, order_id):
        """
        Capture a PayPal order payment
        
        Args:
            order_id (str): PayPal order ID
            
        Returns:
            dict: PayPal capture response or None if error
        """
        try:
            request = OrdersCaptureRequest(order_id)
            response = self.client.execute(request)
            logger.info(f"PayPal order captured: {order_id}")
            return response.result
            
        except Exception as e:
            logger.error(f"Error capturing PayPal order {order_id}: {str(e)}")
            return None
    
    def get_client_id(self):
        """Get PayPal client ID for frontend"""
        return self.client_id
    
    def is_sandbox(self):
        """Check if using sandbox mode"""
        return self.mode == 'sandbox'

def get_paypal_service():
    """Get PayPal service instance"""
    return PayPalService()