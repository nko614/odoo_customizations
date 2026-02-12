{
    'name': 'BAFE 2026 Margin',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Editable margin percentage on sale order lines',
    'depends': ['sale_margin'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
