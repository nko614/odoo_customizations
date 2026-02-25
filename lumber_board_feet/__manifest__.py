{
    'name': 'Lumber Board Feet',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Board feet calculation, pricing, and reporting for lumber products',
    'depends': [
        'product',
        'purchase',
        'sale',
        'stock',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/product_supplierinfo_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/stock_move_views.xml',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
