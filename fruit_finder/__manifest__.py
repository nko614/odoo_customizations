{
    "name": "Fruit Finder",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "USDA fruit and vegetable price data",
    "description": "Browse and search USDA Economic Research Service fruit and vegetable prices (2023). Includes fresh, frozen, canned, dried, and juice forms with price per pound and price per cup equivalent.",
    "author": "Nick Kosinski",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/fruit_price_views.xml",
        "data/fruit_data.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
