from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lumber_length = fields.Float(string='Length (in)', digits=(12, 2))
    lumber_width = fields.Float(string='Width (in)', digits=(12, 2))
    lumber_thickness = fields.Float(string='Thickness (in)', digits=(12, 4))
    board_feet = fields.Float(
        string='Board Feet',
        compute='_compute_board_feet',
        store=True,
        digits=(12, 4),
    )

    @api.depends('lumber_length', 'lumber_width', 'lumber_thickness')
    def _compute_board_feet(self):
        for rec in self:
            l, w, t = rec.lumber_length, rec.lumber_width, rec.lumber_thickness
            rec.board_feet = (l * w * t) / 144 if all([l, w, t]) else 0.0
