# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Prestashop",
    'version': '19.0.1.0',
    'summary': "Ecommerce connector for Odoo",
    'category': 'Sales/Sales',
    'description': """
Connector for Odoo to synchronize customers, products, orders, inventory, and deliveries between PrestaShop and Odoo.
    """,
    'depends': ['odoo_ecommerce'],
    'images': ['static/description/banner.jpg'],
    'data': [
        'data/ecommerce_channel_data.xml',

        'views/ecommerce_account_views.xml',
        'views/ecommerce_menus.xml',
    ],
    'author': "Odoo IN Pvt Ltd",
    'license': "OPL-1",
    'uninstall_hook': 'uninstall_hook',
    'price': "169.00",
    'currency': "USD",
}
