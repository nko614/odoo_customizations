{
    'name': 'Contact Radius Finder',
    'version': '1.0.0',
    'category': 'Contacts',
    'summary': 'Find contacts within a specified radius',
    'description': """
        Contact Radius Finder:
        - Select a source location
        - Specify a radius in miles
        - Find all contacts within that radius using Google Maps
    """,
    'author': 'Your Company',
    'depends': [
        'base',
        'contacts',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/contact_radius_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
