# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re
from datetime import datetime

import pytz
import requests

from odoo.addons.ecommerce_shopify import const
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError

TIMEOUT = 30
LIMIT = 10
MAX_LIMIT = 250  # used for fetch nested objects.

_logger = logging.getLogger(__name__)


# === Graphql Final Request === #
def _call_shopify_graphql_admin_api(headers, url, query):
    """Call shopify graphql api.

    :param dict headers: contain 2 key
        - X-Shopify-Access-Token (str): access token of shopify account.
        - Content-Type (str): 'application/json'
    :param str url: Graphql API url in
        'https://{shopify_store_name}.myshopify.com/admin/api/{const.SHOPIFY_API_VERSION}/graphql.json' format.
    :param str query: query for particular object.

    :return: json response of api
    :rtype: dict
    """
    try:
        response = requests.post(
            url=url,
            headers=headers,
            timeout=TIMEOUT,
            json={'query': query},
        )
        response.raise_for_status()
        _logger.info("Successfully executed request on %s", url)
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.MissingSchema,
    requests.exceptions.Timeout, requests.exceptions.HTTPError, requests.exceptions.RequestException, requests.exceptions.InvalidURL) as ex:
        _logger.error("Error occurred during execute request on %s, error_description: %s", url, ex)
        raise ECommerceApiError(str(ex))
    return response.json()


# === Error Handling After Request === #
def _handle_query_error(response, url):
    """Handles errors that occur during a query to Shopify.

    :param dict response: The response received from Shopify, which may contain errors.
    :param str url: The URL from which the response was fetched.

    This method is called after each query is fetched from Shopify.
    If an error occurs while fetching data from Shopify, it is returned a list of errors under `errors` key,
    where each item is dictionary contain `message` key.
    """
    if response.get('errors'):
        error_message = ", ".join([error.get('message') for error in response.get('errors')])
        _logger.error("Error occurred after fetch data from %s, error_description: %s", url, error_message)
        raise ECommerceApiError(error_message)


def _handle_mutation_error(mutation_key, response, url):
    """Handles errors that occur during a mutation to Shopify.

    :param str mutation_key: The shopify object name where the mutation was performed.
    :param dict response: The response received from Shopify, which may contain errors.
    :param str url: The URL where the mutation was performed.

    This method is called after each mutation to Shopify.
    If an error occurs during the mutation, a list of dictionaries is returned under the `userErrors` key,
    where each item contains a `message` key describing the error.
    """
    userErrors = response['data'][mutation_key]['userErrors']
    if userErrors:
        error_message = ", ".join([error.get('message') for error in userErrors])
        _logger.error("Error occurred after mutation on %s, error_description: %s", url, error_message)
        raise ECommerceApiError(error_message)


# === Prepare Request Query === #
def _generate_shopify_shop_query():
    shop_query = """
    query GetShop {
        shop {
            name
        }
    }
    """
    return shop_query


def _generate_shopify_locations_query(after):
    """Generate shopify location query

    :param str after: The pagination token used to fetch the next page.
    """
    location_query = """
    query GetLocations {
        locations(first: %s, %squery: \"active:true\") {
            edges {
                node {
                    id
                    name
                }
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
    """ % (LIMIT, f'after: \"{after}\", ' if after else '')
    return location_query


def _generate_shopify_products_query(updated_at_min, after):
    """Generate shopify products query

    :param str updated_at_min: The date after which the updated products should be fetched.

    :param str after: The pagination token used to fetch the next page.
    """
    product_query = """
    query GetProducts {
        products(first: %s, %squery: \"updated_at:>\'%s\'\") {
            edges {
                node {
                    id
                    title
                    variants (first:%s) {
                        nodes {
                            id
                            inventoryItem {
                                id
                            }
                            sku
                            title
                        }
                    }
                }
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
    """ % (LIMIT, f'after: \"{after}\", ' if after else '', updated_at_min, MAX_LIMIT)
    return product_query


def _generate_shopify_order_by_id_query(order_id):
    """Generate shopify order by id query

    :param str order_id: The order identifier which is used to fetch particular order from shopify
    """
    order_query = """
    query GetOrder {
        order(id: \"%s\") {%s}
    }
    """ % (const.GLOBAL_ORDER_ID + order_id, _shopify_order_common_query())
    return order_query


def _generate_shopify_orders_query(updated_at_min, after):
    """Generate shopify order query

    :param str updated_at_min: The date after which the updated order should be fetched.

    :param str after: The pagination token used to fetch the next page.
    """
    # not needed to query filter status:any for fetch all orders, it's by default fetch all orders like canceled and successfull.
    order_query = """
    query GetOrders {
        orders(first: %s, sortKey: UPDATED_AT, %squery: \"updated_at:>\'%s\'\") {
            edges {
                node {%s}
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
    """ % (LIMIT, f'after: \"{after}\", ' if after else '', updated_at_min, _shopify_order_common_query())
    return order_query


def _shopify_order_common_query():
    """Generate common query for order which is used to fetch all orders as well as order by id."""
    order_query = """
    billingAddress {
        address1
        address2
        city
        countryCodeV2
        firstName
        lastName
        phone
        provinceCode
        zip
    }
    cancelledAt
    currencyCode
    createdAt
    customer {
        defaultAddress {
            address1
            address2
            city
            countryCodeV2
            firstName
            lastName
            phone
            provinceCode
            zip
        }
        defaultEmailAddress {
            emailAddress
        }
        id
    }
    displayFinancialStatus
    fulfillments(first: %s) {
        fulfillmentLineItems(first: %s) {
            nodes {
                id
                lineItem {
                    id
                }
                quantity
            }
        }
        id
        location {
            id
        }
        status
        trackingInfo(first: %s) {
            company
            number
        }
    }
    id
    lineItems (first:%s) {
        nodes {
            discountAllocations {
                allocatedAmountSet {
                    shopMoney {
                        amount
                    }
                }
            }
            id
            name
            originalUnitPriceSet {
                shopMoney {
                    amount
                }
            }
            product {
                id
            }
            quantity
            sku
            taxLines (first:%s) {
                priceSet {
                    shopMoney {
                        amount
                    }
                }
                rate
            }
            title
            variant {
                id
                inventoryItem {
                    id
                }
            }
            variantTitle
        }
    }
    name
    shippingAddress {
        address1
        address2
        city
        countryCodeV2
        firstName
        lastName
        phone
        provinceCode
        zip
    }
    shippingLines (first:%s) {
        nodes {
            discountAllocations {
                allocatedAmountSet {
                    shopMoney {
                        amount
                    }
                }
            }
            id
            originalPriceSet {
                shopMoney {
                    amount
                }
            }
            taxLines {
                priceSet {
                    shopMoney {
                        amount
                    }
                }
                rate
            }
            title
        }
    }
    updatedAt
    """ % (MAX_LIMIT, MAX_LIMIT, MAX_LIMIT, MAX_LIMIT, MAX_LIMIT, MAX_LIMIT)
    return order_query


def _generate_shopify_fulfillmentCreate_query(picking, headers, request_url):
    """Generate shopify mutation query for push fulfillment.

    :param `stock.pikcing` picking: record set of stock.picking which will be updated.
    :param dict headers: headers, used to make query request for fulfillment order.
    :param str url: Graphql API url, used to make query request for fulfillment order.

    :return fulfillment_query: fulfillment query for push picking.
    :rtype: str.
    """

    # === Handle Fulfillment Order === #
    fulfillment_order_query = _generate_shopify_fulfillment_order_query(picking.ecommerce_order_identifier)
    fulfillment_order_response = _call_shopify_graphql_admin_api(headers, request_url, fulfillment_order_query)
    _handle_query_error(fulfillment_order_response, request_url)
    if not fulfillment_order_response['data']['order']:
        raise ECommerceApiError(f"There is no order exists on shopify, related to id {picking.ecommerce_order_identifier}")

    # === Prepare Fulfillment Update Query === #
    mapped_shopify_line_id = {
        move_id.sale_line_id.ecommerce_line_identifier: int(move_id.quantity)
        for move_id in picking.move_ids
        if move_id.sale_line_id and
        move_id.sale_line_id.ecommerce_line_identifier
    }

    fulfillment_orders_data = fulfillment_order_response['data']['order']['fulfillmentOrders']['nodes']
    fulfillment_orders_query = []
    for fulfillment_order_data in fulfillment_orders_data:
        if fulfillment_order_data['status'] in ['CANCELLED', 'CLOSED', 'INCOMPLETE', 'ON_HOLD', 'SCHEDULED']:
            continue
        fulfillment_order_line_items_query = []
        fulfillment_line_items_data = fulfillment_order_data['lineItems']['nodes']
        for fulfillment_line_item_data in fulfillment_line_items_data:
            order_line_item_id = fulfillment_line_item_data['lineItem']['id'].replace(const.GLOBAL_LINE_ITEM_ID, '')
            if order_line_item_id in mapped_shopify_line_id:
                order_line_item_quantity = mapped_shopify_line_id[order_line_item_id]
                fulfillment_order_line_items_query.append('{id: \"%s\" quantity: %s}' % (fulfillment_line_item_data['id'], order_line_item_quantity))
        if fulfillment_order_line_items_query:
            fulfillment_orders_query.append('{fulfillmentOrderId: \"%s\" fulfillmentOrderLineItems: [%s]}' % (fulfillment_order_data['id'], ''.join(fulfillment_order_line_items_query)))

    fulfillment_tracking_info_query = ''
    fulfillment_tracking_info_query = 'trackingInfo: {'
    tracking_company = (
        const.SHOPIFY_CARRIER_NAMES_MAPPING.get(picking.carrier_id.name)
        or const.SHOPIFY_CARRIER_NAMES_MAPPING.get(picking.carrier_id.delivery_type)
        or 'Other'
    )  # If either the delivery_type of the picking's carrier_id or the name of the picking's carrier_id exists on Shopify, then set it as the company; otherwise, set the company as Other.
    fulfillment_tracking_info_query += f'company: \"{tracking_company}\"'
    fulfillment_tracking_info_query += f'number: \"{picking.carrier_tracking_ref}\"'
    if picking.carrier_tracking_url:
        fulfillment_tracking_info_query += f'url: \"{picking.carrier_tracking_url}\"'
    fulfillment_tracking_info_query += '}'

    fulfillment_push_query = """
    mutation createFulfillment {
        fulfillmentCreate (
            fulfillment: {
                lineItemsByFulfillmentOrder: [%s]
                %s
            }
        ) {
            fulfillment {
                id
            }
            userErrors {
                message
            }
        }
    }
    """ % (''.join(fulfillment_orders_query), fulfillment_tracking_info_query)

    return fulfillment_push_query


def _generate_shopify_fulfillment_order_query(order_id):
    """Generate shopify fulfillment order query

    :param str order_id: Shopify unique identifier of order.
    """

    order_query = """
    query GetOrder {
        order(id: \"%s\") {
            fulfillmentOrders (first:%s) {
                nodes {
                    id
                    lineItems (first:%s) {
                        nodes {
                            id
                            lineItem {
                                id
                            }
                        }
                    }
                    status
                }
            }
        }
    }
    """ % (const.GLOBAL_ORDER_ID + order_id, MAX_LIMIT, MAX_LIMIT)
    return order_query


def _generate_shopify_inventorySetQuantities_query(inventory_data):
    """Generate shopify inventory update query

    :param list inventory_data: Inventory data that will be updated on Shopify. Each item includes:
        - offer (ecommerce.offer): The offer whose quantity will be updated.
        - location (ecommerce.location): The location at which the quantity should be updated.
        - quantity (int): The product quantity.
    """
    quantities_data = []
    for inventory_data in inventory_data:
        quantities_data.append("""
        {
            changeFromQuantity: null
            inventoryItemId: \"%s\"
            locationId: \"%s\"
            quantity: %s
        }
        """ % (
            const.GLOBAL_INVENTORY_ITEM_ID + inventory_data['offer'].shopify_inventory_item_id,
            const.GLOBAL_LOCATION_ID + inventory_data['location'].ecommerce_location_identifier,
            int(inventory_data['quantity'])
            )
        )
    inventory_query = """
    mutation InventoryUpdate {
        inventorySetQuantities(
            input: {
                name: \"available\"
                reason: \"correction\"
                quantities: [%s]
            }
        ){
            userErrors {
                message
            }
        }
    }
    """ % ''.join(quantities_data)
    # name = available, which is used to set absolute quantity
    # reason = correction, Used to correct an inventory error or as a general adjustment reason.
    return inventory_query


# === Make Query Request === #
def call_shopify_graphql_query(account, endpoint, params={}):
    """Call Shopify GraphQL Admin API for query(fetch data).

    :param account: record of `ecommerce.account`
    :param str endpoint: objects for mutation on shopify.
        valid values:
        - 'shop'  : Fetch shop data for authentication.
        - 'order' : Fetch order by identifier.

    :return response: response from shopify
    :rtype dict:
    """
    request_url = f"https://{account.shopify_store}.myshopify.com/admin/api/{const.SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': account.shopify_access_token,
        'Content-Type': 'application/json',
    }
    query = ''
    if endpoint == 'shop':
        query = _generate_shopify_shop_query()
    elif endpoint == 'order':
        order_id = params.get('order_id')
        query = _generate_shopify_order_by_id_query(order_id)
    response = _call_shopify_graphql_admin_api(headers, request_url, query)
    _handle_query_error(response, request_url)
    res = response['data']
    if endpoint == 'order':
        if not res['order']:
            raise ECommerceApiError(f"There is no order exists on shopify, related to {order_id}")
            # A null order comes from Shopify for a wrong ID, so this logic prevents it.
            # For fetching locations/products/orders, if they cannot be fetched, an empty list is returned.
            # But for fetching an order by reference, if it does not exist, Shopify returns null.

        order = _shopify_prepare_order_structure(res['order'])
        return order
    return res


# === Make Pagination Request === #
def call_shopify_graphql_with_pagination(account, endpoint, params={}):
    """Call Shopify GraphQL Admin API with cursor-based pagination.

    :param account: record of `ecommerce.account`
    :param str endpoint: Resource to fetch from Shopify.
        valid values:
        - 'locations' : Fetch locations from shopify.
        - 'products'  : Fetch products from shopify.
        - 'orders'    : Fetch orders from shopify.

    :return response: response from shopify
    :rtype dict:
    """
    request_url = f"https://{account.shopify_store}.myshopify.com/admin/api/{const.SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': account.shopify_access_token,
        'Content-Type': 'application/json',
    }
    result_data = []
    has_next_page = True
    next_page = ''
    while has_next_page:
        query_params = {'after': next_page}
        query_params.update(params)
        query = globals()[f'_generate_shopify_{endpoint}_query'](**query_params)
        response = _call_shopify_graphql_admin_api(headers, request_url, query)
        _handle_query_error(response, request_url)
        edges = response['data'][endpoint]['edges']
        result_data.extend(globals()[f'_shopify_prepare_{endpoint}_structure'](edges))
        has_next_page = response['data'][endpoint]['pageInfo']['hasNextPage']
        next_page = response['data'][endpoint]['pageInfo']['endCursor']
    return {endpoint: result_data}


# === Make Mutation Request === #
def call_shopify_graphql_mutation(account, endpoint, params={}):
    """Call Shopify GraphQL Admin API for mutation.

    :param account: record of `ecommerce.account`
    :param str endpoint: objects for mutation on shopify.
        valid values:
        - 'fulfillmentCreate'      : For create fulfillment on shopify.
        - 'inventorySetQuantities' : For update inventory on shopify.

    :return response: response from shopify
    :rtype dict:
    """
    request_url = f"https://{account.shopify_store}.myshopify.com/admin/api/{const.SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        'X-Shopify-Access-Token': account.shopify_access_token,
        'Content-Type': 'application/json',
    }
    request_query = ''
    if endpoint == 'fulfillmentCreate':
        picking = params.get('picking')
        request_query = _generate_shopify_fulfillmentCreate_query(picking, headers, request_url)
    elif endpoint == 'inventorySetQuantities':
        inventory_data = params.get('inventory_data')
        request_query = _generate_shopify_inventorySetQuantities_query(inventory_data)
    response = _call_shopify_graphql_admin_api(headers, request_url, request_query)
    _handle_mutation_error(endpoint, response, request_url)
    res = {}
    if endpoint == 'fulfillmentCreate':
        res.update({'id': response['data'][endpoint]['fulfillment']['id'].replace(const.GLOBAL_FULFILLMENT_ID, '')})
    return res


# === Prepare Response Structure === #
def _shopify_prepare_locations_structure(edges):
    locations_data = []
    for edge in edges:
        node = edge['node']
        locations_data.append({
            'id': node['id'].replace(const.GLOBAL_LOCATION_ID, ''),
            'name': node['name'],
        })
    return locations_data


def _shopify_prepare_products_structure(edges):
    products_data = []
    for edge in edges:
        product_node = edge['node']
        for variant in product_node['variants']['nodes']:
            products_data.append({
                'shopify_inventory_item_id': variant['inventoryItem']['id'].replace(const.GLOBAL_INVENTORY_ITEM_ID, ''),
                'sku': variant['sku'],
                'name': product_node['title'] if variant['title'] == 'Default Title' else f"{product_node['title']} ({variant['title']})",
                'ec_product_identifier': variant['id'].replace(const.GLOBAL_PRODUCT_VARIANT_ID, ''),
                'ec_product_template_identifier': product_node['id'].replace(const.GLOBAL_PRODUCT_ID, ''),
            })
    return products_data


def _shopify_prepare_orders_structure(edges):
    orders_data = []
    for edge in edges:
        node = edge['node']
        orders_data.append(_shopify_prepare_order_structure(node))
    return orders_data


def _shopify_prepare_order_structure(order_node):
    """Prepare shopify order structure from order data returned by shopify."""
    billing_address = order_node.get('billingAddress') or (order_node.get('customer') or {}).get('defaultAddress')
    email = ((order_node.get('customer') or {}).get('defaultEmailAddress') or {}).get('emailAddress')
    shipping_address = order_node.get('shippingAddress')
    order = {
        'billing_address': {
            'city': billing_address.get('city'),
            'country_code': billing_address.get('countryCodeV2'),
            'email': email,
            'name': ((billing_address.get('firstName') or '') + ' ' + (billing_address.get('lastName') or '')).strip(),
            'phone': billing_address.get('phone'),
            'state_code': billing_address.get('provinceCode'),
            'street': billing_address.get('address1'),
            'street2': billing_address.get('address2'),
            'zip': billing_address.get('zip'),
        } if billing_address else {},
        'currency_code': order_node.get('currencyCode'),
        'customer_id': (order_node.get('customer') or {}).get('id', '').replace(const.GLOBAL_CUSTOMER_ID, ''),
        'financial_status': order_node.get('displayFinancialStatus'),
        'date_order': convert_iso_to_utc(order_node.get('createdAt')),
        'fulfillments': _shopify_prepare_fulfillments_structure(order_node.get('fulfillments')),
        'id': order_node.get('id').replace(const.GLOBAL_ORDER_ID, ''),
        'order_lines': _shopify_prepare_order_lines_structure(order_node.get('lineItems').get('nodes')),
        'reference': order_node.get('name'),
        'shipping_address': {
            'city': shipping_address.get('city'),
            'country_code': shipping_address.get('countryCodeV2'),
            'email': email,
            'name': ((shipping_address.get('firstName') or '') + ' ' + (shipping_address.get('lastName') or '')).strip(),
            'phone': shipping_address.get('phone'),
            'state_code': shipping_address.get('provinceCode'),
            'street': shipping_address.get('address1'),
            'street2': shipping_address.get('address2'),
            'zip': shipping_address.get('zip'),
        } if shipping_address else {},
        'shipping_lines': _shopify_prepare_shipping_lines_structure(order_node.get('shippingLines').get('nodes')),
        'status': 'canceled' if order_node.get('cancelledAt') else 'confirmed',
        'write_date': convert_iso_to_utc(order_node.get('updatedAt')),
    }
    return order


def _shopify_prepare_fulfillments_structure(fulfillments_data):
    """Prepare shopify fulfillments structure from fulfillments data returned by shopify."""
    fulfillments = []
    for fulfillment_data in fulfillments_data:
        tracking_company = ((fulfillment_data.get('trackingInfo') and fulfillment_data.get('trackingInfo')[0] or {}).get('company') or '')
        if tracking_company:
            tracking_company = re.sub(r"\s+", "", tracking_company)
            tracking_company = re.sub(r"\(", "_", tracking_company)
            tracking_company = re.sub(r"\)(?!$)", "_", tracking_company)
            tracking_company = re.sub(r"\)$", "", tracking_company).lower()
        fulfillment = {
            'carrier_id': tracking_company,
            'ecommerce_picking_identifier': fulfillment_data.get('id').replace(const.GLOBAL_FULFILLMENT_ID, ''),
            'location_id': fulfillment_data.get('location').get('id').replace(const.GLOBAL_LOCATION_ID, ''),
            'status': 'canceled' if fulfillment_data.get('status') in ['CANCELLED', 'ERROR', 'FAILURE'] else 'confirmed',
            'tracking_number': (fulfillment_data.get('trackingInfo') and fulfillment_data.get('trackingInfo')[0] or {}).get('number'),
        }
        line_items = []
        for line_item in fulfillment_data.get('fulfillmentLineItems').get('nodes'):
            data = {
                'ecommerce_line_identifier': line_item.get('lineItem').get('id').replace(const.GLOBAL_LINE_ITEM_ID, ''),
                'ecommerce_move_identifier': line_item.get('id').replace(const.GLOBAL_FULFILLMENT_LINE_ITEM_ID, ''),
                'quantity': line_item.get('quantity'),
            }
            line_items.append(data)
        fulfillment['line_items'] = line_items
        fulfillments.append(fulfillment)
    return fulfillments


def _shopify_prepare_order_lines_structure(line_nodes):
    """Prepare shopify order line structure from line item data returned by shopify."""
    order_lines = []
    for line_node in line_nodes:
        order_line = {
            'description': line_node.get('name'),
            'discount_amount': _calculate_shopify_discount(line_node.get('discountAllocations')),
            'id': line_node.get('id').replace(const.GLOBAL_LINE_ITEM_ID, ''),
            'price_unit': line_node.get('originalUnitPriceSet').get('shopMoney').get('amount'),
            'product_data': {
                'shopify_inventory_item_id': line_node.get('variant').get('inventoryItem').get('id').replace(const.GLOBAL_INVENTORY_ITEM_ID, ''),
                'ec_product_identifier': line_node.get('variant').get('id').replace(const.GLOBAL_PRODUCT_VARIANT_ID, ''),
                'ec_product_template_identifier': line_node.get('product').get('id').replace(const.GLOBAL_PRODUCT_ID, ''),
                'name': (line_node['title'] + ' (' + line_node.get('variantTitle') + ')') if line_node.get('variantTitle') else line_node['title'],
                'sku': line_node.get('sku'),
            } if line_node.get('variant') else {},
            'qty_ordered': line_node.get('quantity', 0),
            'tax_amount': _calculate_shopify_tax(line_node.get('taxLines')),
        }
        order_lines.append(order_line)
    return order_lines


def _shopify_prepare_shipping_lines_structure(line_nodes):
    """Prepare shopify shipping line structure from shipping line data returned by shopify."""
    shipping_lines = []
    for line_node in line_nodes:
        shipping_line = {
            'description': line_node.get('title'),
            'discount_amount': _calculate_shopify_discount(line_node.get('discountAllocations')),
            'id': 'shopify_ship_' + str(line_node.get('id').replace(const.GLOBAL_SHIPPING_LINE_ID, '')),
            'price_unit': line_node.get('originalPriceSet').get('shopMoney').get('amount'),
            'shipping_code': line_node.get('title'),
            'tax_amount': _calculate_shopify_tax(line_node.get('taxLines')),
        }
        shipping_lines.append(shipping_line)
    return shipping_lines


# === Helper methods === #
def _calculate_shopify_tax(tax_lines):
    total_tax = 0
    for line in tax_lines:
        total_tax += float(line.get('priceSet', {}).get('shopMoney', {}).get('amount', 0))

    return total_tax


def _calculate_shopify_discount(discount_lines):
    total_discount = 0
    for line in discount_lines:
        total_discount += float(line.get('allocatedAmountSet').get('shopMoney').get('amount'))
    return total_discount


def convert_iso_to_utc(iso_date):
    """Converts Shopify ISO 8601 date to Odoo datetime format"""
    try:
        if not iso_date:
            return False
        date_obj = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        formatted_date = date_obj.astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        return formatted_date
    except Exception:
        return False
