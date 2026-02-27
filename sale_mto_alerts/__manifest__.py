{
    "name": "Sale MTO Alerts",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Customer notes warning, MTO component stock alerts, and alternative variant recommendations",
    "description": "Warns salesperson of customer notes on quotation, checks MTO component stock on order lines, and recommends in-stock alternative product variants.",
    "author": "NKO",
    "depends": ["sale_stock", "sale_mrp", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/mto_stock_wizard_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
