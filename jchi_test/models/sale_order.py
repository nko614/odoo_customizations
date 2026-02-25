from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_field_a = fields.Float(string='Field A')
    x_field_b = fields.Float(string='Field B')
    x_field_c = fields.Float(string='Field C', compute='_compute_field_c', store=True)

    @api.depends('x_field_a', 'x_field_b')
    def _compute_field_c(self):
        for order in self:
            order.x_field_c = order.x_field_a + order.x_field_b
