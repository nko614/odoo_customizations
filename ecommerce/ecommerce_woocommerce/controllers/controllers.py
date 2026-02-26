# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class WooAuthController(http.Controller):
    RETURN_URL = '/woocommerce/callback'

    @http.route(RETURN_URL, auth='public', methods=['POST'], csrf=False)
    def woocommerce_callback(self, **post):
        """Handle the WooCommerce OAuth callback and store API credentials.

        Receives the WooCommerce authorization callback, validates API credentials,
        links them to the ecommerce account, and marks it as connected.

        :param dict post: Raw POST data sent by WooCommerce callback.
        :raises ValidationError: If the consumer key or consumer secret is missing.
        :return: None
        """
        _logger.info('Authenticate Woocommerce redirect request with data: %s', post)
        raw_data = request.httprequest.get_data()
        data = json.loads(raw_data)
        user_id = data.get('user_id')
        ecommerce_account = request.env['ecommerce.account'].sudo().search([
            ('channel_code', '=', 'woocommerce'),
            ('id', '=', int(user_id)),
        ])
        if not data.get('consumer_key') or not data.get('consumer_secret'):
            raise ValidationError(self.env._("WooCommerce callback is missing Consumer Secret or Consumer Key"))
        ecommerce_account.sudo().write({
            'wc_consumer_key': data.get('consumer_key'),
            'wc_consumer_secret': data.get('consumer_secret'),
            'state': 'connected',
        })
        return
