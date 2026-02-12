# -*- coding: utf-8 -*-

from odoo import models, fields, api
try:
    import stripe
except ImportError:
    stripe = None
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    stripe_payment_id = fields.Char(string='Stripe Payment ID')
    stripe_payment_status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled')
    ], string='Stripe Payment Status')
    stripe_payment_amount = fields.Monetary(string='Stripe Payment Amount')
    
    def action_send_stripe_payment(self):
        """Open wizard to send payment via Stripe"""
        self.ensure_one()
        
        if self.move_type != 'in_invoice':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'This action is only available for vendor bills.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        if not self.partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Please select a vendor first.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Check if vendor has Stripe account
        if not self.partner_id.stripe_account_id:
            return {
                'name': 'Setup Stripe Account',
                'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'open_stripe_tab': True}
            }
        
        # Open payment wizard
        return {
            'name': 'Send Stripe Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'stripe.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_amount': self.amount_residual,
                'default_currency_id': self.currency_id.id,
                'default_stripe_account_id': self.partner_id.stripe_account_id,
            }
        }