#############################################################################
#
#    Critical Hits LLC
#
#    Copyright (C) 2025-TODAY Critical Hits LLC(<https://www.vikuno.com>)
#    Author: Critical Hits LLC(<https://www.vikuno.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    "name": "Delivery Route Optimizer",
    "version": "19.0.1.0.0",
    "category": "Inventory/Delivery",
    "summary": "Optimize delivery routes using Google Maps",
    "description": """
        Optimize delivery routes using Google Maps API:
        - Integrates with Google Maps API for route optimization (via secure proxy)
        - Calculates optimal delivery sequence
        - Updates delivery order sequence automatically
        - Manual optimization trigger available
    """,
    "author": "Critical Hits LLC",
    "company": "Critical Hits LLC",
    "maintainer": "Critical Hits LLC",
    "website": "https://vikuno.com",
    "depends": [
        "base",
        "sale",
        "purchase",
        "stock",
        "contacts",
    ],
    "data": [
        "views/stock_picking_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "price": 60,
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
