{
    'name': 'Barcode State Field',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Add State field to barcode interface',
    'description': 'Adds a custom State selection field (New/Used) to barcode operations',
    'depends': ['stock', 'stock_barcode'],
    'data': [
        'views/barcode_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'barcode_state_field/static/src/css/barcode_state.css',
            'barcode_state_field/static/src/xml/barcode_state_template.xml',
            'barcode_state_field/static/src/js/barcode_state_field.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}