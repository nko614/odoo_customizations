{
    'name': 'NADA Automated Receipts',
    'version': '1.0.1',
    'category': 'Inventory/Purchase',
    'summary': 'Auto-generate POs from blanket orders based on forecasted inventory',
    'depends': ['purchase_requisition', 'purchase_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/receipt_run_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
