{
    'name': 'CLEN Customization',
    'version': '1.0',
    'category': 'Purchase',
    'summary': 'Customer-specific vendor management',
    'description': """
        Extends purchase and sale functionality to:
        - Support customer-specific vendors
        - Automatically select correct vendor based on end customer
        - Handle dropshipping to customer locations
    """,
    'depends': [
        'base',
        'purchase',
        'sale',
        'stock',
        'purchase_stock',
        'sale_stock',
    ],
    'data': [
        'views/product_supplierinfo_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 