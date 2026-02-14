from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_field_a = fields.Float(string="Field A")
    x_field_b = fields.Float(string="Field B")
    x_field_c = fields.Float(string="Field C", compute="_compute_field_c", store=True)

    @api.depends("x_field_a", "x_field_b")
    def _compute_field_c(self):
        for partner in self:
            partner.x_field_c = partner.x_field_a + partner.x_field_b
