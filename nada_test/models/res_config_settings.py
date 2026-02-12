from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fsm_mileage_unit_cost = fields.Float(
        string="Mileage Cost per Mile",
        config_parameter='nada_test.fsm_mileage_unit_cost',
        default=0.67,
    )
