{
    'name': "Shopify Marketing Attribution",
    'version': '19.0.1.0',
    'summary': "Capture UTM source, medium, and campaign from Shopify orders into Odoo sale orders",
    'category': 'Sales/Sales',
    'description': """
Extends the Shopify ecommerce connector to pull marketing attribution data
(UTM source, medium, campaign) from Shopify's customerJourneySummary API
and populate the corresponding fields on Odoo sale orders.

Requires that Odoo link tracker URLs are used to drive traffic to the Shopify
storefront, so that UTM parameters are appended to the redirect URL and
captured by Shopify's session tracking.
    """,
    'depends': ['ecommerce_shopify', 'utm'],
    'author': "Odoo IN Pvt Ltd",
    'license': "OPL-1",
}
