# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from odoo.addons.odoo_ecommerce.utils import ecommerce_checks_and_cleanup


def uninstall_hook(env):
    ecommerce_checks_and_cleanup(env, 'bigcommerce')
