# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.ecommerce_magento import const, utils as magento_utils
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError


class EcommerceAccount(models.Model):
    _inherit = "ecommerce.account"

    magento_base_url = fields.Char(
        help="Enter the Magento server base url. e.g. https://my-magento-shop.com",
        required_if_channel="magento",
    )
    magento_admin_pathname = fields.Char(
        help="Admin panel pathname, usually 'admin' or 'admin_XXXXXX'.",
        copy=False,
    )
    magento_auth_method = fields.Selection(selection=[
        ("token", "Admin Credentials"),
        ("oauth", "Integration Credentials"),
    ],
        compute="_compute_magento_auth_method",
        store=True,
        required_if_channel="magento",
    )
    magento_admin_username = fields.Char(
        copy=False,
    )
    magento_admin_password = fields.Char(
        copy=False,
    )
    magento_admin_access_token = fields.Char(
        copy=False,
    )
    magento_oauth_consumer_key = fields.Char(
        copy=False,
    )
    magento_oauth_consumer_secret = fields.Char(
        copy=False,
    )
    magento_oauth_access_token = fields.Char(
        copy=False,
    )
    magento_oauth_access_token_secret = fields.Char(
        copy=False,
    )
    magento_store_view_code = fields.Char(
        help="Magento Store View Code (e.g. 'default') to fetch data of only that store view.\n"
        "Leave empty to fetch data of all websites, stores and store views.",
        copy=False,
    )
    magento_website_id = fields.Integer(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    # NOTE: 'store_group_id' in magento
    magento_store_id = fields.Integer(
        compute="_compute_magento_store_values",
        store=True,
        copy=False,
    )
    # NOTE: 'store_id' in magento
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

    @api.depends("ecommerce_channel_id")
    def _compute_magento_auth_method(self):
        for account in self:
            if account.channel_code == "magento":
                account.magento_auth_method = account.magento_auth_method or "token"
            else:
                account.magento_auth_method = False

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
            try:
                data = magento_utils.make_request(account, "GET", "/store/storeViews")
            except ECommerceApiError as e:
                raise UserError(self.env._("Error fetching store views: %s", e))
            store_view = next((sv for sv in data if sv["code"] == account.magento_store_view_code), None)
            if not store_view:
                raise UserError(self.env._(
                    "Magento store view code '%s' not found.", account.magento_store_view_code))
            account.magento_website_id = store_view["website_id"]
            account.magento_store_id = store_view["store_group_id"]
            account.magento_store_view_id = store_view["id"]
            account.magento_store_view_name = store_view["name"]
            try:
                data = magento_utils.make_request(account, "GET", "/store/storeGroups")
                store = next((s for s in data if s["id"] == account.magento_store_id), {})
                account.magento_store_name = store["name"]
            except ECommerceApiError as e:
                raise UserError(self.env._("Error fetching store groups: %s", e))
            try:
                data = magento_utils.make_request(account, "GET", "/store/websites")
                website = next((w for w in data if w["id"] == account.magento_website_id), {})
                account.magento_website_name = website["name"]
            except ECommerceApiError as e:
                raise UserError(self.env._("Error fetching websites: %s", e))

    def action_connect(self):
        """Override for magento accounts for performing authentication."""
        if self.channel_code == "magento":
            try:
                if self.magento_auth_method == "token":
                    self.magento_admin_access_token = magento_utils.get_admin_access_token(
                        self.magento_base_url,
                        self.magento_admin_username,
                        self.magento_admin_password,
                    )
                else:  # self.magento_auth_method == "oauth"
                    # making a test request to verify credentials
                    magento_utils.make_request(self, "GET", "/orders", {"searchCriteria[pageSize]": 1})
            except ECommerceApiError as e:
                raise UserError(e)
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
            "searchCriteria[filterGroups][1][filters][0][value]": "simple,virtual,downloadable",  # equivalent to: not in "configurable,grouped,bundle"
            "searchCriteria[filterGroups][2][filters][0][field]": "updated_at",
            "searchCriteria[filterGroups][2][filters][0][conditionType]": "from",
            "searchCriteria[filterGroups][2][filters][0][value]": self.last_products_sync.strftime("%Y-%m-%d %H:%M:%S"),
            "fields": "total_count,items[id,name,sku,price,status,type_id,updated_at,extension_attributes[website_ids]]",
        }
        magento_products = magento_utils.make_paginated_request(self, "GET", "/products", params)
        return {
            "products": [
                self._magento_prepare_product_structure(magento_product)
                for magento_product in magento_products
                if not self.magento_website_id or self.magento_website_id in
                magento_product.get("extension_attributes", {}).get("website_ids", [])
            ],
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
                "id": magento_location["source_code"],
                "name": magento_location["name"],
            } for magento_location in magento_locations],
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
        if not magento_orders["items"]:
            raise UserError(self.env._("Could not find any order with reference %s", ecommerce_order_ref))
        magento_order = magento_orders["items"][0]
        if self.magento_store_id and magento_order["store_id"] != self.magento_store_view_id:
            raise UserError(self.env._(
                "This order belongs to a different store view than the one set on this ecommerce account."))
        orders_related_resources = self._magento_fetch_orders_related_resources([str(magento_order["entity_id"])])
        magento_shipments = orders_related_resources["shipments"]
        return self._magento_prepare_order_structure(magento_order, magento_shipments)

    def _fetch_orders_from_ecommerce(self):
        """Override for magento accounts to fetch orders that are updated after the specified date."""
        if self.channel_code != "magento":
            return super()._fetch_orders_from_ecommerce()
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "updated_at",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "from",
            "searchCriteria[filterGroups][0][filters][0][value]": self.last_orders_sync.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self.magento_store_view_id:
            params.update({
                "searchCriteria[filterGroups][1][filters][0][field]": "store_id",
                "searchCriteria[filterGroups][1][filters][0][conditionType]": "eq",
                "searchCriteria[filterGroups][1][filters][0][value]": self.magento_store_view_id,
            })
        magento_orders = magento_utils.make_paginated_request(self, "GET", "/orders", params)
        if not magento_orders:
            return {"orders": []}
        magento_order_ids = [str(order_data["entity_id"]) for order_data in magento_orders]
        orders_related_resources = self._magento_fetch_orders_related_resources(magento_order_ids)
        shipments_by_order = defaultdict(list)
        for shipment in orders_related_resources["shipments"]:
            shipments_by_order[shipment["order_id"]].append(shipment)
        return {
            "orders": [
                self._magento_prepare_order_structure(
                    order_data,
                    shipments_by_order.get(order_data["entity_id"]),
                ) for order_data in magento_orders
            ],
        }

    def _update_pickings_to_ecommerce(self, pickings):
        """Override for magento accounts to create shipments from given pickings."""
        if self.channel_code != "magento":
            return super()._update_pickings_to_ecommerce(pickings)
        for picking in pickings:
            payload = {
                "items": [],
                "notify": True,
                "appendComment": True,
                "comment": {
                    "comment": "Your order has been shipped.",
                    "is_visible_on_front": 1,
                },
            }
            for move in picking.move_ids:
                if move.sale_line_id.ecommerce_line_identifier and move.quantity > 0:
                    payload["items"].append({
                        "order_item_id": int(move.sale_line_id.ecommerce_line_identifier),
                        "qty": move.quantity,
                    })
            if not payload["items"]:
                self._post_process_after_picking_update_failed(picking, self.env._(
                    "No moves found in delivery that can be sent to Magento."))
                continue
            if picking.carrier_id and picking.carrier_tracking_ref:
                delivery_carrier_odoo_to_magento = {v: k for k, v in const.DELIVERY_CARRIER_MAPPING.items()}
                payload["tracks"] = [{
                    "carrier_code": delivery_carrier_odoo_to_magento.get(picking.carrier_id.name, "custom"),
                    "title": picking.carrier_id.name or "Custom Delivery",
                    "track_number": picking.carrier_tracking_ref,
                }]
            if ec_location := self.ecommerce_location_ids.filtered(
                lambda el: el.matched_location_id == picking.location_id):
                payload["arguments"] = {
                    "extension_attributes": {
                        "source_code": ec_location[0].ecommerce_location_identifier,
                    },
                }
            shipment_id = None
            try:
                shipment_id = magento_utils.make_request(
                    self, "POST", f"/order/{picking.sale_id.ecommerce_order_identifier}/ship", payload=payload)
                self._post_process_after_picking_update_success(picking, shipment_id)
            except ECommerceApiError as e:
                self._post_process_after_picking_update_failed(picking, str(e))
                continue
            try:
                # NOTE: according to API docs, /shipment/{id} is supposed to return the shipment object but it actually returns a list of shipment items
                shipment_items = magento_utils.make_paginated_request(self, "GET", f"/shipment/{shipment_id}")
            except ECommerceApiError as e:
                self.log_xml(
                    message="Failed to fetch shipment items for shipment %s after creating it on Magento: %s" % (shipment_id, str(e)),
                    func='_update_pickings_to_ecommerce',
                    type='server',
                )
                continue
            for shipment_item in shipment_items:
                move = picking.move_ids.filtered(
                    lambda move: move.sale_line_id.ecommerce_line_identifier == str(shipment_item["order_item_id"])
                )[0]
                move.ecommerce_move_identifier = shipment_item["entity_id"]
                if move.quantity != shipment_item["qty"]:
                    picking.message_post(body=self.env._(
                        "The Magento shipment item with ID '%s' linked to '%s' move was created with a "
                        "different quantity than the move.", shipment_item["entity_id"], move.reference)
                    )

    def _update_inventory_to_ecommerce(self, inventory_data):
        """Override for magento accounts to update stock of given products."""
        if self.channel_code != "magento":
            return super()._update_inventory_to_ecommerce(inventory_data)
        payload = {
            "sourceItems": [{
                "sku": inventory["offer"].sku,
                "source_code": inventory["location"].ecommerce_location_identifier,
                "quantity": inventory["quantity"],
                "status": 1 if inventory["quantity"] > 0 else 0,
            } for inventory in inventory_data]
        }
        return magento_utils.make_request(self, "POST", "/inventory/source-items", payload=payload)

    def _magento_fetch_orders_related_resources(self, magento_order_ids):
        """Fetch shipments for the given Magento orders."""
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "order_id",
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "in",
            "searchCriteria[filterGroups][0][filters][0][value]": ",".join(magento_order_ids),
        }
        return {
            "shipments": magento_utils.make_paginated_request(self, "GET", "/shipments", params),
        }

    @api.model
    def _magento_prepare_product_structure(self, product_data, from_order=False):
        """Prepare the common product structure from the given Magento product."""
        return {
            "name": product_data["name"],
            "sku": product_data["sku"],
            "ec_product_identifier": (from_order and product_data["product_id"]) or product_data["id"],
        }

    @api.model
    def _magento_prepare_partner_structure(self, address_data):
        """Prepare the common partner structure from the given Magento address."""
        streets = address_data.get("street") or []
        return {
            "name": " ".join(filter(None, [address_data.get("prefix"), address_data.get("firstname"),
                address_data.get("middlename"), address_data.get("lastname"), address_data.get("suffix")])),
            "email": address_data.get("email"),
            "phone": address_data.get("telephone"),
            "street": streets[0] if streets else "",
            "street2": streets[1] if len(streets) > 1 else "",
            "zip": address_data.get("postcode"),
            "city": address_data.get("city"),
            "state_name": address_data.get("region"),
            "state_code": address_data.get("region_code"),
            "country_code": address_data.get("country_id"),
            "is_company": bool(address_data.get("company")),
            "vat": address_data.get("vat_id"),
        }

    @api.model
    def _magento_prepare_order_structure(self, order_data, shipments_data):
        """Prepare the common order structure from the given Magento order."""
        billing_address = order_data.get("billing_address")
        shipping_address = order_data.get("extension_attributes", {}).get("shipping_assignments", [{}])[0].get("shipping", {}).get("address")
        net_paid = order_data.get("base_total_paid", 0) - order_data.get("base_total_refunded", 0)
        return {
            "id": order_data["entity_id"],
            "reference": order_data["increment_id"],
            "create_date": order_data["created_at"],
            "write_date": order_data["updated_at"],
            "date_order": order_data["created_at"],
            "currency_code": order_data["base_currency_code"],  # ---> global_currency_code ---> store_currency_code ---> order_currency_code
            "status": const.ORDER_STATE_MAPPING.get(order_data["state"]),
            "financial_status": net_paid >= order_data["base_grand_total"] and "PAID",
            "customer_id": order_data["customer_id"],
            "billing_address": self._magento_prepare_partner_structure(billing_address) if billing_address else None,
            "shipping_address": self._magento_prepare_partner_structure(shipping_address) if shipping_address else None,
            "order_lines": [{
                "id": item["item_id"],
                "product_data": self._magento_prepare_product_structure(item, True),
                "qty_ordered": item["qty_ordered"],
                "price_unit": item["base_price_incl_tax"] if self.tax_included else item["base_price"],
                "tax_amount": item["base_tax_amount"],
                "discount_amount": item["base_discount_amount"],
                "discount_tax": item["base_discount_tax_compensation_amount"],
                "price_subtotal": (
                    item["base_row_total_incl_tax"] if self.tax_included else item["base_row_total"]
                ) + item["base_discount_amount"],
            } for item in order_data["items"] if item.get("product_type") in
                ["simple", "virtual", "grouped", "downloadable"]],  # NOTE: same as: not in ["configurable", "bundle"]
            # NOTE: the same shipping data is also present at: order_data.get("extension_attributes", {}).get("shipping_assignments", [{}])[0].get("shipping", {}).get("total", {})
            "shipping_lines": [{
                "id": f"shipping_cost_for_{order_data['entity_id']}",
                "shipping_code": order_data["shipping_description"],
                "price_unit": order_data["base_shipping_amount"],
                "tax_amount": order_data["base_shipping_tax_amount"],
                "discount_amount": order_data["base_shipping_discount_amount"],
                "discount_tax": order_data["base_shipping_discount_tax_compensation_amnt"],
            }] if order_data["base_shipping_amount"] > 0 else [],
            "fulfillments": [
                self._magento_prepare_picking_structure(shipment_data)
                for shipment_data in shipments_data
            ] if shipments_data else [],
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
            carrier_name = const.DELIVERY_CARRIER_MAPPING.get(carrier_code) or carrier_title
        return {
            "ecommerce_picking_identifier": shipment_data["entity_id"],
            "location_id": shipment_data.get("extension_attributes", {}).get("source_code"),
            "line_items": [{
                "ecommerce_move_identifier": item["entity_id"],
                "ecommerce_line_identifier": item["order_item_id"],
                "quantity": item["qty"],
            } for item in shipment_data.get("items", []) if bool(item["qty"])],
            "carrier_id": carrier_name,
            "tracking_number": track.get("track_number"),
        }
