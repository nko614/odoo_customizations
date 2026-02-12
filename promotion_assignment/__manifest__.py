{
    'name': 'Promotion Assignments',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Manage exclusive product promotions per customer with date-range enforcement',
    'description': """
        Track promotional discounts assigned to specific customers for specific products
        during defined time periods. Enforces exclusivity: only one customer can hold a
        promotion on a given product during any overlapping date range.

        Features:
        - Exclusive promotion assignment per product/date range
        - Gantt timeline view by product
        - Pivot matrix view (customer x product)
        - Smart button linking to actual sale order lines during promo period
        - Computed revenue tracking per promotion
    """,
    'author': 'Custom',
    'depends': ['sale', 'web_gantt'],
    'data': [
        'security/ir.model.access.csv',
        'views/promotion_assignment_views.xml',
        'views/promotion_assignment_menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
