# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class EcommerceChannel(models.Model):
    _inherit = 'ecommerce.channel'

    def _compute_feature_support_fields(self):
        """Override of 'channel' to update features"""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'woocommerce').update({
            'support_location': False,
            'support_shipping': False,
        })
