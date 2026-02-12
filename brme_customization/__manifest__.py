{
    'name': 'Google Maps Helper',
    'version': '1.0.0',
    'category': 'Tools',
    'summary': 'Google Maps API integration helper',
    'author': 'Demo',
    'depends': [
        'base',
        'crm',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'views/crm_views.xml',
        'data/model_load_stub.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}