# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields, models
from odoo.addons.ecommerce_shopify import utils_graphql as shopify_utils_graphql
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError
from odoo.exceptions import UserError


class ecommerceAccount(models.Model):
    _inherit = 'ecommerce.account'

    shopify_authorization_type = fields.Selection(
        selection=[
            ('oauth', "Oauth"),
            ('self_access', "Self Access"),
        ],
        string="Authorization Type",
        required_if_channel="shopify",
        default='self_access',
        help="Select the authorization type to use for Shopify API access.",
    )
    shopify_store = fields.Char(
        string="Shopify Store",
        help="Shopify store name for Shopify API authentication.",  # main store name used for every request.
        copy=False,
    )
    shopify_store_name = fields.Char(
        string="Shopify OAuth Store",
        help="Shopify store name for Shopify API authentication.",
        readonly=True,  # visible in case of oauth flow.
        copy=False,
    )
    shopify_client_id = fields.Char(
        string="Shopify Client Id",
        help="Client Id for Shopify API authentication.",
        copy=False,
    )
    shopify_client_secret = fields.Char(
        string="Shopify Client Secret",
        help="Client Secret for Shopify API authentication.",
        copy=False,
    )
    shopify_access_token = fields.Char(
        string="Shopify Access Token",
        help="Access token for Shopify API authentication.",
        copy=False,
    )

    def action_connect(self):
        self.ensure_one()
        if self.channel_code == 'shopify' and self.shopify_authorization_type == 'self_access':
            self._authenticate_shopify()
        return super().action_connect()

    def action_disconnect(self):
        self.ensure_one()
        if self.channel_code == 'shopify':
            self.shopify_access_token = None
        return super().action_disconnect()

    def action_copy_shopify_app_url(self):
        self.ensure_one()
        url = f"{self.get_base_url()}/odoo/ecommerce.account/{self.id}/shopify/app"
        return {
            'type': 'ir.actions.client',
            'tag': 'copy_shopify_url',
            'params': {
                'url': url,
            }
        }

    def _authenticate_shopify(self):
        try:
            response = shopify_utils_graphql.call_shopify_graphql_query(
                account=self,
                endpoint='shop'
            )
        except ECommerceApiError as ex:
            raise UserError(self.env._(
                "Shopify account is not authenticated: %s", str(ex)
            ))
        if (response.get('shop') or {}).get('name') != self.shopify_store:
            raise UserError(self.env._(
                "Shopify account is not authenticated: 'No shop information received'",
            ))

    def _get_product_url(self, offer):
        if self.channel_code != 'shopify':
            return super()._get_product_url(offer)
        return f"https://admin.shopify.com/store/{self.shopify_store}/products/{offer.ec_product_template_identifier}/variants/{offer.ec_product_identifier}"

    def _fetch_products_from_ecommerce(self):
        if self.channel_code != 'shopify':
            return super()._fetch_products_from_ecommerce()
        updated_at_min_date = (self.last_products_sync + timedelta(seconds=1)).isoformat() + 'Z'
        response = shopify_utils_graphql.call_shopify_graphql_with_pagination(
            account=self,
            endpoint='products',
            params={'updated_at_min': updated_at_min_date}
        )
        return response

    def _fetch_orders_from_ecommerce(self):
        if self.channel_code != 'shopify':
            return super()._fetch_orders_from_ecommerce()
        updated_at_min_date = (self.last_orders_sync + timedelta(seconds=1)).isoformat() + 'Z'
        result = shopify_utils_graphql.call_shopify_graphql_with_pagination(
            account=self,
            endpoint='orders',
            params={'updated_at_min': updated_at_min_date}
        )   # fetch orders which are updated after this sync date.
        return result

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        if self.channel_code != 'shopify':
            return super()._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        response_order = shopify_utils_graphql.call_shopify_graphql_query(
            account=self,
            endpoint='order',
            params={'order_id': ecommerce_order_ref}
        )
        return response_order

    def _fetch_locations_from_ecommerce(self):
        if self.channel_code != 'shopify':
            return super()._fetch_locations_from_ecommerce()
        response = shopify_utils_graphql.call_shopify_graphql_with_pagination(
            account=self,
            endpoint='locations'
        )
        return response

    def _update_pickings_to_ecommerce(self, pickings):
        if self.channel_code != 'shopify':
            return super()._update_pickings_to_ecommerce(pickings)
        for picking in pickings:
            try:
                fulfillment = self._update_picking_to_shopify(picking)
            except ECommerceApiError as error:
                self._post_process_after_picking_update_failed(picking, str(error))
            else:
                self._post_process_after_picking_update_success(picking, fulfillment.get('id'))

    def _update_inventory_to_ecommerce(self, inventory_data):
        if self.channel_code != 'shopify':
            return super()._update_inventory_to_ecommerce(inventory_data)
        response = shopify_utils_graphql.call_shopify_graphql_mutation(
            account=self,
            endpoint='inventorySetQuantities',
            params={'inventory_data': inventory_data}
        )
        return response

    def _update_picking_to_shopify(self, picking):
        response = shopify_utils_graphql.call_shopify_graphql_mutation(
            account=self,
            endpoint='fulfillmentCreate',
            params={'picking': picking}
        )
        return response
