from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    field_a = fields.Float(string='A')
    field_b = fields.Float(string='B')
    field_c = fields.Float(string='C', compute='_compute_field_c', store=True)

    @api.depends('field_a', 'field_b')
    def _compute_field_c(self):
        for record in self:
            record.field_c = record.field_a + record.field_b
