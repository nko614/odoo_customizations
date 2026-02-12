from odoo import models, fields, api

class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    # Add a many2many field to specify which products can be paid for with this program
    allowed_product_ids = fields.Many2many(
        'product.product',
        'loyalty_program_product_rel',
        'program_id',
        'product_id',
        string='Allowed Products',
        help='Products that can be paid for using this loyalty program',
        domain="[('sale_ok', '=', True)]"
    )

    # Add a boolean field to enable/disable product restrictions
    restrict_products = fields.Boolean(
        string='Restrict Products',
        help='Enable to restrict which products can be paid for with this program',
        default=False
    )