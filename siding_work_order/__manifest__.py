{
    'name': 'Siding Work Order!',
    'version': '1.0',
    'category': 'Operations',
    'summary': 'Manage siding work orders with comprehensive project details',
    'description': """
        Siding Work Order Management
        ============================
        
        This module provides comprehensive management for siding work orders including:
        - Project scope definition
        - Customer information management
        - Material specifications (vinyl, steel, hardboard, stucco)
        - Trim and soffit details
        - Window and door wrapping specifications
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/siding_work_order_views.xml',
        'views/siding_work_order_menu.xml',
        'report/siding_work_order_report.xml',
        'report/siding_work_order_template.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}