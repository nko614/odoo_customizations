from odoo import models


class EcommerceAccount(models.Model):
    _inherit = 'ecommerce.account'

    def _prepare_order_values(self, order_data):
        order_vals = super()._prepare_order_values(order_data)

        if self.channel_code != 'shopify':
            return order_vals

        utm_data = order_data.get('utm_data') or {}
        if not utm_data.get('ready'):
            return order_vals

        if utm_data.get('source'):
            source = self.env['utm.source'].sudo().search(
                [('name', '=ilike', utm_data['source'])], limit=1,
            )
            if not source:
                source = self.env['utm.source'].sudo().create(
                    {'name': utm_data['source']},
                )
            order_vals['source_id'] = source.id

        if utm_data.get('medium'):
            medium = self.env['utm.medium'].sudo().search(
                [('name', '=ilike', utm_data['medium'])], limit=1,
            )
            if not medium:
                medium = self.env['utm.medium'].sudo().create(
                    {'name': utm_data['medium']},
                )
            order_vals['medium_id'] = medium.id

        if utm_data.get('campaign'):
            campaign = self.env['utm.campaign'].sudo().search(
                [('name', '=ilike', utm_data['campaign'])], limit=1,
            )
            if not campaign:
                campaign = self.env['utm.campaign'].sudo().create(
                    {'name': utm_data['campaign']},
                )
            order_vals['campaign_id'] = campaign.id

        return order_vals
