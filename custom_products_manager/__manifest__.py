{
    'name': 'Custom Products Manager',
    'version': '18.0.1.0',
    'category': 'Sales/Manufacturing',
    'summary': 'Create custom products and BOMs on-the-fly from sales orders',
    'description': """
    Custom Products Manager
    ======================
    
    This module allows you to create custom products and their Bill of Materials (BOM) 
    directly from sales orders with an intuitive UI/UX designed for custom product sales.
    
    Features:
    ---------
    * Create products instantly from sale order lines
    * Build BOM components with drag-and-drop interface
    * Template-based product creation for faster setup
    * Real-time cost calculation and pricing
    * Custom product variants and configurations
    * Integration with manufacturing workflows
    * Mobile-friendly responsive design
    
    Perfect for businesses selling custom-made products, configured items, 
    or any scenario where products are created on demand.
    """,
    'author': 'Custom Development Team',
    'website': 'https://www.example.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'product',
        'mrp',
        'stock',
        'purchase',
        'web',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/default_data.xml',
        'data/update_custom_product_routes.xml',
        
        # Views
        'views/sale_order_views.xml',
        'views/product_views.xml',
        'views/mrp_views.xml',
        'views/wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_products_manager/static/src/js/custom_product_widget.js',
            'custom_products_manager/static/src/js/dashboard.js',
            'custom_products_manager/static/src/xml/custom_product_templates.xml',
            'custom_products_manager/static/src/xml/dashboard_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': [
        'static/description/icon.svg',
        'static/description/icon.png',
        'static/src/img/hammer_icon.png',
    ],
    'external_dependencies': {
        'python': [],
    },
}