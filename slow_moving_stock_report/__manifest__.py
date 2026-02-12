# -*- coding: utf-8 -*-
{
    'name': 'Slow Moving Stock Report',
    'version': '1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Track slow moving inventory over 30, 60, and 90 day periods',
    'description': """
        This module provides a report to identify slow moving stock items.
        It calculates the movement rate of products over different time periods:
        - 30 days
        - 60 days  
        - 90 days
        
        This helps warehouse managers identify items that need attention.
    """,
    'depends': ['stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/simple_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}