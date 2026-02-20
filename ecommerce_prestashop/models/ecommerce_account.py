# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from odoo import _, fields, models
from odoo.addons.ecommerce_prestashop.utils.prestashop_api import PrestashopAPI
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ECommerceAccount(models.Model):
    _inherit = 'ecommerce.account'

    # ===== FIELDS ===== #

    webservice_key = fields.Char(
        string="Webservice Key",
        required_if_channel='prestashop',
        help="Key used to authenticate prestashop API requests. Keep it secure.",
        copy=False,
    )

    prestashop_url = fields.Char(
        string="Prestashop Admin Dashboard URL",
        required_if_channel='prestashop',
        help="The website URL where Prestashop is hosted.",
        copy=False,
    )

    prestashop_store = fields.Char(
        string="Prestashop Store Name",
        help="Prestashop Store Name for Prestashop API authentication.",
        copy=False,
    )

    prestashop_store_id = fields.Integer(
        string="Store ID",
        help="Prestashop Store ID for Prestashop API authentication.",
        copy=False,
    )

    # ===== ACTION METHODS ===== #

    def action_connect(self):
        """Connect with Prestashop using WEBSERVICE_KEY"""

        def match_store():
            """Match and assign the PrestaShop store (default or by name)."""
            store_name = (self.prestashop_store or '').strip().lower()
            prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=1, endpoint=self.prestashop_url)

            # Case 1: No store name provided, fallback to default store
            if not store_name:
                default_location = prestashop_api._get_default_location()
                if default_location:
                    default_store_id = str(default_location[0].get('value', 1))
                    response_all_shops = prestashop_api._get_locations()

                    matching_shop = next(
                        (shop for shop in response_all_shops if str(shop.get('id')) == default_store_id),
                        None,
                    )

                    if matching_shop:
                        self.prestashop_store_id = int(default_store_id)
                        self.prestashop_store = matching_shop.get('name', '')
                return

            # Case 2: Store name provided, find by name
            response_all_shops = prestashop_api._get_locations()
            matching_shop = next(
                (
                    shop for shop in response_all_shops
                    if str(shop.get('name', '')).strip().lower() == store_name
                ),
                None,
            )

            if not matching_shop:
                store = self.prestashop_store or _("(unknown)")
                raise ValidationError(_("Invalid Store Name: ") + str(store))

            # Update location if already exists
            location = self.env['ecommerce.location'].search(
                [('ecommerce_account_id', '=', self.id)], limit=1
            )
            if location:
                location.write({
                    'ecommerce_location_identifier': str(matching_shop.get('id', '')),
                    'name': matching_shop.get('name', ''),
                })

            # Always update store id
            self.prestashop_store_id = int(matching_shop.get('id'))

        self.ensure_one()
        if self.channel_code == 'prestashop':
            try:
                prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, endpoint=self.prestashop_url)
                prestashop_api._authenticate_connection()
                match_store()
            except ECommerceApiError as error:
                raise UserError(self.env._("Failed to connect %s ECommerce account: %s") % (self.name, error)) from error
        return super().action_connect()

    # ===== OVERRIDE METHODS ===== #

    def _fetch_products_from_ecommerce(self):
        '''Fetch products from PrestaShop, including variant combinations.'''

        if self.channel_code != 'prestashop':
            return super()._fetch_products_from_ecommerce()

        # --- Get Products from Prestashop --- #
        prestashop_api = PrestashopAPI(
            webservice_key=self.webservice_key,
            store_id=self.prestashop_store_id,
            endpoint=self.prestashop_url
        )
        response_products = prestashop_api._get_products(self.last_products_sync)
        _logger.debug('Fetched %d products from PrestaShop', len(response_products) if response_products else 0)

        if not response_products:
            _logger.debug('No products returned from PrestaShop.')
            return {'products': []}

        # --- Language handling --- #
        response_all_languages = prestashop_api._get_languages()
        default_language = next(
            (lang for lang in response_all_languages if str(lang.get('iso_code')) == 'en'),
            {}
        )
        default_lang_id = int(default_language.get('id', 1)) or 1

        def get_multilang_value(value_list):
            """
            Return the value for the default language.
            If not found, return the first available value.
            """
            # If it's not a list, return it directly (or empty string)
            if not isinstance(value_list, list):
                return value_list or ''

            # Try to find value for the default language
            for item in value_list:
                if int(item.get('id', 0)) == default_lang_id:
                    return item.get('value', '')

            # Fallback: return the first available value
            for item in value_list:
                if item.get('value'):
                    return item.get('value')

            return ''

        # --- Results container --- #
        products = []

        for product in response_products:
            product_id = product.get('id')
            product_type = product.get('product_type')
            product_name = get_multilang_value(product.get('name'))

            if product_type != 'combinations':  # --- Simple product ---
                products.append({
                    'name': product_name,
                    'sku': product.get('reference'),
                    'ec_product_template_identifier': str(product_id),
                })
            else:  # --- Product with combinations ---
                combination_ids = [
                    c.get('id')
                    for c in product.get('associations', {}).get('combinations', [])
                    if c.get('id')
                ]

                if not combination_ids:
                    _logger.debug("No combinations found for product ID %s", product_id)
                else:
                    start = time.time()
                    variants = self._fetch_product_variants_parallel(
                        prestashop_api,
                        product,
                        combination_ids,
                        get_multilang_value
                    )
                    products.extend(variants)

                    _logger.debug(
                        "Fetched %d variants for product ID %s in %.2f seconds",
                        len(variants),
                        product_id,
                        time.time() - start
                    )

        return {'products': products}

    def _fetch_orders_from_ecommerce(self):
        if self.channel_code != 'prestashop':
            return super()._fetch_orders_from_ecommerce()
        start = time.time()
        response = self._fetch_orders_from_ecommerce_parallel(self.last_orders_sync)
        end = time.time()
        _logger.debug('API Time: %s', end - start)
        return response

    def _fetch_locations_from_ecommerce(self):
        '''Fetch shop locations from PrestaShop.'''
        if self.channel_code != 'prestashop':
            return super()._fetch_locations_from_ecommerce()

        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)
        response_shops = prestashop_api._get_locations()

        if not response_shops:
            _logger.debug('No shops returned from PrestaShop.')
            return {'locations': []}
        locations = [
            {
                'id': str(shop.get('id', '')),
                'name': shop.get('name', ''),
            } for shop in response_shops if shop.get('id') and shop.get('id') == self.prestashop_store_id
        ]
        _logger.debug('Fetched %d locations from PrestaShop.', len(locations))
        _logger.debug('Fetched locations %s.', locations)
        return {'locations': locations}

    def _update_inventory_to_ecommerce(self, inventory_data):
        if self.channel_code != 'prestashop':
            return super()._update_inventory_to_ecommerce(inventory_data)

        def fetch_product(product_id):
            return prestashop_api._get_product(product_id=product_id)

        # Helper to find stock_available_id
        def get_stock_available_id(item):
            offer = item.get('offer', {})
            stock_available_id = 0

            if not offer.ec_product_identifier:
                product_id = offer.ec_product_template_identifier
                relative_product = response_products.get(product_id, [{}])
                stock_availables = relative_product[0].get('associations', {}).get('stock_availables', [])
                if stock_availables:
                    stock_available_id = stock_availables[0].get('id', 0)
            else:
                # Variant-level product
                product_template_id = offer.ec_product_template_identifier
                product_id = offer.ec_product_identifier
                relative_product = response_products.get(product_template_id, [{}])
                stock_availables = relative_product[0].get('associations', {}).get('stock_availables', [])
                if stock_availables:
                    stock = next(
                        (s for s in stock_availables if str(s.get('id_product_attribute')) == str(product_id)),
                        None
                    )
                    if stock:
                        stock_available_id = stock.get('id', 0)

            return stock_available_id

        # Update inventory in parallel
        def update_stock(store_inventory):
            stock_available_id = store_inventory.get('stock_available_id', 0)
            quantity = store_inventory.get('quantity', 0)
            if stock_available_id > 0:
                return prestashop_api._set_inventory(stock_available_id=stock_available_id, quantity=quantity)
            return None

        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)

        # Filter inventory for this PrestaShop store
        current_store_inventory = [
            stock for stock in inventory_data
            if str(stock.get('location', {})['ecommerce_location_identifier']) == str(self.prestashop_store_id)
        ]

        # Collect unique product IDs
        unique_product_ids = {
            row.get('offer')['ec_product_template_identifier']
            if row.get('offer')['ec_product_template_identifier'] else row.get('offer')['ec_product_identifier']
            for row in current_store_inventory
        }

        response_products = {pid: fetch_product(pid) for pid in unique_product_ids}

        # Add stock_available_id to each item
        for item in current_store_inventory:
            item['stock_available_id'] = get_stock_available_id(item)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_stock, item) for item in current_store_inventory]
            # Optionally, handle responses or exceptions
            for future in as_completed(futures):
                future.result()

        return {}

    def _get_product_url(self, offer):
        """Return the PrestaShop product URL for a given offer."""
        if self.channel_code != 'prestashop':
            return super()._get_product_url(offer)

        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)
        base_url = prestashop_api.client_endpoint

        if not offer:
            return base_url

        product_id = (
            offer.ec_product_template_identifier if offer.ec_product_template_identifier else offer.ec_product_identifier
        )

        product_url = f'{base_url}/sell/catalog/products/{product_id}'
        return product_url

    # ===== HELPER METHODS ===== #

    def _get_database_from_url(self, url):
        """Extract database name from URL path.

        :param str url: Full Prestashop admin URL
        :return: Database name from URL path or None
        :rtype: str or None
        """
        if not url:
            return None
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.strip('/')

            if path:
                segments = path.split('/')
                return segments[-1] if segments else None
        except (ValueError, AttributeError, TypeError) as e:
            # Log the error but don't block the operation
            _logger.warning("Failed to extract database name from URL %s: %s", url, e)
        return None

    def _fetch_orders_from_ecommerce_parallel(self, last_orders_sync):
        if self.channel_code != 'prestashop':
            return super()._fetch_orders_from_ecommerce()

        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)
        response_orders = prestashop_api._get_orders(last_orders_sync)
        if not response_orders:
            _logger.debug('No orders returned from PrestaShop.')
            return {'orders': []}

        orders = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._process_order, so) for so in response_orders if so.get('id')]
            for future in as_completed(futures):
                orders.append(future.result())
        return {'orders': orders}

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        if self.channel_code != 'prestashop':
            return super()._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)
        response_order = prestashop_api._get_order(ecommerce_order_ref)
        order = self._process_order(response_order[0])
        return order

    def _process_order(self, so):
        prestashop_api = PrestashopAPI(webservice_key=self.webservice_key, store_id=self.prestashop_store_id, endpoint=self.prestashop_url)

        def get_country_code(country_id):
            if not country_id:
                return ''
            countries = prestashop_api._get_country(country_id)
            return next((c.get('iso_code') for c in countries if str(c.get('id')) == str(country_id)), '')

        def get_state_code(state_id):
            if not state_id:
                return ''
            states = prestashop_api._get_state(state_id)
            return next((s.get('iso_code') for s in states if str(s.get('id')) == str(state_id)), '')

        def get_carrier_name(carrier_id):
            response_carrier = prestashop_api._get_carrier(carrier_id=carrier_id)
            result_carrier = list(filter(lambda carrier: carrier.get('id') == carrier_id, response_carrier))
            return result_carrier[0].get('name', '') if result_carrier else ''

        def get_order_address(customer_id, address_id):

            def get_customer_info(customer_id):
                if not customer_id or customer_id == '0':
                    return {}

                customers = prestashop_api._get_customer(customer_id)
                customer = next((customer for customer in customers if str(customer.get('id')) == str(customer_id)), {})

                return customer

            if not address_id or address_id == '0':
                return {
                    'name': '',
                    'email': '',
                    'phone': '',
                    'street': '',
                    'street2': '',
                    'zip': '',
                    'city': '',
                    'state_code': '',
                    'country_code': ''
                }

            addresses = prestashop_api._get_address(address_id)
            addr = next((a for a in addresses if str(a.get('id')) == str(address_id)), {})

            customer = get_customer_info(customer_id)
            return {
                'name': f'{addr.get("firstname", "")}{addr.get("lastname", "")}',
                'email': customer.get('email', ''),
                'phone': addr.get('phone', ''),
                'street': addr.get('address1', ''),
                'street2': addr.get('address2', ''),
                'zip': addr.get('postcode', ''),
                'city': addr.get('city', ''),
                'state_code': get_state_code(addr.get('id_state')),
                'country_code': get_country_code(addr.get('id_country'))
            }

        def get_currency_code(currency_id):
            if not currency_id:
                return ''
            currencies = prestashop_api._get_currency(currency_id)
            return next((c.get('iso_code') for c in currencies if str(c.get('id')) == str(currency_id)), '')

        def get_order_status(order_state_id):
            if not order_state_id:
                return 0
            states = prestashop_api._get_order_state(order_state_id)
            return next((s.get('id') for s in states if str(s.get('id')) == str(order_state_id)), 0)

        def get_shipping_lines(so):
            return [{
                'id': f"prestashop_ship_{so.get('id')}",
                'description': get_carrier_name(so.get('id_carrier')),
                'shipping_code': so.get('shipping_number', ''),
                'price_unit': float(so.get('total_shipping_tax_excl', 0.0)),
                'tax_amount': float(so.get('total_shipping_tax_incl', 0.0)) - float(so.get('total_shipping_tax_excl', 0.0)),
            }]

        def get_discount_lines(so):
            return [{
                'price_unit': float(so.get('total_discounts_tax_excl', 0.0)),
                'tax_amount': float(so.get('total_discounts_tax_incl', 0.0)) - float(so.get('total_discounts_tax_excl', 0.0))
            }]

        order_payload = {
            'id': str(so['id']),
            'status': 'canceled' if get_order_status(so.get('current_state')) == 6 else 'confirmed',
            'reference': so.get('reference'),
            'write_date': str(so.get('date_upd', '')),
            'currency_code': get_currency_code(so.get('id_currency')),
            'customer_id': str(so.get('id_customer', '')),
            'location_id': str(so.get('id_shop', '0')),
            'date_order': so.get('date_add'),
            'billing_address': get_order_address(so.get('id_customer', '0'), so.get('id_address_invoice', '0')),
            'shipping_address': get_order_address(so.get('id_customer', '0'), so.get('id_address_delivery', '0')),
            'order_lines': [{
                'id': str(line.get('id')),
                'description': line.get("product_name"),
                'product_data': {
                    'name': line.get('product_name'),
                    'sku': str(line.get('product_reference')),
                    'ec_product_identifier': line.get('product_attribute_id'),
                    'ec_product_template_identifier': line.get('product_id')
                },
                'price_unit': line.get('unit_price_tax_excl', 0),
                'tax_amount': (float(line.get('unit_price_tax_incl', 0)) - float(line.get('unit_price_tax_excl', 0))) * line.get('product_quantity', 0),
                'qty_ordered': line.get('product_quantity', 0),
            } for line in so.get('associations', {}).get('order_rows', [])],
        }

        # Add discount lines if discount is present
        if float(so.get('total_discounts_tax_excl', 0.0)) > 0:
            order_payload.update({
                'discount_lines': get_discount_lines(so),
            })

        # Add shipping lines if shipping is present
        if float(so.get('total_shipping_tax_excl', 0.0)) > 0:
            order_payload.update({
                'shipping_lines': get_shipping_lines(so),
            })

        return order_payload

    def _fetch_product_variants_parallel(self, prestashop_api, product, combination_ids, get_multilang_value):
        '''
        Run API calls for product combinations in parallel threads (like Promise.all),
        and preserve the order of combination_ids.
        '''
        def fetch_combination_values(pov_ids):
            """Fetch option values (color, size, etc.) for one combination."""
            pov_names = [None] * len(pov_ids)
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_map = {
                    executor.submit(prestashop_api._get_product_combination_option_values, pov_id): idx
                    for idx, pov_id in enumerate(pov_ids)
                }
                for future in as_completed(future_map):
                    idx = future_map[future]
                    response = future.result()
                    povs = response[0] if response else {}
                    pov_list = povs.get('name')

                    pov_name = get_multilang_value(pov_list)
                    pov_names[idx] = pov_name
            return pov_names

        results = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {
                executor.submit(prestashop_api._get_product_combinations, cid): cid
                for cid in combination_ids
            }
            for future in as_completed(future_map):
                cid = future_map[future]
                response = future.result()
                combination = response[0] if response else {}

                pov_ids = [
                    pov.get('id')
                    for pov in combination.get('associations', {}).get('product_option_values', [])
                    if pov.get('id')
                ]

                # Fetch option values
                combination_values_str = ''
                if pov_ids:
                    combination_values = fetch_combination_values(pov_ids)
                    combination_values_str = ', '.join(filter(None, combination_values))

                # Build variant record
                product_name = get_multilang_value(product.get('name'))
                results[cid] = {
                    'name': (product_name + (' (' + combination_values_str + ')' if combination_values_str else '')).strip(),
                    'sku': combination.get('reference'),
                    'ec_product_identifier': str(combination.get('id', '')),
                    'ec_product_template_identifier': str(combination.get('id_product', ''))
                }

        return [results[cid] for cid in combination_ids if results.get(cid)]
