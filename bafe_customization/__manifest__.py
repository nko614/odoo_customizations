{
    'name': 'BAFE Customization',
    'version': '1.0',
    'category': 'Purchase',
    'summary': 'Custom modifications for BAFE',
    'description': """
        Custom modifications for purchase orders and customer specific pricing
    """,
    'depends': ['base', 'purchase', 'sale', 'stock', 'purchase_stock'],
    'data': [
        'data/ir_sequence_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 