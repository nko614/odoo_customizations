# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    def _get_available_payment_method_lines(self, payment_type):
        """Override to add Stripe payment method to bank journals"""
        payment_method_lines = super()._get_available_payment_method_lines(payment_type)
        
        if payment_type == 'outbound' and self.type == 'bank':
            # Add Stripe payment method if it exists
            stripe_method = self.env.ref('stripe_vendor_payments.account_payment_method_stripe', raise_if_not_found=False)
            if stripe_method:
                payment_method_lines |= self.env['account.payment.method.line'].create({
                    'name': stripe_method.name,
                    'payment_method_id': stripe_method.id,
                    'journal_id': self.id,
                })
        
        return payment_method_lines