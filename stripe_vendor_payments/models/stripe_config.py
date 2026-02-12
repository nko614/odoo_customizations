# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None
    logging.warning("Stripe library not installed. Install with: pip install stripe")

_logger = logging.getLogger(__name__)

class StripeConfig(models.Model):
    _name = 'stripe.config'
    _description = 'Stripe Configuration'
    _rec_name = 'name'
    
    name = fields.Char(string='Configuration Name', default='Default', required=True)
    publishable_key = fields.Char(
        string='Publishable Key',
        required=True,
        help='Your Stripe publishable key (starts with pk_)'
    )
    secret_key = fields.Char(
        string='Secret Key',
        required=True,
        help='Your Stripe secret key (starts with sk_)'
    )
    webhook_endpoint_secret = fields.Char(string='Webhook Endpoint Secret')
    is_test_mode = fields.Boolean(string='Test Mode', default=True)
    
    @api.model
    def get_stripe_config(self):
        """Get the active Stripe configuration"""
        config = self.search([], limit=1)
        if not config:
            # Create default config if none exists
            config = self.create({
                'name': 'Default Configuration',
            })
        return config
    
    def init_stripe(self):
        """Initialize Stripe with the configuration"""
        import stripe  # Import here to ensure it's fresh
        stripe.api_key = self.secret_key
        stripe.api_version = '2024-06-20'  # Use a stable API version
        return stripe