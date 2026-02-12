from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    devarsh_field = fields.Char(string="Devarsh's Field")