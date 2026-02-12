{
    'name': 'LinkedIn Lead Webhook',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Receive LinkedIn follower data via webhook and create CRM leads',
    'description': """
        Webhook endpoint for external scrapers (PhantomBuster, Apify)
        to POST LinkedIn profile data. Creates res.partner + crm.lead
        with deduplication and import logging.
    """,
    'author': 'NKO',
    'depends': ['crm', 'utm'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'views/res_config_settings_views.xml',
        'views/linkedin_import_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
