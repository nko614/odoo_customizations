{
    'name': 'Split Shipping',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Split deliveries by shipment date on sale order lines',
    'description': """
        This module adds split shipping functionality to sale orders:
        - Add a "Split Shipping" option on sale orders
        - When enabled, each sale order line can have a shipment date
        - On confirmation, creates separate delivery orders grouped by shipment date
    """,
    'author': 'Custom',
    'depends': ['sale_stock', 'delivery'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
