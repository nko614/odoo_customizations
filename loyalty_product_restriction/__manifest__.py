{
    'name': 'Loyalty Product Restriction',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Restrict which products can be paid for with loyalty points',
    'description': """
        This module allows you to restrict which products can be paid for using loyalty points.
        You can specify allowed products for each loyalty program.
    """,
    'depends': [
        'loyalty',
        'sale',
    ],
    'data': [
        'views/loyalty_program_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}