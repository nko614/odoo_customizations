from odoo import models, fields

class SupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    x_customer_id = fields.Many2one('res.partner', string='End Customer') 