from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # The attachment logic is now handled in mail_compose_message.py
    # This ensures attachments are properly included when sending emails