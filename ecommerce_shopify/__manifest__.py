# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Shopify",
    'version': '19.0.1.0',
    'summary': "Ecommerce connector for Odoo",
    'category': 'Sales/Sales',
    'description': """
Connector for Odoo to synchronize customers, products, orders, inventory, and deliveries between Shopify and Odoo.
    """,
    'depends': ['odoo_ecommerce'],
    'images': ['static/description/banner.jpg'],
    'data': [
        'data/ecommerce_channel_data.xml',

        'views/ecommerce_account_views.xml',
        'views/ecommerce_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ecommerce_shopify/static/src/js/shopify_app_url_copy_clipboard.js',
        ],
    },
    'author': "Odoo IN Pvt Ltd",
    'license': "OPL-1",
    'uninstall_hook': 'uninstall_hook',
    'price': "169.00",
    'currency': "USD",
}
