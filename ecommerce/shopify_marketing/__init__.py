import logging

from odoo.addons.ecommerce_shopify import utils_graphql

from . import models

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patch 1: Extend the Shopify GraphQL order query to include UTM attribution
# data from customAttributes (note attributes set by the storefront JS
# snippet) and customerJourneySummary (Shopify's native attribution).
# ---------------------------------------------------------------------------
_original_order_common_query = utils_graphql._shopify_order_common_query


def _patched_shopify_order_common_query():
    original = _original_order_common_query()
    utm_fragment = """
    customAttributes {
        key
        value
    }
    customerJourneySummary {
        ready
        firstVisit {
            utmParameters {
                campaign
                medium
                source
            }
        }
    }
    """
    return original + utm_fragment


utils_graphql._shopify_order_common_query = _patched_shopify_order_common_query

# ---------------------------------------------------------------------------
# Patch 2: Extract UTM data from the raw GraphQL order node and add it to the
# standardized order_data dict so it can be read during sale.order creation.
#
# Priority: customAttributes (from JS snippet, always available) takes
# precedence. Falls back to customerJourneySummary (Shopify native, may be
# delayed or unavailable).
# ---------------------------------------------------------------------------
_original_prepare_order_structure = utils_graphql._shopify_prepare_order_structure

UTM_ATTRIBUTE_KEYS = {'utm_source': 'source', 'utm_medium': 'medium', 'utm_campaign': 'campaign'}


def _patched_shopify_prepare_order_structure(order_node):
    order = _original_prepare_order_structure(order_node)

    utm_data = {}

    # --- Source 1: customAttributes (note attributes from JS snippet) ---
    custom_attrs = order_node.get('customAttributes') or []
    for attr in custom_attrs:
        key = attr.get('key', '')
        value = attr.get('value', '')
        if key in UTM_ATTRIBUTE_KEYS and value:
            utm_data[UTM_ATTRIBUTE_KEYS[key]] = value

    _logger.info(
        "shopify_marketing: order %s customAttributes UTM: %s",
        order.get('id'), utm_data,
    )

    # --- Source 2: customerJourneySummary (fallback) ---
    if not utm_data:
        journey = order_node.get('customerJourneySummary') or {}
        ready = journey.get('ready', False)
        _logger.info(
            "shopify_marketing: order %s customerJourneySummary raw: %s",
            order.get('id'), journey,
        )
        if ready:
            first_visit = journey.get('firstVisit') or {}
            utm_params = first_visit.get('utmParameters') or {}
            for key in ('source', 'medium', 'campaign'):
                val = utm_params.get(key)
                if val:
                    utm_data[key] = val

    _logger.info("shopify_marketing: order %s final utm_data: %s", order.get('id'), utm_data)

    order['utm_data'] = utm_data
    return order


utils_graphql._shopify_prepare_order_structure = _patched_shopify_prepare_order_structure
