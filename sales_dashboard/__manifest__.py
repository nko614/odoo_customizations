{
    "name": "Sales Dashboard",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Daily sales dashboard showing confirmed orders and salesperson performance",
    "description": "Dashboard tracking today's confirmed sale orders with salesperson breakdown and totals.",
    "author": "NKO",
    "depends": ["sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/sales_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sales_dashboard/static/src/css/dashboard.css",
            "sales_dashboard/static/src/js/dashboard.js",
            "sales_dashboard/static/src/xml/dashboard.xml",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
