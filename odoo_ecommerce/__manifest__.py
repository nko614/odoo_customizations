# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "eCommerce Engine",
    'version': '19.0.1.0',
    'category': "Sales/Sales",
    'summary': "The ecommerce engine used by ecommerce channel modules.",
    'description': """
E-commerce base module to connect Odoo with various e-commerce platforms.
==========================================================================
This module provides the functionality to integrate Odoo with different e-commerce platforms,
enabling the synchronization of products, orders, inventory and other data across systems.
    """,
    'depends': ['sale_management', 'stock_delivery'],
    'data': [
        'security/ir.model.access.csv',
        'security/ecommerce_security.xml',

        'data/ecommerce_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',

        'views/ecommerce_account_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/stock_location_views.xml',
        'views/stock_picking_views.xml',
        'views/ecommerce_offer_views.xml',
        'views/ecommerce_location_views.xml',

        'wizards/ecommerce_recover_order_wizard_views.xml',
    ],
    'author': "Odoo IN Pvt Ltd",
    'installable': True,
    'application': True,
    'license': "OPL-1",
    'price': "30.00",
    'currency': "USD",
}
