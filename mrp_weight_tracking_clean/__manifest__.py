{
    'name': 'MRP Weight Tracking Clean',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': 'Track weight changes during manufacturing work orders',
    'description': """
        This module adds weight tracking functionality to manufacturing work orders.
        It prompts for start and end weights, calculates the delta, and creates
        stock moves for the weight difference.
    """,
    'depends': ['mrp', 'mrp_workorder', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_workorder_views.xml',
        'views/mrp_weight_capture_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}