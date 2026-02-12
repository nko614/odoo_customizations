{
    'name': 'Board Footage',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Add board feet calculations and PDF visibility control to sale order lines',
    'description': """
        This module extends sale order lines with:
        - Board feet and feet calculations based on product dimensions
        - Length, width, and thickness fields for products
        - Automatic computation of board feet and feet values on sale order lines
        - Checkbox to hide specific lines from PDF reports while keeping them in subtotal
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['sale', 'product'],
    'data': [
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'report/sale_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
} 