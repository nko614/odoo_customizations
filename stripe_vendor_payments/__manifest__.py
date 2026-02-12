# -*- coding: utf-8 -*-
{
    'name': 'Stripe Vendor Payments',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Send payments to vendors via Stripe Connect',
    'description': """
        MVP Module for Stripe Vendor Payments
        ======================================
        
        Features:
        - Send money to vendors via Stripe
        - Initiate KYC onboarding from Odoo
        - Extend vendor bill payment functionality
    """,
    'author': 'NKO',
    'depends': ['account', 'base', 'account_batch_payment'],
    'data': [
        'security/ir.model.access.csv',
        'data/account_payment_method_data.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_batch_payment_views.xml',
        'wizard/stripe_payment_wizard_views.xml',
        'wizard/stripe_batch_payment_wizard_views.xml',
        'data/stripe_config.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}