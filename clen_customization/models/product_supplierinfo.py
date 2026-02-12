from odoo import models, fields, api

class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    x_customer_id = fields.Many2one(
        'res.partner',
        string='End Customer',
        help='Specific customer this vendor is associated with for this product'
    ) 