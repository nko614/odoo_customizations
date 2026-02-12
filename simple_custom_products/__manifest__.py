{
    'name': 'Simple Custom Products',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Create custom products and BOMs directly from sale order lines',
    'description': """
    Simple Custom Products
    ======================
    
    Adds a "Create Custom Product" button to sale order lines that:
    1. Opens a wizard to create a custom product
    2. Opens a wizard to create a BOM for that product
    3. Automatically adds the product to the sale order line
    4. All custom products are MTO by default
    """,
    'author': 'Custom Development',
    'depends': ['sale', 'mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views_temp.xml',
        'wizards/product_creator_views.xml',
        'wizards/bom_creator_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}