# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.odoo_ecommerce.utils import ecommerce_checks_and_cleanup

from . import models


def uninstall_hook(env):
    ecommerce_checks_and_cleanup(env, 'prestashop')
