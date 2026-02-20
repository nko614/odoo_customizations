# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    is_create_from_ecommerce = fields.Boolean(string='Created from E-commerce Platform')
