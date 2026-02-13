{
    "name": "Delivery Route Optimizer",
    "version": "19.0.1.1.0",
    "category": "Inventory/Delivery",
    "summary": "Optimize delivery routes using Google Route Optimization API",
    "description": """
        Optimize delivery routes using Google Route Optimization API:
        - Integrates with Google Route Optimization API
        - Calculates optimal delivery sequence for multiple stops
        - Updates delivery order sequence automatically
        - Open optimized route directly in Google Maps
        - Manual optimization trigger available
        - Route preview popover with embedded maps (NEW)
        - Per-delivery route visualization (NEW)
    """,
    "author": "NKO",
    "website": "",
    "depends": [
        "base",
        "stock",
        "web",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/delivery_route_wizard_views.xml",
        "views/stock_picking_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "delivery_optimizer/static/src/css/route_preview.css",
            "delivery_optimizer/static/src/js/google_map_embed.js",
            "delivery_optimizer/static/src/js/route_preview_button.js",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
