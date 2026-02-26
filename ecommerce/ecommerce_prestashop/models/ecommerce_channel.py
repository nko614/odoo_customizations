# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class EcommerceChannel(models.Model):
    _inherit = 'ecommerce.channel'

    def _compute_feature_support_fields(self):
        """Override of 'channel' to update features"""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'prestashop').update({
            'support_shipping': False,
        })
