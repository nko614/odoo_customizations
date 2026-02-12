{
    'name': 'Dev App',
    'version': '1.0',
    'category': 'Sales',
    'summary': "Adds Devarsh's Field to Sale Orders",
    'description': """
        Simple module that adds a custom field called "Devarsh's Field" to sale orders.
    """,
    'author': 'Devarsh',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}