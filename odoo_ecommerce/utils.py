# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError


def ecommerce_checks_and_cleanup(env, channel_code):
    """checks and cleanup data related to the given ecommerce channel during module uninstallation."""
    account = env['ecommerce.account'].search([('channel_code', '=', channel_code)])
    if account:
        raise UserError(env._("Please uninstall the ecommerce account(s) related to %s module before uninstalling it.", channel_code))
    env['ecommerce.channel'].search([('code', '=', channel_code)]).unlink()


def ensure_account_is_authenticated(account):
    """Ensure that the ecommerce account is authenticated and ready to use."""
    account.ensure_one()
    if account.state == "disconnected":
        raise UserError(account.env._("The %s account is disconnected. Please connect it first.", account.ecommerce_channel_id.name))
    return True


class ECommerceApiError(Exception):
    """Custom exception for ECommerce API request errors."""
    pass


class ECommerceAccountWideError(ECommerceApiError):
    """Custom exception for account-wide ECommerce errors like Rate Limits, Authentication issues, API downtime, etc."""
    pass
