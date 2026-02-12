{
    'name': 'Partial Disassembly',
    'version': '19.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Partially disassemble finished goods by selecting which sub-assemblies to remove',
    'description': """
        Allows partial disassembly of finished products. Select a manufactured product,
        pick which sub-assemblies to remove, and the system creates stock moves
        for just those components. The finished product stays in stock while
        removed parts are added to stock for separate shipping.
    """,
    'author': 'NKO',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/disassembly_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
