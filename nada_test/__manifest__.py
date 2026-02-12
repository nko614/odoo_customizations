{
    'name': 'Field Service Mileage Tracking',
    'version': '1.0',
    'category': 'Services/Field Service',
    'summary': 'Track mileage on FSM tasks and post as analytic expenses',
    'description': """
        Adds a mileage field to field service tasks.
        Configurable cost-per-mile in Field Service settings.
        Automatically posts mileage cost as an analytic expense when task is marked done.
    """,
    'depends': ['industry_fsm', 'account'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/project_task_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
