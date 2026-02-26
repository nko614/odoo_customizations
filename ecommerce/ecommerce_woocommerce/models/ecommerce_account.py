# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
from urllib.parse import urlencode

import requests
from requests.auth import HTTPBasicAuth
from werkzeug.urls import url_join

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.ecommerce_woocommerce import const
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError

_logger = logging.getLogger(__name__)


class EcommerceAccount(models.Model):
    _inherit = 'ecommerce.account'

    # ===== FIELDS ===== #

    wc_store_url = fields.Char(
        string="Store URL",
        required_if_channel="woocommerce",
        copy=False,
        help="Woocommerce store URL for Woocommerce API authentication.",
    )
    wc_consumer_key = fields.Char(
        string="WooCommerce Consumer Key",
        help="Woocommerce consumer key for Woocommerce API authentication.",
        copy=False,
    )
    wc_consumer_secret = fields.Char(
        string="WooCommerce Consumer Secret",
        help="Woocommerce consumer secret for Woocommerce API authentication.",
        copy=False,
    )
    wc_store = fields.Char(
        string="woocommerce store",
        compute='_compute_wc_store',
        copy=False,
    )

    # ==== COMPUTE METHODS ==== #

    @api.depends('wc_store_url')
    def _compute_wc_store(self):
        for account in self:
            account.wc_store = account.wc_store_url and account.wc_store_url.removeprefix('https://')

    # ===== ACTION METHODS ===== #

    def action_connect(self):
        """Initiate the WooCommerce OAuth connection flow.

        Validates the store URL, checks connectivity, and redirects the user
        to the WooCommerce authorization page.

        :return: Action to redirect the user to the WooCommerce authorization URL.
        :rtype: ir.actions.act_url
        """
        self.ensure_one()
        if self.channel_code != 'woocommerce':
            return super().action_connect()

        try:
            base_url = self.get_base_url()
            params = {
                'app_name': 'odoo-app',
                'scope': 'read_write',
                'user_id': self.id,
                'return_url': f"{base_url}/odoo/action-2004/ecommerce.account/{self.id}",
                'callback_url': f"{base_url}/woocommerce/callback",
            }
            url = f'{self.wc_store_url}{const.OAUTHORIZE_END_POINT}'
            return {
                'type': 'ir.actions.act_url',
                'url': f"{url}?{urlencode(params)}",
                'target': 'new',
            }
        except Exception as error:
            raise UserError(self.env._("User input error while connecting to %s ecommerce: %s") % (self.name, error)) from error

    # pull product
    def _fetch_products_from_ecommerce(self):
        """Fetch and structure products from the WooCommerce store.

        Falls back to the parent implementation for non-WooCommerce channels.

        :return: Structured product data fetched from the ecommerce platform.
        :rtype: dict
        """
        if self.channel_code != 'woocommerce':
            return super()._fetch_products_from_ecommerce()
        product_tmpls = self._wc_fetch_product_tmpl()
        product_name_by_id = {
            product['id']: product['name'] for product in product_tmpls
        }
        products = self._wc_fetch_products(product_tmpls=product_tmpls)
        structured_product = self._wc_build_structured(products, product_name_by_id)

        return {'products': structured_product}

    def _wc_fetch_product_tmpl(self):
        """Fetch product templates from WooCommerce modified after the last sync date.

        Retrieves simple and variable product types updated since the last
        products pull from the WooCommerce store.

        :return: List of WooCommerce product templates.
        :rtype: list
        """
        created_at_min_date = self._convert_odoo_date_to_wc_format(self.last_products_sync)
        page = 1
        per_page = 50
        all_products = []

        while True:
            products = self._call_wc(
                method='GET',
                end_point='products',
                params={
                    'modified_after': created_at_min_date,
                    'page': page,
                    'per_page': per_page,
                },
            )
            if not products:
                break
            # FIXME: Make separate requests for simple and variable product types
            for product in products:
                if product.get('type') in ['variable', 'simple']:
                    all_products.append(product)

            page += 1
        return all_products

    def _wc_fetch_products(self, product_tmpls):
        """Fetch WooCommerce products and their variations.

        Includes simple products directly and fetches variations
        for variable product templates.

        :param list product_tmpls: List of WooCommerce product templates.
        :return: List of simple products and product variations.
        :rtype: list
        """
        response = []
        for product_tmpl in product_tmpls:
            if product_tmpl.get('type') == 'simple':
                response.append(product_tmpl)
                continue

            page = 1
            per_page = 100
            while True:
                product_variations = self._call_wc(
                    method='GET',
                    end_point=f"products/{product_tmpl.get('id')}/variations",
                    params={
                        'page': page,
                        'per_page': per_page,
                    },
                )
                if not product_variations:
                    break
                response.extend(product_variations)
                page += 1
        return response

    def _wc_build_structured(self, products, product_name_by_id):
        """Build structured product data from WooCommerce products.

        Formats product and variation data into a unified structure
        with SKU, name, and ecommerce identifiers.

        :param list products: List of WooCommerce products and variations.
        :param dict product_name_by_id: Mapping of product template IDs to names.
        :return: Structured product data.
        :rtype: list
        """
        structure_product = []
        for product in products:
            variant_name = (
                product.get('name')
                if product.get('type') == 'simple'
                else f"{product_name_by_id.get(product.get('parent_id'), '')} ({product.get('name')})"
            )
            product_data = {
                'sku': product.get('sku') if product.get('sku') else None,
                'name': variant_name,
                'ec_product_identifier': product.get('id'),
                'ec_product_template_identifier': product.get('parent_id'),
            }
            structure_product.append(product_data)
        return structure_product

    # orders
    def _fetch_orders_from_ecommerce(self):
        """Fetch and structure orders from the WooCommerce store.

        Retrieves orders modified after the last sync date, excludes
        draft checkout orders, and returns structured order data.

        :return: Structured order data from the ecommerce platform.
        :rtype: dict
        """
        if self.channel_code != 'woocommerce':
            return super()._fetch_orders_from_ecommerce()
        created_at_min_date = self._convert_odoo_date_to_wc_format(self.last_orders_sync)

        structured_orders = []
        page = 1
        per_page = 50  # WooCommerce allows up to 100

        while True:
            orders = self._call_wc(
                method='GET',
                end_point='orders',
                params={
                    'modified_after': created_at_min_date,
                    'page': page,
                    'per_page': per_page,
                },
            )
            if not orders:
                break
            for order in orders:
                if order.get('status') not in ['checkout-draft', 'auto-draft']:
                    structured_order = self._wc_build_order_structure(order)
                    structured_orders.append(structured_order)

            page += 1
        return {'orders': structured_orders}

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        if self.channel_code != 'woocommerce':
            return super()._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        order = self._call_wc(
            method='GET',
            end_point=f"orders/{ecommerce_order_ref}",
        )
        if not order:
            raise ECommerceApiError(self.env._("This order does not exist on the WooCommerce side."))
        structured_order = self._wc_build_order_structure(order)
        return structured_order

    def _wc_build_order_structure(self, order, **kwargs):
        """Build a structured order dictionary from a WooCommerce order.

        Converts WooCommerce order data into a normalized format including
        order details, order lines, billing address, and shipping address.

        :param dict order: WooCommerce order data.
        :return: Structured order representation.
        :rtype: dict
        """
        billing_address = order.get('billing')
        shipping_address = order.get('shipping')
        order_lines = order.get('line_items')
        return {
            'id': order.get('id'),
            'status': const.ORDER_STATUS_MAPPING[order.get('status')],
            'currency_code': order.get('currency'),
            'reference': order.get('order_key'),
            'customer_id': order.get('customer_id'),
            'date_order': order.get('date_created', ''),
            'order_lines': self._wc_prepare_order_line_data(order_lines),
            'financial_status': self._wc_find_financial_status(order),
            'billing_address': {
                    'name': f"{billing_address.get('first_name', '')} {billing_address.get('last_name', '')}".strip(),
                    'email': billing_address.get('email', ''),
                    'phone': billing_address.get('phone', ''),
                    'street': billing_address.get('address_1', ''),
                    'street2': billing_address.get('address_2', ''),
                    'zip': billing_address.get('postcode', ''),
                    'city': billing_address.get('city', ''),
                    'state_code': billing_address.get('state', ''),
                    'country_code': billing_address.get('country', ''),
            }if billing_address else {},
            'shipping_address': {
                    'name': f"{shipping_address.get('first_name', '')} {shipping_address.get('last_name', '')}".strip(),
                    'email': shipping_address.get('email', ''),
                    'phone': shipping_address.get('phone', ''),
                    'street': shipping_address.get('address_1', ''),
                    'street2': shipping_address.get('address_2', ''),
                    'zip': shipping_address.get('postcode', ''),
                    'city': shipping_address.get('city', ''),
                    'state_code': shipping_address.get('state', ''),
                    'country_code': shipping_address.get('country', ''),
            }if shipping_address else {},
            'shipping_lines': [
                {
                    'id': str(shipping_line.get('id')),
                    'shipping_code': shipping_line.get('method_id'),
                    'description': shipping_line.get('method_title'),
                    'price_unit': (
                        float(shipping_line.get('total') or 0.0) +
                        float(shipping_line.get('total_tax') or 0.0)
                    ) if self.tax_included else float(shipping_line.get('total') or 0.0),
                    'tax_amount': shipping_line.get('total_tax'),
                }
                for shipping_line in order.get('shipping_lines', [])
            ],
        }

    def _wc_find_financial_status(self, order):
        """Determine financial status from WooCommerce order data.
        Marks order as 'PAID' based on business rules:
        - Prepaid orders are considered paid when status is 'processing'.
        - Cash on Delivery orders are considered paid when status is 'completed'.
        :param dict order: WooCommerce order data.
        :return: 'PAID' if payment is confirmed, otherwise None.
        :rtype: str or None
        """
        payment_method = (order.get('payment_method_title') or '').strip().lower()
        status = (order.get('status') or '').strip().lower()
        if payment_method != 'cash on delivery' and status == 'processing':
            return 'PAID'
        if payment_method == 'cash on delivery' and status == 'completed':
            return 'PAID'
        return None

    def _wc_prepare_order_line_data(self, order_lines):
        """Prepare structured order line data from WooCommerce order lines.

        Converts WooCommerce line items into a normalized format with
        product identifiers, pricing, quantity, and product metadata.

        :param list order_lines: List of WooCommerce order line items.
        :return: Structured order line data.
        :rtype: list
        """
        lines = []
        for line in order_lines:
            subtotal = float(line.get('subtotal', 0.0))
            subtotal_tax = float(line.get('subtotal_tax', 0.0))
            total = float(line.get('total', 0.0))
            total_tax = float(line.get('total_tax', 0.0))
            quantity = line.get('quantity', 0)  # 1
            discount_amount = subtotal - total
            discount_tax = subtotal_tax - total_tax
            line_data = {
                'id': line.get('id'),
                'sku': line.get('sku') if line.get('sku') else None,
                'description': '',
                'name': line.get('name', ''),
                'product_id': line.get('variation_id'),
                'qty_ordered': quantity,
                'price_subtotal': subtotal + subtotal_tax if self.tax_included else subtotal,
                'tax_amount': subtotal_tax,
                'discount_amount': discount_amount + discount_tax if self.tax_included else discount_amount,
                'discount_tax': discount_tax,
                'product_data': {
                    'name': line.get('name'),
                    'sku': line.get('sku'),
                    'ec_product_identifier': line.get('variation_id') if line.get('variation_id') else line.get('product_id'),
                    'ec_product_template_identifier': line.get('product_id') if line.get('variation_id') else None,
                },
            }
            lines.append(line_data)
        return lines

    def _update_inventory_to_ecommerce(self, inventory_data):
        if self.channel_code != 'woocommerce':
            return super()._update_inventory_to_ecommerce(inventory_data)
        updated_products = []
        failed_products = []
        for val in inventory_data:
            if not val['offer'].ec_product_template_identifier:
                end_point = f"products/{val['offer'].ec_product_identifier}"
            else:
                end_point = f"products/{val['offer'].ec_product_template_identifier}/variations/{val['offer'].ec_product_identifier}"
            product = self._call_wc(
                method='PUT',
                end_point=end_point,
                data={
                    'manage_stock': True,
                    'stock_quantity': val.get('quantity', 0),
                },
            )
            if not product:
                _logger.warning("Product %s quantity not updated", val['offer'].ec_product_identifier)
                failed_products.append(val['offer'].ec_product_identifier)
                continue
            updated_products.append(val['offer'].ec_product_identifier)
        return {}

    def _get_product_url(self, offer):
        """Return the WooCommerce admin edit URL for the given product offer.

        :param offer: Offer record linked to the product.
        :return: Product edit URL.
        :rtype: str
        """
        if self.channel_code != 'woocommerce':
            return super()._get_product_url(offer)
        product_id = (
            offer.ec_product_template_identifier
            if int(offer.ec_product_template_identifier)
            else offer.ec_product_identifier
        )
        return f"{self.wc_store_url}/wp-admin/post.php?post={product_id}&action=edit"

    def _call_wc(
        self,
        data=False,
        end_point=False,
        method='GET',
        params=False,
    ):
        """Send an authenticated request to the WooCommerce API and return the JSON response.

        :raises ECommerceApiError: If the connection fails or an HTTP error occurs.
        :return: WooCommerce API response as JSON.
        :rtype: dict
        """
        base_url = f'{self.wc_store_url}{const.wc_api_endpoint}'
        url = url_join(base_url, end_point) if end_point else base_url
        auth = HTTPBasicAuth(self.wc_consumer_key, self.wc_consumer_secret)
        try:
            response = requests.request(
                method,
                url,
                params=params,
                data=data,
                auth=auth,
                timeout=10,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise ECommerceApiError(self.env._("Could not establish the connection to the WooCommerce."))
        try:
            response.raise_for_status()
            _logger.info("Request response: %s", pprint.pformat(response.json()))
        except requests.exceptions.HTTPError as error:
            raise ECommerceApiError(
                self.env._(
                    "[http_error] %(error_message)s",
                    error_message=error,
                ),
            )
        return response.json()

    def _convert_odoo_date_to_wc_format(self, odoo_date):
        try:
            if not odoo_date:
                return False
            return odoo_date.isoformat() + 'Z'
        except UserError as error:
            raise ECommerceApiError(f"Invalid date provided: {error}") from error
        except Exception as error:
            raise ECommerceApiError(f"Unexpected error while converting date: {error}") from error
