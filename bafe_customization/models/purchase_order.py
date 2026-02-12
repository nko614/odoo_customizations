from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    x_customer_id = fields.Many2one(
        'res.partner', 
        string='End Customer',
        store=True
    )
    
    unique_key = fields.Char(
        string='Unique Key',
        copy=False,
        help='Technical field to prevent PO grouping'
    ) 