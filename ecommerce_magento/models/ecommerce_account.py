# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models
from odoo.addons.ecommerce_magento import utils as magento_utils
from odoo.addons.ecommerce_magento.const import (
    DELIVERY_CARRIER_MAPPING,
    ORDER_STATE_MAPPING,
)
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError
from odoo.exceptions import UserError


class EcommerceAccount(models.Model):
    _inherit = "ecommerce.account"

    magento_base_url = fields.Char(
        help="Enter the Magento server base url. e.g. https://my-magento-shop.com",
        required_if_channel="magento",
        copy=False,
    )
    magento_auth_method = fields.Selection(selection=[
        ("token", "Admin Credentials"),
        ("oauth", "Integration Credentials"),
    ],
        required_if_channel="magento",
        default="token",
    )
    # 1. Token-based authentication fields
    magento_username = fields.Char(
        copy=False,
    )
    magento_password = fields.Char(
        copy=False,
    )
    magento_access_token = fields.Char(
        copy=False,
    )
    # 2. OAuth-based authentication fields
    magento_oauth_consumer_key = fields.Char(
        copy=False,
    )
    magento_oauth_consumer_secret = fields.Char(
        copy=False,
    )
    magento_oauth_token = fields.Char(
        copy=False,
    )
    magento_oauth_token_secret = fields.Char(
        copy=False,
    )
    magento_admin_pathname = fields.Char(
        help="Admin panel pathname, usually 'admin' or 'admin_XXXXXX'.",
        copy=False,
    )
    # NOTE: from magento's heirarchy levels website/store/storeview, we are using the lowest level (store view) for filtering data
    magento_store_view_code = fields.Char(
        help="Magento Store View Code (e.g. 'default') to fetch data of only that store view.\n"
        "Leave empty to fetch data of all the store views.",
        copy=False,
    )
    magento_website_id = fields.Integer(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    # NOTE: The following field is not needed anywhere yet, but added for completeness.
    # NOTE: 'store_group_id' in magento.
    magento_store_id = fields.Integer(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    # NOTE: 'store_id' in magento.
    magento_store_view_id = fields.Integer(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    magento_website_name = fields.Char(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    magento_store_name = fields.Char(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    magento_store_view_name = fields.Char(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )

    @api.depends("magento_base_url", "magento_store_view_code")
    def _compute_magento_store_values(self):
        for account in self:
            if not account.magento_base_url or not account.magento_store_view_code:
                account.magento_website_id = False
                account.magento_store_id = False
                account.magento_store_view_id = False
                account.magento_website_name = False
                account.magento_store_name = False
                account.magento_store_view_name = False
                continue
            # NOTE: the search params are not available for these endpoints, so filtering objects manually
            try:
                data = magento_utils.make_request(account, "GET", "/store/storeViews")
            except ECommerceApiError as e:
                raise UserError(self.env._("Error fetching store views from Magento: %s", e)) from e
            store_view = next((sv for sv in data if sv["code"] == account.magento_store_view_code), None)
            if not store_view:
                raise UserError(self.env._(
                    "Magento store view code '%s' not found.", account.magento_store_view_code))
            account.magento_website_id = store_view.get("website_id")
            account.magento_store_id = store_view.get("store_group_id")
            account.magento_store_view_id = store_view.get("id")
            account.magento_store_view_name = store_view.get("name")
            try:
                data = magento_utils.make_request(account, "GET", "/store/websites")
                website = next((w for w in data if w["id"] == account.magento_website_id), {})
                account.magento_website_name = website.get("name")
            except ECommerceApiError:
                account.magento_website_name = False
            try:
                data = magento_utils.make_request(account, "GET", "/store/storeGroups")
                store = next((s for s in data if s["id"] == account.magento_store_id), {})
                account.magento_store_name = store.get("name")
            except ECommerceApiError:
                account.magento_store_name = False

    def action_open_ecommerce_accounts(self, channel_code):
        """Override to add default value in context."""
        action = super().action_open_ecommerce_accounts(channel_code)
        if channel_code == "magento":
            action.get("context").update({
                "default_magento_auth_method": "token",
            })
        return action

    def action_connect(self):
        """Override for magento accounts for performing authentication."""
        if self.channel_code == "magento":
            try:
                if self.magento_auth_method == "token":
                    self.magento_access_token = magento_utils.get_admin_access_token(
                        self.magento_base_url,
                        self.magento_username,
                        self.magento_password,
                    )
                else:  # self.magento_auth_method == "oauth"
                    # making a test request to verify credentials
                    magento_utils.make_request(self, "GET", "/orders", params={"searchCriteria[pageSize]": 1})
            except ECommerceApiError as e:
                raise UserError(e) from e
        return super().action_connect()

    def _get_product_url(self, offer):
        """Override for magento accounts to return the admin portal product url."""
        if self.channel_code != "magento":
            return super()._get_product_url(offer)
        if not self.magento_admin_pathname:
            raise UserError(self.env._("Please set the Admin Pathname on the account first."))
        return f"{self.magento_base_url.rstrip('/')}/{self.magento_admin_pathname}/catalog/product/edit/id/{offer.ec_product_identifier}"

    def _fetch_products_from_ecommerce(self):
        """Override for magento accounts to fetch products that are updated after the specified date."""
        if self.channel_code != "magento":
            return super()._fetch_products_from_ecommerce()
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "status",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "eq",
            "searchCriteria[filterGroups][0][filters][0][value]": 1,
            "searchCriteria[filterGroups][1][filters][0][field]": "type_id",
            "searchCriteria[filterGroups][1][filters][0][conditionType]": "in",
            "searchCriteria[filterGroups][1][filters][0][value]": "simple,virtual,downloadable",  # not in "configurable,grouped,bundle"
            "searchCriteria[filterGroups][2][filters][0][field]": "updated_at",
            "searchCriteria[filterGroups][2][filters][0][conditionType]": "from",
            "searchCriteria[filterGroups][2][filters][0][value]": self.last_products_sync.strftime("%Y-%m-%d %H:%M:%S"),
            "fields": "total_count,items[id,name,sku,price,status,type_id,updated_at,extension_attributes[website_ids]]",
        }
        magento_products = magento_utils.make_paginated_request(self, "GET", "/products", params)
        return {
            "products": [{
                "name": product["name"],
                "sku": product["sku"],
                "ec_product_identifier": product["id"],
            } for product in magento_products if (not self.magento_website_id or
                self.magento_website_id in product.get("extension_attributes", {}).get("website_ids", [])
            )],
        }

    def _fetch_locations_from_ecommerce(self):
        """Override for magento accounts to fetch inventory sources."""
        if self.channel_code != "magento":
            return super()._fetch_locations_from_ecommerce()
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "enabled",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "eq",
            "searchCriteria[filterGroups][0][filters][0][value]": "1",
            "fields": "items[name,source_code]",
        }
        magento_locations = magento_utils.make_paginated_request(self, "GET", "/inventory/sources", params)
        return {
            "locations": [{
                "id": location.get("source_code"),
                "name": location.get("name"),
            } for location in magento_locations],
        }

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        """Override for magento accounts to fetch a single order by its Order Reference."""
        if self.channel_code != "magento":
            return super()._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "increment_id",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "eq",
            "searchCriteria[filterGroups][0][filters][0][value]": ecommerce_order_ref,
        }
        magento_orders = magento_utils.make_request(self, "GET", "/orders", params)
        if not magento_orders.get("items"):
            raise UserError(self.env._("Could not find any order with reference %s", ecommerce_order_ref))
        magento_order = magento_orders["items"][0]
        if self.magento_store_id and magento_order.get("store_id") != self.magento_store_view_id:
            raise UserError(self.env._(
                "This order belongs to a different store view than the one set on this ecommerce account."))
        magento_shipments = self._magento_fetch_shipments([magento_order.get("entity_id")])
        return {
            **self._magento_prepare_order_structure(magento_order),
            "fulfillments": [
                self._magento_prepare_picking_structure(shipment_data)
                for shipment_data in magento_shipments
            ],
        }

    def _fetch_orders_from_ecommerce(self):
        """Override for magento accounts to fetch orders that are updated after the specified date."""
        if self.channel_code != "magento":
            return super()._fetch_orders_from_ecommerce()
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "state",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "in",
            "searchCriteria[filterGroups][0][filters][0][value]": "processing,complete,canceled",
            "searchCriteria[filterGroups][1][filters][0][field]": "updated_at",
            "searchCriteria[filterGroups][1][filters][0][conditionType]": "from",
            "searchCriteria[filterGroups][1][filters][0][value]": self.last_orders_sync.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self.magento_store_view_id:
            params.update({
                "searchCriteria[filterGroups][2][filters][0][field]": "store_id",
                "searchCriteria[filterGroups][2][filters][0][conditionType]": "eq",
                "searchCriteria[filterGroups][2][filters][0][value]": self.magento_store_view_id,
            })
        magento_orders = magento_utils.make_paginated_request(self, "GET", "/orders", params)
        if not magento_orders:
            return {"orders": []}
        magento_shipments = self._magento_fetch_shipments(
            [order_data.get("entity_id") for order_data in magento_orders])
        shipments_by_order = defaultdict(list)
        for shipment in magento_shipments:
            shipments_by_order[shipment.get("order_id")].append(shipment)
        return {
            "orders": [{
                **self._magento_prepare_order_structure(order_data),
                "fulfillments": [
                    self._magento_prepare_picking_structure(shipment_data)
                    for shipment_data in shipments_by_order.get(order_data.get("entity_id"), [])
                ],
            } for order_data in magento_orders]
        }

    def _update_pickings_to_ecommerce(self, pickings):
        """Override for magento accounts to create shipments from given pickings."""
        if self.channel_code != "magento":
            return super()._update_pickings_to_ecommerce(pickings)
        failed_pickings_count = 0
        for picking in pickings:
            payload = {
                "notify": True,
                "appendComment": True,
                "comment": {
                    "comment": "Order shipped and is on its way to you!",
                    "is_visible_on_front": 1,
                },
            }
            payload["items"] = [{
                "qty": int(move.quantity),
                "order_item_id": int(move.sale_line_id.ecommerce_line_identifier),
            } for move in picking.move_ids if (
                move.sale_line_id and move.sale_line_id.ecommerce_line_identifier and move.quantity > 0)]
            if not payload["items"]:
                self._post_process_after_picking_update_failed(picking, "No moves found in delivery that can be sent.")
                continue
            if picking.carrier_id or picking.carrier_tracking_ref:
                delivery_carrier_odoo_to_magento = {v: k for k, v in DELIVERY_CARRIER_MAPPING.items()}
                payload["tracks"] = [{
                    "carrier_code": delivery_carrier_odoo_to_magento.get(picking.carrier_id.name, "custom"),
                    "title": picking.carrier_id.name or "Custom Delivery",
                    "track_number": picking.carrier_tracking_ref,
                }]
            if ec_location := self.ecommerce_location_ids.filtered(lambda el: el.matched_location_id == picking.location_id):
                payload["arguments"] = {
                    "extension_attributes": {
                        "source_code": ec_location.ecommerce_location_identifier,
                    },
                }
            try:
                shipment_id = magento_utils.make_request(
                    self, "POST", f"/order/{picking.sale_id.ecommerce_order_identifier}/ship", payload=payload)
                self._post_process_after_picking_update_success(picking, shipment_id)
            except ECommerceApiError as e:
                failed_pickings_count += 1
                self._post_process_after_picking_update_failed(picking, str(e))
        return not bool(failed_pickings_count)

    def _update_inventory_to_ecommerce(self, inventory_data):
        """Override for magento accounts to update stock of given products."""
        if self.channel_code != "magento":
            return super()._update_inventory_to_ecommerce(inventory_data)
        payload = {
            "sourceItems": [{
                "sku": inventory.get("offer").sku,
                "source_code": inventory.get("location").ecommerce_location_identifier,
                "quantity": float(inventory.get("quantity")),
                "status": 1 if inventory.get("quantity") > 0 else 0,
            } for inventory in inventory_data]
        }
        return magento_utils.make_request(self, "POST", "/inventory/source-items", payload=payload)

    def _magento_fetch_shipments(self, magento_order_ids):
        """Fetch shipments for the given Magento orders."""
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "order_id",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "in",
            "searchCriteria[filterGroups][0][filters][0][value]": ",".join(str(order_id) for order_id in magento_order_ids),
        }
        return magento_utils.make_paginated_request(self, "GET", "/shipments", params)

    @api.model
    def _magento_prepare_partner_structure(self, address_data):
        """Prepare the common partner structure from the given Magento address."""
        streets = address_data.get("street") or []
        return {
            "name": f"{address_data.get('firstname', '').strip()} {address_data.get('lastname', '').strip()}",
            "email": address_data.get("email"),
            "phone": address_data.get("telephone"),
            "street": streets[0] if streets else "",
            "street2": streets[1] if len(streets) > 1 else "",
            "zip": address_data.get("postcode"),
            "city": address_data.get("city"),
            "state_name": address_data.get("region"),
            "state_code": address_data.get("region_code"),
            "country_code": address_data.get("country_id"),
            "is_company": bool(address_data.get("company_name")),
            "vat": address_data.get("vat_id"),
        }

    @api.model
    def _magento_prepare_order_structure(self, order_data):
        """Prepare the common order structure from the given Magento order."""
        billing_address = order_data.get("billing_address")
        shipping_address = order_data.get("extension_attributes", {}).get("shipping_assignments", [{}])[0].get("shipping", {}).get("address")
        return {
            "id": order_data.get("entity_id"),
            "reference": order_data.get("increment_id"),
            "create_date": order_data.get("created_at"),
            "write_date": order_data.get("updated_at"),
            "date_order": order_data.get("created_at"),
            "currency_code": order_data.get("base_currency_code"),  # ---> global_currency_code ---> store_currency_code ---> order_currency_code
            "status": ORDER_STATE_MAPPING.get(order_data.get("state")),
            "customer_id": order_data.get("customer_id"),
            "billing_address": self._magento_prepare_partner_structure(billing_address) if billing_address else None,
            "shipping_address": self._magento_prepare_partner_structure(shipping_address) if shipping_address else None,
            "order_lines": [{
                "id": item.get("item_id"),
                "product_data": {
                    "name": item.get("name"),
                    "sku": item.get("sku"),
                    "ec_product_identifier": item.get("product_id"),
                },
                "qty_ordered": item.get("qty_ordered"),
                "price_unit": item.get("base_price"),
                # NOTE: "price_unit_incl_tax": item.get("base_price_incl_tax"),
                "tax_amount": item.get("base_tax_amount"),
                # NOTE: "tax_percent": item.get("tax_percent"),
                "discount_amount": item.get("base_discount_amount"),
                # NOTE: "discount_percent": item.get("discount_percent"),
                # NOTE: "discount_invoiced": item.get("base_discount_invoiced"),
                "discount_tax": item.get("base_discount_tax_compensation_amount"),
                "price_subtotal": item.get("base_row_total") + item.get("base_discount_amount"),
                # NOTE: "price_total": item.get("base_row_total_incl_tax"),
            } for item in order_data.get("items", []) if item.get("product_type") in ["simple", "virtual", "grouped", "downloadable"]],  # NOTE: same as: not in ["configurable", "bundle"]
            # NOTE: the same shipping data is also present at: order_data.get("extension_attributes", {}).get("shipping_assignments", [{}])[0].get("shipping", {}).get("total", {})
            "shipping_lines": [{
                "id": f"shipping_cost_for_{order_data.get('entity_id')}",
                "shipping_code": order_data.get("shipping_description"),
                "price_unit": order_data.get("base_shipping_amount"),
                "tax_amount": order_data.get("base_shipping_tax_amount"),
                "discount_amount": order_data.get("base_shipping_discount_amount"),
                "discount_tax": order_data.get("base_shipping_discount_tax_compensation_amnt"),
            }] if order_data.get("base_shipping_amount", 0) > 0 else [],
        }

    @api.model
    def _magento_prepare_picking_structure(self, shipment_data):
        """Prepare the common fulfillment structure from the given Magento shipment."""
        # NOTE: one shipment can have multiple tracking numbers. considering only first one for now
        track = (shipment_data.get("tracks") or [{}])[0]
        carrier_code = track.get("carrier_code")
        carrier_title = track.get("title")
        if not track or (carrier_code == "custom" and not carrier_title):
            carrier_name = "fixed"  # Standard delivery
        else:
            carrier_name = DELIVERY_CARRIER_MAPPING.get(carrier_code) or carrier_title
        return {
            "ecommerce_picking_identifier": shipment_data.get("entity_id"),
            "location_id": shipment_data.get("extension_attributes", {}).get("source_code"),
            "line_items": [{
                "ecommerce_move_id": item.get("item_id"),
                "ecommerce_line_identifier": item.get("order_item_id"),
                "quantity": item.get("qty"),
            } for item in shipment_data.get("items", []) if bool(item.get("qty"))],
            "carrier_id": carrier_name,
            "tracking_number": track.get("track_number"),
        }
