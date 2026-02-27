from odoo.addons.ecommerce_shopify import utils_graphql

from . import models

# ---------------------------------------------------------------------------
# Patch 1: Extend the Shopify GraphQL order query to include UTM attribution
# data from customerJourneySummary.
# ---------------------------------------------------------------------------
_original_order_common_query = utils_graphql._shopify_order_common_query


def _patched_shopify_order_common_query():
    original = _original_order_common_query()
    utm_fragment = """
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
# ---------------------------------------------------------------------------
_original_prepare_order_structure = utils_graphql._shopify_prepare_order_structure


def _patched_shopify_prepare_order_structure(order_node):
    order = _original_prepare_order_structure(order_node)

    journey = order_node.get('customerJourneySummary') or {}
    ready = journey.get('ready', False)
    utm_data = {'ready': ready}

    if ready:
        first_visit = journey.get('firstVisit') or {}
        utm_params = first_visit.get('utmParameters') or {}
        utm_data.update({
            'source': utm_params.get('source') or '',
            'medium': utm_params.get('medium') or '',
            'campaign': utm_params.get('campaign') or '',
        })

    order['utm_data'] = utm_data
    return order


utils_graphql._shopify_prepare_order_structure = _patched_shopify_prepare_order_structure
