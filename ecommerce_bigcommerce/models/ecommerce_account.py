# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.ecommerce_bigcommerce import const
from odoo.addons.ecommerce_bigcommerce.utils.bigcommerce_request import (
    BigcommerceRequest,
)
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError
from odoo.exceptions import UserError

bigcommerce_request_handler = BigcommerceRequest()


class ecommerceAccount(models.Model):
    _inherit = 'ecommerce.account'

    bigcommerce_access_token = fields.Char(
        string="BigCommerce Access Token",
        help="BigCommerce Access Token for BigCommerce API authentication.",
        required_if_channel="bigcommerce",
        copy=False
    )
    bigcommerce_store_hash = fields.Char(
        string="BigCommerce Store Hash",
        help="BigCommerce store hash for BigCommerce  API authentication.",
        required_if_channel="bigcommerce",
        copy=False
    )

    def action_connect(self):
        self.ensure_one()
        if self.channel_code == 'bigcommerce' and self.bigcommerce_access_token and self.bigcommerce_store_hash:
            self._authenticate_bigcommerce()
        return super().action_connect()

    def _authenticate_bigcommerce(self):
        response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            version='v2',
            endpoint='store',
            method='GET'
        )
        if response.get('errors'):
            raise UserError(
                self.env._("Failed to connect BigCommerce account: %s", response.get('errors'))
            )
        is_valid_response = response and response.get('id') and response.get('id') == self.bigcommerce_store_hash
        if not is_valid_response:
            raise UserError(
                self.env._("Failed to connect BigCommerce account: No shop information received.")
            )

    def _fetch_products_from_ecommerce(self):
        if self.channel_code != 'bigcommerce':
            return super()._fetch_products_from_ecommerce()
        params = {
            'include': 'variants',
            'date_modified:min': self.last_products_sync.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'is_visible': 'true',
        }
        response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            version='v3',
            endpoint='catalog/products',
            method='GET',
            params=params
        )
        if response.get('errors'):
            result = {'error': response.get('errors')}
            return result

        if not (response and "data" in response):
            raise ECommerceApiError("Unexpected Error, something went wrong.")

        response_products = []
        for bigcommerce_product in response.get('data'):
            variants = bigcommerce_product.get('variants', [])
            has_variants = (len(variants) > 1 or (variants and len(variants[0].get('option_values', [])) > 0))
            if has_variants:
                for variant in variants:
                    option_values = variant.get('option_values', [])
                    variant_name_parts = []

                    for option_value in option_values:
                        label = option_value.get('label', '')
                        if label:
                            variant_name_parts.append(label)

                    if variant_name_parts:
                        variant_name = f"{bigcommerce_product['name']} ({' '.join(variant_name_parts)})"
                    else:
                        variant_name = f"{bigcommerce_product['name']}"

                    response_products.append({
                        'name': variant_name,
                        'ec_product_identifier': str(variant['id']),
                        'sku': variant.get('sku', ''),
                        'ec_product_template_identifier': str(bigcommerce_product['id'])
                    })
            else:
                response_products.append({
                    'name': bigcommerce_product['name'],
                    # 'ec_product_identifier': str(bigcommerce_product['id']),
                    'sku': bigcommerce_product.get('sku', ''),
                    # 'identifier_type': 'template',
                    'ec_product_template_identifier': str(bigcommerce_product['id'])
                })

        return {'products': response_products}

    def _fetch_locations_from_ecommerce(self):
        if self.channel_code != 'bigcommerce':
            return super()._fetch_locations_from_ecommerce()
        response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            version='v3',
            endpoint='inventory/locations',
            method='GET',
            params={'is_active': 'true'}
        )
        if response.get('errors'):
            result = {'error': response.get('error')}
            return result
        is_valid_response = response and 'data' in response
        if not is_valid_response:
            result = {'error': "Unexpected error, something went wrong."}
            return result
        response_location = []
        for bigcommerce_location in response.get('data', []):
            response_location.append({
                'id': bigcommerce_location.get('id', ''),
                'name': bigcommerce_location.get('label', '')
            })
        return {'locations': response_location}

    def _fetch_orders_from_ecommerce(self):
        if self.channel_code != 'bigcommerce':
            return super()._fetch_orders_from_ecommerce()
        params = {
            'min_date_modified': self.last_orders_sync.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'include': 'consignments, consignments.line_items'
        }
        response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='GET',
            version='v2',
            endpoint='orders',
            params=params
        )
        if isinstance(response, dict) and 'errors' in response:
            raise ECommerceApiError(response.get('errors'))
        is_valid_response = response and len(response) > 0
        if not is_valid_response:
            return {'orders': []}
        result = {'orders': []}
        for order in response:
            order_data = self._prepare_order_structure(order)
            if not order_data:
                continue
            result['orders'].append(order_data)
        return result

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        if self.channel_code != 'bigcommerce':
            return super()._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        order = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='GET',
            version='v2',
            endpoint=f'orders/{ecommerce_order_ref}',
            params={'include': 'consignments, consignments.line_items'},
        )
        if isinstance(order, dict) and 'errors' in order:
            raise ECommerceApiError(order.get('errors'))
        order_data = self._prepare_order_structure(order)
        return order_data

    def _prepare_order_structure(self, order):
        """ Prepare order structure for BigCommerce order creation """
        if order.get('status_id', 0) == 0:
            return {}
        billing_address = order.get('billing_address', {})
        shipping_address = None
        consignments = order.get('consignments', [])
        order_status = 'Deleted' if order.get('is_deleted', False) else order.get('status', '')
        if consignments:
            shipping_list = consignments[0].get('shipping', [])
            if shipping_list:
                shipping = shipping_list[0]
                shipping_address = {
                    'name': f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
                    'email': shipping.get('email', ''),
                    'phone': shipping.get('phone', ''),
                    'street': shipping.get('street_1', ''),
                    'street2': shipping.get('street_2', ''),
                    'zip': shipping.get('zip', ''),
                    'city': shipping.get('city', ''),
                    'state_code': shipping.get('state', ''),
                    'country_code': shipping.get('country_iso2', ''),
                    'company_name': shipping.get('company', '')
                }
        order_data = {
            'id': str(order['id']),
            'status': const.ORDER_STATUS_MAPPING.get(order_status),
            'customer_id': order.get('customer_id'),
            'create_date': order.get('date_created'),
            'update_date': order.get('date_modified'),
            "date_order": order.get("date_created"),
            'currency_code': order.get('currency_code'),
            'fulfillments': self._prepare_fulfillment(order),
            'shipping_price': str(order.get('base_shipping_cost', 0)),
            # "fulfillment_type": "FBMe",
            'shipping_tax_amount': str(order.get('shipping_cost_tax', 0)),
            'billing_address': {
                'name': f"{billing_address.get('first_name', '')} {billing_address.get('last_name', '')}".strip(),
                'email': billing_address.get('email', ''),
                'phone': billing_address.get('phone', ''),
                'street': billing_address.get('street_1', ''),
                'street2': billing_address.get('street_2', ''),
                'zip': billing_address.get('zip'),
                'city': billing_address.get('city'),
                'state_code': billing_address.get('state'),
                'country_code': shipping.get('country_iso2', ''),
                'company_name': billing_address.get('company')
            } if billing_address else None,
            'other_address': [],
            'order_lines': self._prepare_order_lines(order),
            'shipping_lines': self._prepare_shipping_lines(order),
            'shipping_address': shipping_address,
            'location_id': "1",  # BigCommerce API does not provide location_id in order consignments
        }
        return order_data

    def _prepare_fulfillment(self, order):
        fulfillments = []
        shipments = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='GET',
            version='v2',
            endpoint=f'orders/{order["id"]}/shipments'
        ) or []

        if not shipments:
            return False

        # Create shipping address lookup from consignments
        shipping_lookup = {}
        for consignment in order.get('consignments', []):
            for shipping in consignment.get('shipping', []):
                shipping_lookup[shipping.get('id')] = shipping

        # Get all shipping addresses that have shipments
        shipped_addresses = {shipment.get('order_address_id') for shipment in shipments}

        # Check if any shipping address has no shipments - return False if so
        all_shipping_addresses = {shipping.get('id') for consignment in order.get('consignments', []) for shipping in consignment.get('shipping', [])}

        # If any shipping address has no shipments, return False
        if not shipped_addresses or shipped_addresses != all_shipping_addresses:
            return False

        # Create one fulfillment per shipment
        for shipment in shipments:
            order_address_id = shipment.get('order_address_id')
            shipping_details = shipping_lookup.get(order_address_id)

            # Skip if we can't find shipping details
            if not shipping_details:
                continue

            data = {
                'ecommerce_picking_identifier': str(shipment.get('id')),
                'order_id': str(order.get('id')),
                'shipping_address': {
                    'name': f"{shipping_details.get('first_name', '')} {shipping_details.get('last_name', '')}".strip(),
                    'email': shipping_details.get('email', ''),
                    'phone': shipping_details.get('phone', ''),
                    'street': shipping_details.get('street_1', ''),
                    'street2': shipping_details.get('street_2', ''),
                    'zip': shipping_details.get('zip', ''),
                    'city': shipping_details.get('city', ''),
                    'state_code': shipping_details.get('state', ''),
                    'country_code': shipping_details.get('country_iso2', '')
                },
                "location_id": "1",  # BigCommerce API does not provide location_id in order consignments
                'tracking_number': shipment.get('tracking_number', ''),
                'carrier_id': shipment.get('shipping_provider', ''),
                'line_items': []
            }

            # Only add products that are actually in THIS shipment
            shipment_product_ids = {
                item.get('order_product_id') for item in shipment.get('items', [])}

            for item in shipment.get('items', []):
                order_product_id = item.get('order_product_id')

                # Find corresponding product details from consignment
                consignment_item = None
                for consignment_line_item in shipping_details.get('line_items', []):
                    if consignment_line_item.get('id') == order_product_id:
                        consignment_item = consignment_line_item
                        break

                # Only include if this product is actually in this shipment
                if order_product_id in shipment_product_ids:
                    line_item = {
                        'ecommerce_line_identifier': order_product_id,
                        'ecommerce_move_identifier': order_product_id,
                        'fulfillment_line_id': order_product_id,
                        'quantity': item.get('quantity'),
                        'product_id': item.get('product_id'),
                        'variant_id': item.get('variant_id'),
                        'sku': item.get('sku'),
                        'qty_shipped': item.get('quantity', 0),
                    }

                    # Enrich with consignment data if available and missing in shipment
                    if consignment_item:
                        if not line_item['sku']:
                            line_item['sku'] = consignment_item.get('sku')
                        if not line_item['variant_id']:
                            line_item['variant_id'] = consignment_item.get(
                                'variant_id')
                        if not line_item['product_id']:
                            line_item['product_id'] = consignment_item.get(
                                'product_id')

                    data['line_items'].append(line_item)

            # Only add fulfillment if it has line items
            if data['line_items']:
                fulfillments.append(data)

        return fulfillments if fulfillments else False

    def _prepare_order_lines(self, order):
        order_lines = []
        for consignment in order.get('consignments', []):
            for shipping in consignment.get('shipping', []):
                for order_line in shipping.get('line_items', []):
                    total_discount = 0.0
                    if order_line.get('applied_discounts', []):
                        for discount in order_line.get('applied_discounts', []):
                            total_discount += float(discount.get('amount', 0.0))
                    tax_amount = float(order_line.get('total_inc_tax')) - float(order_line.get('total_ex_tax'))
                    subtotal_tax = order_line.get('total_tax')
                    discount_tax = float(tax_amount) - float(subtotal_tax)
                    order_lines.append({
                        'id': str(order_line.get('id')),
                        'description': order_line.get('name'),
                        'product_data': {
                            'name': order_line.get('name'),
                            'sku': order_line.get('sku'),
                            'ec_product_identifier': order_line.get('product_id'),
                        },
                        'qty_ordered': order_line.get('quantity'),
                        'qty_shipped': order_line.get('quantity_shipped'),
                        'qty_refunded': order_line.get('quantity_refunded'),
                        'price_unit': order_line.get('price_ex_tax'),
                        'price_incl_tax': order_line.get('price_inc_tax'),
                        'unit_price_excluding_tax': order_line.get('price_ex_tax'),
                        'price_subtotal': order_line.get('total_ex_tax'),
                        'price_total': order_line.get('total_inc_tax'),
                        'tax_amount': tax_amount,
                        'discount_amount': total_discount,
                        'discount_tax': discount_tax
                    })
        return order_lines

    def _prepare_shipping_lines(self, order):
        shipping_lines = []
        for consignment in order.get('consignments', []):
            for shipping in consignment.get('shipping', []):
                if shipping.get('base_cost', 0):
                    shipping_lines.append({
                        'id': f"bigc_ship_{shipping.get('id')}",
                        'description': shipping.get('shipping_method', ''),
                        'shipping_code': shipping.get('shipping_method', ''),
                        'price_unit': float(shipping.get('base_cost', 0.0)) + float(shipping.get('base_handling_cost', 0.0)),
                        'tax_amount': float(shipping.get('cost_tax', 0.0)) + float(shipping.get('handling_cost_tax', 0.0))
                    })
        return shipping_lines

    def _update_inventory_to_ecommerce(self, inventory_data):
        if self.channel_code != 'bigcommerce':
            return super()._update_inventory_to_ecommerce(inventory_data)

        MAX_BATCH = 2000

        # Convert inventory_data into BigCommerce items
        items = []
        for record in inventory_data:
            offer = record.get('offer')
            location = record.get('location')
            quantity = record.get('quantity', 0)
            # Decide whether to send product_id or variant_id
            if offer.ec_product_identifier and offer.ec_product_identifier != offer.ec_product_template_identifier:
                item = {
                    "variant_id": int(offer.ec_product_identifier),
                    "location_id": int(location.ecommerce_location_identifier),
                    "quantity": int(quantity),
                }
            else:
                item = {
                    "product_id": int(offer.ec_product_template_identifier),
                    "location_id": int(location.ecommerce_location_identifier),
                    "quantity": int(quantity),
                }

            items.append(item)

        # Split into chunks of 2000
        for i in range(0, len(items), MAX_BATCH):
            batch = items[i:i + MAX_BATCH]
            payload = {
                "reason": "Absolute adjustment reason",
                "items": batch,
            }

            response = bigcommerce_request_handler.request(
                ecommerce_account=self,
                version='v3',
                endpoint='inventory/adjustments/absolute',
                method='PUT',
                payload=payload
            )
            if response.get('errors'):
                raise ECommerceApiError(response.get('errors'))
                # return {'error': response.get('errors'), 'batch': i // MAX_BATCH + 1}

            if not response or 'transaction_id' not in response:
                raise ECommerceApiError("Unexpected error, something went wrong")
                # return {'error': "Unexpected error, something went wrong", 'batch': i // MAX_BATCH + 1}

        return {}

    def _get_product_url(self, offer):
        if self.channel_code != 'bigcommerce':
            return super()._get_product_url(offer)
        store_hash = self.bigcommerce_store_hash
        product_id = offer.ec_product_template_identifier or offer.ec_product_identifier
        return f"https://store-{store_hash}.mybigcommerce.com/manage/products/edit/{product_id}"

    def _update_pickings_to_ecommerce(self, pickings):
        if self.channel_code != 'bigcommerce':
            return super()._update_pickings_to_ecommerce(pickings)

        for picking in pickings:
            try:
                fulfillment = self._update_picking_to_bigcommerce(picking)
            except ECommerceApiError as error:
                self._post_process_after_picking_update_failed(picking, error)
            else:
                self._post_process_after_picking_update_success(picking, fulfillment.get('id'))

    def _update_picking_to_bigcommerce(self, pickings):
        bigcommerce_order_id = pickings.ecommerce_order_identifier
        carrier_name = pickings.carrier_id.name.lower() if pickings.carrier_id else ""
        tracking_number = pickings.carrier_tracking_ref

        if not bigcommerce_order_id or not tracking_number:
            raise ECommerceApiError("Missing BigCommerce order ID or tracking number.")

        # Update order status to "Shipped" (status_id=2)
        update_payload = {"status_id": 2}
        update_response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='PUT',
            version='v2',
            endpoint=f'orders/{bigcommerce_order_id}',
            payload=update_payload
        )

        if isinstance(update_response, dict) and update_response.get("errors"):
            raise ECommerceApiError(update_response.get("errors"))

        # Fetch the order details to get consignments/shipping addresses
        order_response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='GET',
            version='v2',
            endpoint=f'orders/{bigcommerce_order_id}',
            params={'include': 'consignments,consignments.line_items'}
        )

        if not order_response or 'consignments' not in order_response:
            raise ECommerceApiError("Unable to fetch order consignments for shipment creation.")
        # Take the first shipping address
        order_address_id = None
        items_payload = []
        for consignment in order_response.get("consignments", []):
            for shipping in consignment.get("shipping", []):
                if not order_address_id:
                    order_address_id = shipping.get("id")
                for item in shipping.get("line_items", []):
                    items_payload.append({
                        "order_product_id": item.get("id"),
                        "quantity": item.get("quantity"),
                    })

        if not order_address_id:
            raise ECommerceApiError("No shipping address found for creating shipment.")

        if carrier_name in [
            "auspost", "canadapost", "endicia", "usps", "fedex", "royalmail",
            "ups", "upsready", "shipperhq"
        ]:
            shipping_provider = carrier_name
        else:
            shipping_provider = ""  # BigCommerce will use default carrier (Other)

        # Create shipment
        shipment_payload = {
            "order_address_id": order_address_id,
            "tracking_number": tracking_number,
            "shipping_provider": shipping_provider,
            "items": items_payload
        }

        shipment_response = bigcommerce_request_handler.request(
            ecommerce_account=self,
            method='POST',
            version='v2',
            endpoint=f'orders/{bigcommerce_order_id}/shipments',
            payload=shipment_payload
        )

        if isinstance(shipment_response, dict) and shipment_response.get("errors"):
            raise ECommerceApiError(shipment_response.get("errors"))

        return shipment_response
