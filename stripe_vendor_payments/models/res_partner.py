# -*- coding: utf-8 -*-

from odoo import models, fields, api
try:
    import stripe
except ImportError:
    stripe = None
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Stripe Connect fields
    stripe_account_id = fields.Char(
        string='Stripe Account ID',
        help='Stripe Connected Account ID for this vendor'
    )
    stripe_onboarding_completed = fields.Boolean(
        string='Stripe Onboarding Completed',
        default=False
    )
    stripe_charges_enabled = fields.Boolean(
        string='Stripe Charges Enabled',
        default=False
    )
    stripe_payouts_enabled = fields.Boolean(
        string='Stripe Payouts Enabled',
        default=False
    )
    stripe_account_link = fields.Char(
        string='Stripe Account Link',
        help='Temporary link for completing Stripe onboarding'
    )
    stripe_account_type = fields.Selection([
        ('express', 'Express'),
        ('standard', 'Standard'),
        ('custom', 'Custom')
    ], string='Stripe Account Type', default='express')
    
    def action_create_stripe_account(self):
        """Create a Stripe Connect account for this vendor"""
        self.ensure_one()
        
        # Get Stripe configuration
        stripe_config = self.env['stripe.config'].get_stripe_config()
        stripe_api = stripe_config.init_stripe()
        
        try:
            # Create Express account (simplest for MVP)
            account = stripe_api.Account.create(
                type='express',
                country='US',  # Default to US, can be made dynamic
                email=self.email or False,
                capabilities={
                    'transfers': {'requested': True},
                    'card_payments': {'requested': True}
                },
                business_profile={
                    'name': self.name,
                    'url': self.website or None,
                },
                metadata={
                    'odoo_partner_id': str(self.id),
                    'odoo_partner_name': self.name,
                }
            )
            
            self.stripe_account_id = account.id
            
            # Create account link for onboarding
            self.action_create_onboarding_link()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Stripe account created: {account.id}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except stripe.error.StripeError as e:
            _logger.error(f"Stripe error creating account: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to create Stripe account: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }
    
    def action_create_onboarding_link(self):
        """Create an onboarding link for the vendor to complete KYC"""
        self.ensure_one()
        
        if not self.stripe_account_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No Stripe account found. Please create one first.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        stripe_config = self.env['stripe.config'].get_stripe_config()
        stripe_api = stripe_config.init_stripe()
        
        try:
            # Create account link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            account_link = stripe_api.AccountLink.create(
                account=self.stripe_account_id,
                refresh_url=f"{base_url}/web#id={self.id}&model=res.partner&view_type=form",
                return_url=f"{base_url}/web#id={self.id}&model=res.partner&view_type=form&stripe_onboarding=success",
                type='account_onboarding',
            )
            
            self.stripe_account_link = account_link.url
            
            # Open the link in a new tab
            return {
                'type': 'ir.actions.act_url',
                'url': account_link.url,
                'target': 'new',
            }
            
        except stripe.error.StripeError as e:
            _logger.error(f"Stripe error creating onboarding link: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to create onboarding link: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }
    
    def action_check_stripe_status(self):
        """Check and update the Stripe account status"""
        self.ensure_one()
        
        if not self.stripe_account_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No Stripe account found.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        stripe_config = self.env['stripe.config'].get_stripe_config()
        stripe_api = stripe_config.init_stripe()
        
        try:
            # Retrieve account details
            account = stripe_api.Account.retrieve(self.stripe_account_id)
            
            # Update status fields
            self.stripe_charges_enabled = account.charges_enabled
            self.stripe_payouts_enabled = account.payouts_enabled
            self.stripe_onboarding_completed = account.details_submitted
            
            status_msg = f"""
            Account Status Updated:
            - Charges Enabled: {'Yes' if account.charges_enabled else 'No'}
            - Payouts Enabled: {'Yes' if account.payouts_enabled else 'No'}
            - Details Submitted: {'Yes' if account.details_submitted else 'No'}
            """
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Status Updated',
                    'message': status_msg,
                    'type': 'info',
                    'sticky': True,
                }
            }
            
        except stripe.error.StripeError as e:
            _logger.error(f"Stripe error checking account status: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to check account status: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }