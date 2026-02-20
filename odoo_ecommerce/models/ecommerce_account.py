# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

import dateutil.parser
import psycopg2
from odoo import SUPERUSER_ID, Command, _, api, fields, models, modules
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.modules.registry import Registry
from odoo.service.model import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY
from odoo.tools import groupby

from ..utils import ECommerceApiError, ensure_account_is_authenticated

_logger = logging.getLogger(__name__)


class ECommerceAccount(models.Model):
    _name = "ecommerce.account"
    _description = "E-commerce Account"
    _check_company_auto = True

    name = fields.Char(
        required=True,
    )
    active = fields.Boolean(
        help="If made inactive, this account will no longer be synchronized with E-commerce Platform.",
        default=True,
    )

    # channel fields
    ecommerce_channel_id = fields.Many2one(
        comodel_name="ecommerce.channel",
        string="E-commerce Channel",
        required=True,
    )
    channel_code = fields.Char(
        related="ecommerce_channel_id.code",
    )

    # support featuers fields.
    support_location = fields.Boolean(
        related='ecommerce_channel_id.support_location'
    )
    support_shipping = fields.Boolean(
        related='ecommerce_channel_id.support_shipping'
    )

    # configuration fields
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    fulfilled_by = fields.Selection(
        string="Delivery Handled On",
        selection=[
            ('odoo', "Odoo"),
            ('ecommerce', "E-commerce Platform"),
        ],
        required=True,
        default='odoo'
    )
    location_id = fields.Many2one(
        string="Stock Location",
        help="The location of the stock managed by E-commerce Platform",
        comodel_name='stock.location',
        domain='[("usage", "=", "internal")]',
        check_company=True,
    )
    team_id = fields.Many2one(
        comodel_name='crm.team',
        string="Sales Team"
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        default=lambda self: self.env.user
    )
    update_inventory = fields.Boolean(
        string="Update Inventory",
        help="When enabled, this option allows the inventory to be updated on the e-commerce platform.",
        default=True
    )

    # Display fields.
    state = fields.Selection(
        selection=[
            ("connected", "Connected"),
            ("disconnected", "Disconnected"),
        ],
        string="State",
        default="disconnected"
    )
    ecommerce_offer_ids = fields.One2many(
        comodel_name='ecommerce.offer',
        string="E-commerce Offers",
        inverse_name='ecommerce_account_id',
        bypass_search_access=True
    )
    default_product_ids = fields.Many2many(
        string="Default Products",
        comodel_name='product.product',
        compute='_compute_default_product_ids',
        context={'active_test': False},
    )
    sale_order_ids = fields.One2many(
        comodel_name='sale.order',
        string="Sale Orders",
        inverse_name='ecommerce_account_id'
    )
    ecommerce_location_ids = fields.One2many(
        comodel_name='ecommerce.location',
        string="E-commerce Locations",
        inverse_name='ecommerce_account_id',
        bypass_search_access=True
    )

    # last sync date fields.
    last_products_sync = fields.Datetime(
        string="Last Products Sync",
        help="The last time products were synced with E-commerce Platform.",
        required=True,
        default=fields.Datetime.now,
    )
    last_orders_sync = fields.Datetime(
        string="Last Orders Sync",
        help="The last time orders were synced with E-commerce Platform.",
        required=True,
        default=fields.Datetime.now,
    )

    # count fields.
    offer_count = fields.Integer(string="E-commerce Offer Count", compute="_compute_offer_count")
    order_count = fields.Integer(string="E-commerce Order Count", compute="_compute_order_count")
    location_count = fields.Integer(string="E-commerce Location Count", compute="_compute_location_count")

    _unique_name = models.Constraint(
        "UNIQUE(company_id, name)",
        "The name must be unique within the same company",
    )

    # === ORM METHODS ===#

    def _valid_field_parameter(self, field, name):
        return name == "required_if_channel" or super()._valid_field_parameter(field, name)

    # === COMPUTE METHODS ===#

    def _compute_default_product_ids(self):
        ProductProduct = self.env['product.product']
        default_product = (
            self.env.ref('odoo_ecommerce.ecommerce_default_product', raise_if_not_found=False)
            or ProductProduct._restore_data_product("E-commerce Sales", 'consu', 'ecommerce_default_product')
        )
        discount_product = (
            self.env.ref('odoo_ecommerce.ecommerce_default_discount', raise_if_not_found=False)
            or ProductProduct._restore_data_product("E-commerce Discount", 'service', 'ecommerce_default_discount')
        )
        shipping_product = (
            self.env.ref('odoo_ecommerce.ecommerce_default_shipping', raise_if_not_found=False)
            or ProductProduct._restore_data_product("E-commerce Shipping", 'service', 'ecommerce_default_shipping')
        )
        for account in self:
            account.default_product_ids = default_product + shipping_product + discount_product

    @api.depends('ecommerce_offer_ids')
    def _compute_offer_count(self):
        offers_data = self.env['ecommerce.offer']._read_group(
            [('ecommerce_account_id', 'in', self.ids)],
            groupby=['ecommerce_account_id'],
            aggregates=['__count'],
        )
        accounts_data = {account.id: count for account, count in offers_data}
        for account in self:
            account.offer_count = accounts_data.get(account.id, 0)

    @api.depends('sale_order_ids')
    def _compute_order_count(self):
        orders_data = self.env['sale.order']._read_group(
            [('ecommerce_account_id', 'in', self.ids)],
            groupby=['ecommerce_account_id'],
            aggregates=['__count'],
        )
        orders_per_account = {account.id: count for account, count in orders_data}
        for account in self:
            account.order_count = orders_per_account.get(account.id, 0)

    @api.depends('ecommerce_location_ids')
    def _compute_location_count(self):
        for account in self:
            account.location_count = len(account.ecommerce_location_ids)

    # === ONCHANGE METHODS === #

    @api.onchange('last_orders_sync')
    def _onchange_last_orders_sync(self):
        """ Display a warning about the possible consequences of modifying the last orders sync. """
        self.ensure_one()
        if self._origin.id:
            return {
                'warning': {
                    'title': self.env._("Warning"),
                    'message': self.env._(
                        "If the date is set in the past, orders placed on this %s "
                        "Account before the first synchronization of the module might be "
                        "synchronized with Odoo.\n"
                        "If the date is set in the future, orders placed on this %s "
                        "Account between the previous and the new date will not be "
                        "synchronized with Odoo." %
                        (self.ecommerce_channel_id.name, self.ecommerce_channel_id.name)
                    )
                }
            }

    @api.onchange('last_products_sync')
    def _onchange_last_products_sync(self):
        """ Display a warning about the possible consequences of modifying the last products sync. """
        self.ensure_one()
        if self._origin.id:
            return {
                'warning': {
                    'title': self.env._("Warning"),
                    'message': self.env._(
                        "If the date is set in the past, products created on this %s "
                        "Account before the first synchronization of the module might be "
                        "synchronized with Odoo.\n"
                        "If the date is set in the future, products created on this %s "
                        "Account between the previous and the new date will not be "
                        "synchronized with Odoo." %
                        (self.ecommerce_channel_id.name, self.ecommerce_channel_id.name)
                    )
                }
            }

    # === CRUD METHODS ===#

    @api.model_create_multi
    def create(self, vals_list):
        vals_grouped_by_channel = {}
        for vals in vals_list:
            channel_id = vals.get('ecommerce_channel_id')
            vals_grouped_by_channel.setdefault(channel_id, []).append(vals)

        for channel_id, grouped_vals_list in vals_grouped_by_channel.items():
            ecommerce_accounts_rg = self._read_group([('ecommerce_channel_id', '=', channel_id)], ['team_id', 'location_id'])
            ecommerce_teams_ids = [team.id for team, __ in ecommerce_accounts_rg]
            ecommerce_locations_ids = [location.id for __, location in ecommerce_accounts_rg]
            ecommerce_channel_name = self.env['ecommerce.channel'].browse(channel_id).name
            for vals in grouped_vals_list:
                # Find or create the location of the Ecommerce location to be associated with this account
                location = self.env['stock.location'].search([
                    *self.env['stock.location']._check_company_domain(vals.get('company_id')),
                    ('id', 'in', ecommerce_locations_ids),
                ], limit=1)
                if not location:
                    parent_location_data = self.env['stock.warehouse'].search_read(
                        [*self.env['stock.warehouse']._check_company_domain(self.env.company)],
                        ['view_location_id'],
                        limit=1,
                    )
                    location = self.env['stock.location'].create({
                        'name': vals.get('name') or ecommerce_channel_name,
                        'usage': 'internal',
                        'location_id': parent_location_data[0]['view_location_id'][0] if parent_location_data else False,
                        'company_id': vals.get('company_id'),
                    })
                vals.update({'location_id': location.id})

                # Find or create the sales team to be associated with this account
                team = self.env['crm.team'].search([
                    *self.env['crm.team']._check_company_domain(vals.get('company_id')),
                    ('id', 'in', ecommerce_teams_ids),
                ], limit=1)
                if not team:
                    team = self.env['crm.team'].create({
                        'name': vals.get('name') or ecommerce_channel_name,
                        'company_id': vals.get('company_id'),
                    })
                vals.update({'team_id': team.id})
        flat_vals_list = [vals for grouped_vals in vals_grouped_by_channel.values() for vals in grouped_vals]
        accounts = super().create(flat_vals_list)
        accounts._check_required_if_channel()
        return accounts

    def write(self, vals):
        result = super().write(vals)
        self._check_required_if_channel()
        return result

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        for ecommerce_account, vals in zip(self, vals_list):
            if "name" not in default:
                vals["name"] = self.env._("%s (copy)", ecommerce_account.name)
        return vals_list

    def log_xml(self, message, func, type='client', level='Error', name=''):
        self.env.flush_all()
        db_name = self.env.cr.dbname
        try:
            with Registry(db_name).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                IrLogging = env['ir.logging']
                IrLogging.sudo().create({
                    'name': name if name else f'{self.name}-{self.id}',
                    'type': type,
                    'dbname': db_name,
                    'level': level,
                    'message': message,
                    'path': 'E-Commerce',
                    'func': func,
                    'line': 1
                })
        except psycopg2.Error:
            pass

    # === ACTION METHODS ===#

    def action_archive(self):
        """Override to disconnect the E-commerce account before archiving it."""
        self.action_disconnect()
        return super().action_archive()

    # connect to the ecommerce platform
    def action_connect(self):
        self.state = "connected"
        return True

    # disconnect from the ecommerce platform
    def action_disconnect(self):
        self.state = "disconnected"
        return True

    @api.model
    def action_open_ecommerce_accounts(self, channel_code):
        ecommerce_channel = self.env.ref(
            f'ecommerce_{channel_code}.ecommerce_channel_{channel_code}'
        )
        accounts = self.env['ecommerce.account'].search([
            ('channel_code', '=', channel_code)
        ])
        action_open_ecommerce = {
            'type': 'ir.actions.act_window',
            'name': f'{ecommerce_channel.name} Accounts',
            'res_model': 'ecommerce.account',
            'context': {
                'default_ecommerce_channel_id': ecommerce_channel.id,
                'default_name': ecommerce_channel.name
            }
        }
        if not accounts:
            action_open_ecommerce.update({
                'view_mode': 'form',
                'target': 'current',
            })
        else:
            action_open_ecommerce.update({
                'view_mode': 'list,form',
                'domain': [('channel_code', '=', channel_code)],
            })
        return action_open_ecommerce

    def action_view_ecommerce_offers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Offers"),
            'res_model': 'ecommerce.offer',
            'view_mode': 'list',
            'domain': [('ecommerce_account_id', '=', self.id)],
            'context': {'default_ecommerce_account_id': self.id}
        }

    def action_view_ecommerce_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Orders"),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('ecommerce_account_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_view_ecommerce_location(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Locations"),
            'res_model': 'ecommerce.location',
            'view_mode': 'list,form',
            'domain': [('ecommerce_account_id', '=', self.id)],
            'context': {'default_ecommerce_account_id': self.id}
        }

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Logs"),
            'res_model': 'ir.logging',
            'view_mode': 'list,form',
            'domain': [('name', '=', f"{self.name}-{self.id}")],
            'context': {'create': False}
        }

    def action_sync_products(self):
        return self._sync_products()

    def action_sync_orders(self):
        return self._sync_orders()

    def action_sync_locations(self):
        return self._sync_locations()

    def action_update_pickings(self):
        return self._update_pickings()

    def action_update_inventory(self):
        return self._update_inventory()

    def action_ecommerce_recover_order(self):
        self.ensure_one()
        return {
            'name': _("Recover Order"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ecommerce.recover.order.wizard',
            'target': 'new',
        }

    # === SETUP METHODS === #

    def _check_required_if_channel(self):
        """Check that channel-specific required fields have been filled.

        The fields that have the `required_if_channel='<channel_code>'` attribute are made
        required for all `ecommerce.account` records with the `channel_code` field equal to
        `<channel_code>` and with the `state` field equal to `'connected'`.

        Channel-specific views should make the form fields required under the same conditions.

        :return: None
        :raise ValidationError: If a channel-specific required field is empty.
        """
        field_names = []
        for field_name, field in self._fields.items():
            required_for_channel_code = getattr(field, "required_if_channel", None)
            if required_for_channel_code and any(
                required_for_channel_code == account.channel_code and not account[field_name]
                for account in self
            ):
                ir_field = self.env["ir.model.fields"]._get(self._name, field_name)
                field_names.append(ir_field.field_description)
        if field_names:
            raise ValidationError(
                self.env._("The following fields must be filled: %s", ", ".join(field_names))
            )

    # === SYNC METHODS === #

    def _sync_products(self, auto_commit=True):
        """
        We commit the changes after each offer is successfully processed.
        This allows us to retain the processed offers if an error occurs in any offer or in any account.
        """
        count_fetched = 0
        count_processed = 0
        count_failed = []
        for account in self:
            try:
                ensure_account_is_authenticated(account)
                result = account._fetch_products_from_ecommerce()
            except (ECommerceApiError, UserError) as error:
                account.log_xml(
                    "An error occurred while fetching products for %s account with id %s."
                    "Error description: %s" %
                    (account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                    '_sync_products',
                    'server'
                )
                continue  # skip this account and continue with the next one
            products_data = result.get("products", [])
            count_fetched += len(products_data)
            for product_data in products_data:
                try:
                    processed_offer = None
                    if auto_commit:
                        with self.env.cr.savepoint():
                            processed_offer = account._find_or_create_offer(product_data, auto_match=True)
                    else:  # Avoid the savepoint in testing
                        processed_offer = account._find_or_create_offer(product_data, auto_match=True)
                    if processed_offer:
                        count_processed += 1
                except Exception as error:
                    if modules.module.current_test:
                        raise  # we are executing during testing, do not try to rollback
                    if isinstance(error, PG_CONCURRENCY_EXCEPTIONS_TO_RETRY):
                        account.log_xml(
                            "A concurrency error occurred while processing the offer data "
                            "with ec_product_identifier %s for %s account with id %s."
                            "Error description: %s" %
                            (product_data.get("ec_product_identifier"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                            '_sync_products',
                        )
                        raise
                    account.log_xml(
                        "Error occurred while processing the product data "
                        "with ec_product_identifier '%s' for %s account with id '%s'."
                        "Error description: %s" %
                        (product_data.get("ec_product_identifier"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                        '_sync_products',
                    )
                    self.env.cr.rollback()
                    count_failed.append(product_data.get("ec_product_identifier"))
                if auto_commit:
                    self.env.cr.commit()
            account.last_products_sync = fields.Datetime.now()
        message = "No products found."
        if count_fetched:
            message = f"Fetched: {count_fetched} | Processed: {count_processed} | Failed: {len(count_failed)}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if count_failed else "success",
                "title": self.env._("Product Sync Summary") if count_fetched else '',
                "message": self.env._(message),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    def _sync_orders(self, auto_commit=True):
        """Synchronize the account's sales orders that were recently updated on E-commerce Platform.

        Note: This method is called by the `ir_cron_ecommerce_sync_orders` cron.

        :param bool auto_commit: Whether the database cursor should be committed as soon as an order
                                 is successfully synchronized.
        :return: None
        """
        domain = Domain([
            ('active', '=', True),
            ('state', '=', 'connected')
        ])
        accounts = self.filtered(domain) if self else self.search(domain)
        for account in accounts:
            if account.support_location:
                account.action_sync_locations()
        count_fetched = 0
        count_processed = 0
        count_failed = []
        for account in accounts:
            account = account.with_prefetch()  # Avoid pre-fetching after each cache invalidation.
            try:
                ensure_account_is_authenticated(account)
                result = account._fetch_orders_from_ecommerce()
            except (ECommerceApiError, UserError) as error:
                account.log_xml(
                    "An error occurred while fetching orders for %s account with id %s."
                    "Error description: %s" %
                    (account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                    '_sync_orders',
                    'server'
                )
                continue  # skip this account and continue with the next one
            orders_data = result.get("orders") or []
            count_fetched += len(orders_data)
            for order_data in orders_data:
                try:
                    processed_order = None
                    if auto_commit:
                        with self.env.cr.savepoint():
                            processed_order = account._process_order_data(order_data)
                    else:  # Avoid the savepoint in testing
                        processed_order = account._process_order_data(order_data)
                    if processed_order:
                        count_processed += 1
                except Exception as error:
                    if modules.module.current_test:
                        raise  # we are executing during testing, do not try to rollback
                    if isinstance(error, PG_CONCURRENCY_EXCEPTIONS_TO_RETRY):
                        account.log_xml(
                            "A concurrency error occurred while processing the order data "
                            "with ec_order_identifier %s for %s account with id %s."
                            "Error description: %s" %
                            (order_data.get("id"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                            '_sync_orders'
                        )
                        raise
                    self.env.cr.rollback()
                    account._handle_sync_failure(
                        flow="order_sync", data={"ec_order_ref": order_data.get("reference")}, error_messages=str(error).split('DETAIL')[0]
                    )
                    account.log_xml(
                        "Error occurred while processing the order data "
                        "with ec_order_identifier %s for %s account with id %s. "
                        "Error description: %s" %
                        (order_data.get("id"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                        '_sync_orders',
                        'server'
                    )
                    count_failed.append(order_data.get("id"))
                    continue  # Skip these order data and resume with the next ones.
                if auto_commit:
                    self.env.cr.commit()
            account.last_orders_sync = fields.Datetime.now()
        message = "No orders found."
        if count_fetched:
            message = f"Fetched: {count_fetched} | Processed: {count_processed} | Failed: {len(count_failed)} | Not confirmed: {count_fetched - count_processed - len(count_failed)}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if count_failed else "success",
                "title": self.env._("Order Sync Summary") if count_fetched else '',
                "message": self.env._(message),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    def _sync_order_by_reference(self, ecommerce_order_ref):
        ensure_account_is_authenticated(self)
        try:
            result = self._fetch_order_from_ecommerce_by_order_ref(ecommerce_order_ref)
        except ECommerceApiError as error:
            raise UserError(self.env._("Error during fetching orders from %s account: %s", self.name, str(error).split('DETAIL')[0])) from error
        self._process_order_data(result)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": 'success',
                "title": self.env._("Order Sync:"),
                "message": self.env._(f'Order with reference {result.get("id")} was fetched and processed successfully.'),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    def _sync_locations(self, auto_commit=True):
        """
        We commit the changes after each location is successfully processed.
        This allows us to retain the processed location if an error occurs in any location or in any account.
        """
        count_fetched = 0
        count_processed = 0
        count_failed = []
        for account in self:
            try:
                ensure_account_is_authenticated(account)
                result = account._fetch_locations_from_ecommerce()
            except (ECommerceApiError, UserError) as error:
                account.log_xml(
                    "An error occurred while fetching locations for %s account with id %s."
                    "Error description: %s" %
                    (account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                    '_sync_locations',
                    'server'
                )
                continue  # skip this account and continue with the next one
            locations_data = result.get("locations", [])
            count_fetched += len(locations_data)
            for location_data in locations_data:
                try:
                    proccessed_location = None
                    if auto_commit:
                        with self.env.cr.savepoint():
                            proccessed_location = account._find_or_create_location(location_data.get("id"), location_data.get("name"))
                    else:  # Avoid the savepoint in testing
                        proccessed_location = account._find_or_create_location(location_data.get("id"), location_data.get("name"))
                    if proccessed_location:
                        count_processed += 1
                except Exception as error:
                    if modules.module.current_test:
                        raise  # we are executing during testing, do not try to rollback
                    if isinstance(error, PG_CONCURRENCY_EXCEPTIONS_TO_RETRY):
                        account.log_xml(
                            "A concurrency error occurred while processing the location data "
                            "with id %s for %s account with id %s."
                            "Error description: %s" %
                            (location_data.get("id"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                            '_sync_locations',
                        )
                        raise
                    account.log_xml(
                        "Error occurred while processing the location data "
                        "with id '%s' for %s account with id '%s'. "
                        "Error description: %s" %
                        (location_data.get("id"), account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                        '_sync_locations',
                    )
                    self.env.cr.rollback()
                    count_failed.append(location_data.get("id"))
                if auto_commit:
                    self.env.cr.commit()
        message = "No locations found."
        if count_fetched:
            message = f"Fetched: {count_fetched} | Processed: {count_processed} | Failed: {len(count_failed)}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if count_failed else "success",
                "title": self.env._("Location Sync Summary") if count_fetched else '',
                "message": self.env._(message),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    def _update_pickings(self):
        """Update the pickings created in case of fulfilled by odoo to the E-commerce platform.

        Note: This method is called by the `ir_cron_ecommerce_update_pickings` cron.

        :return: None
        """
        domain = Domain([
            ('active', '=', True),
            ('state', '=', 'connected'),
            ('fulfilled_by', '=', 'odoo'),
            ('support_shipping', '=', True)
        ])
        accounts = self.filtered(domain) if self else self.search(domain)
        count_total = 0
        count_success = 0
        count_failed = 0
        for account in accounts:
            pickings = self.env["stock.picking"].search([
                ("state", "=", "done"),
                ("sale_id.ecommerce_account_id", "=", account.id),
                ("ecommerce_sync_status", "=", "pending"),
            ])
            count_total += len(pickings)
            try:
                ensure_account_is_authenticated(account)
            except UserError:
                count_failed += len(pickings)
                account.log_xml(
                    "skip updating pickings for the account with id %s because the account is not authenticated." % account, id,
                    '_update_pickings',
                )
                continue
            account._update_pickings_to_ecommerce(pickings)
            count_success += len(pickings.filtered(lambda d: d.ecommerce_sync_status == 'done'))
            count_failed += len(pickings.filtered(lambda d: d.ecommerce_sync_status == 'error'))
        message = "No pickings found for update."
        if count_total:
            message = f"Total: {count_total} | Updated: {count_success} | Failed: {count_failed}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if count_failed else "success",
                "message": self.env._(message),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    @api.model
    def _update_pickings_to_ecommerce_via_pickings(self, pickings):
        """Update the pickings created in case of fulfilled by odoo to the E-commerce platform.

        Note: This method is call from `stock.picking`

        :return: None
        """
        count_total = 0
        count_success = 0
        count_failed = 0
        pickings = pickings.filtered(
            lambda picking: picking.sale_id and
            picking.ec_account_id and
            picking.ecommerce_sync_status != 'done'
        )
        accounts = groupby(pickings, key=lambda picking: picking.sale_id.ecommerce_account_id)
        for account, pickings in accounts:
            count_total += len(pickings)
            try:
                ensure_account_is_authenticated(account)
            except UserError:
                count_failed += len(pickings)
                account.log_xml(
                    "skip updating pickings for the account with id %s because the account is not authenticated." % account, id,
                    '_update_pickings_to_ecommerce_via_pickings',
                )
                continue
            pickings_rs = self.env['stock.picking'].browse([d.id for d in pickings])
            account._update_pickings_to_ecommerce(pickings_rs)
            count_success += len(pickings_rs.filtered(lambda d: d.ecommerce_sync_status == 'done'))
            count_failed += len(pickings_rs.filtered(lambda d: d.ecommerce_sync_status == 'error'))
        message = "No pickings found for update."
        if count_total:
            message = f"Total: {count_total} | Updated: {count_success} | Failed: {count_failed}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if count_failed else "success",
                "message": self.env._(message),
                "next": {"type": "ir.actions.act_window_close"},
            }
        }

    def _update_inventory(self):
        domain = Domain([
            ('active', '=', True),
            ('state', '=', 'connected'),
            ('update_inventory', '=', True)
        ])
        accounts = self.filtered(domain) if self else self.search(domain)
        notification_type = 'success'
        for account in accounts:
            try:
                ensure_account_is_authenticated(account)
            except UserError:
                account.log_xml(
                    "skip updating inventory for the account with id %s because the account is not authenticated." % account, id,
                    '_update_inventory',
                )
                continue  # skip this account and continue with the next one
            locations = account.ecommerce_location_ids.filtered(lambda location: location.sync_stock)
            offers = account.ecommerce_offer_ids.filtered(lambda offer: offer.sync_stock)
            inventory_data = []
            for offer in offers:
                if not account.support_location:
                    inventory_data.append({
                        'offer': offer,
                        'quantity': offer.matched_product_id.free_qty
                    })
                    continue
                for location in locations:
                    quantity = offer.matched_product_id.with_context(location=location.matched_location_id.id).free_qty
                    inventory_data.append({
                        'offer': offer,
                        'location': location,
                        'quantity': quantity,
                    })
            if inventory_data:
                try:
                    account._update_inventory_to_ecommerce(inventory_data)
                except ECommerceApiError as error:
                    account._handle_sync_failure(
                        flow="inventory_update", error_messages=str(error).split('DETAIL')[0]
                    )
                    account.log_xml(
                        "Error occurred while update inventory on %s account with id %s"
                        "Error description: %s" %
                        (account.ecommerce_channel_id.name, account.id, str(error).split('DETAIL')[0]),
                        'update_inventory',
                        'server'
                    )
                    notification_type = 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': self.env._("Inventory successfully updated to ecommerce platform." if notification_type == 'success' else "Error occuer during update inventory to ecommerce platform."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    # === FIND OR CREATE METHODS === #

    def _find_or_create_offer(self, product_data, auto_match=True):
        """Find & update or create the ecommerce offer based on the product/listing/offer sku.

        :param dict product_data: The product data to find & update or create the offer from.
        :param bool auto_match: Whether to automatically match the product based on SKU.
        :return: The ecommerce offer.
        :rtype: recordset of `ecommerce.offer`
        """
        offer = self.ecommerce_offer_ids.filtered(
            lambda offer: offer.sku == (product_data.get("sku") or None))
        if offer:
            offer.write(product_data)
        else:
            offer = self.env["ecommerce.offer"].with_context(tracking_disable=True).create({
                **product_data,
                "sku": product_data.get("sku") or None,
                "ecommerce_account_id": self.id,
                "matched_product_id": self._find_matching_product(
                    product_data["sku"] if auto_match else None, "ecommerce_default_product", "E-commerce Sales", "consu"
                ).id,
            })
        return offer

    def _find_or_create_moves(self, order, order_location_id, fulfillments):
        """Generate a stock move for each product of the provided sales order.

        :param recordset order: The sales order to generate the stock moves for, as a `sale.order`
                                record.
        :param int order_location_id: record set of 'stock.location' where the generated stock moves will be created in case location is not come with fulfillment.
        :param list fulfillments: E-commerce fulfillment details; stock moves are generated
                                  only for the products included in these fulfillments.
        :return: None
        """
        customers_location = self.env.ref("stock.stock_location_customers")
        for fulfillment in fulfillments:
            existing_picking = self.env['stock.picking'].search([('ecommerce_picking_identifier', '=', str(fulfillment.get('ecommerce_picking_identifier')))])
            if existing_picking:
                if fulfillment.get('status') == 'canceled':
                    activity_message = self.env._(
                        f"This delivery has been cancelled on {self.ecommerce_channel_id.name}, "
                        f"please create return of this delivery to adjust the stock."
                    )
                    existing_picking.activity_schedule(
                        act_type_xmlid='mail.mail_activity_data_todo',
                        user_id=self.user_id.id,
                        note=activity_message,
                    )
                continue
            if fulfillment.get('status') == 'canceled':
                continue
            line_items = fulfillment.get('line_items', [])
            fulfillment_mapped_lines = {
                str(line_item.get('ecommerce_line_identifier')): line_item for line_item in line_items
            }
            stock_moves = self.env['stock.move']
            stock_location_id = (
                self._find_or_create_location(fulfillment.get("location_id")).matched_location_id
                if fulfillment.get("location_id")
                else order_location_id
            )
            for order_line in order.order_line.filtered(
                lambda l: l.product_id.type != "service" and not l.display_type
            ):
                if fulfillment_mapped_lines.get(order_line.ecommerce_line_identifier):
                    picking_type_id = self.env['stock.picking.type'].search([
                        ('code', '=', 'outgoing'), ('warehouse_id', '=', order_line.warehouse_id.id)
                    ], limit=1)
                    stock_move = self.env["stock.move"].create({
                        "company_id": self.company_id.id,
                        "product_id": order_line.product_id.id,
                        "product_uom_qty": fulfillment_mapped_lines[order_line.ecommerce_line_identifier].get('quantity'),
                        "product_uom": order_line.product_uom_id.id,
                        "location_id": stock_location_id.id,
                        "location_dest_id": customers_location.id,
                        "state": "draft",
                        "sale_line_id": order_line.id,
                        "picking_type_id": picking_type_id.id,
                        "ecommerce_move_identifier": fulfillment_mapped_lines[order_line.ecommerce_line_identifier].get('ecommerce_move_identifier')
                    })
                    stock_move._action_confirm()
                    stock_move._action_assign()
                    stock_move._set_quantity_done(fulfillment_mapped_lines[order_line.ecommerce_line_identifier].get('quantity'))
                    stock_move.picked = True  # To also change move lines created in `_set_quantity_done`
                    stock_moves |= stock_move
            if stock_moves:
                stock_moves._action_done()
                shipping_code = fulfillment.get('carrier_id')
                shipping_product = self._find_matching_product(
                    shipping_code, 'ecommerce_default_shipping', 'E-commerce Shipping', 'service'
                )
                tracking_ref = fulfillment.get('tracking_number')
                vals = {
                    'ecommerce_picking_identifier': str(fulfillment.get('ecommerce_picking_identifier')),
                }
                if tracking_ref:
                    vals.update({
                        'carrier_tracking_ref': tracking_ref,
                    })
                if shipping_code:
                    vals.update({
                        'carrier_id': self._find_or_create_delivery_carrier(shipping_code, shipping_product).id,
                    })
                vals['partner_id'] = order.partner_shipping_id.id

                stock_moves[0].picking_id.write(vals)

    def _find_or_create_delivery_carrier(self, shipping_code, shipping_product):
        """ Find or create a delivery carrier based on the shipping code.

        :param str shipping_code: The shipping code.
        :param record shipping_product: The shipping product matching the shipping code, as a
                                        `product.product` record.
        :return: The delivery carrier.
        :rtype: delivery.carrier
        """
        shipping_code = shipping_code.strip()
        delivery_method = self.env['delivery.carrier'].search(
            ['|', ('name', '=', shipping_code), ('delivery_type', '=', shipping_code)], limit=1,
        )
        if not delivery_method:
            delivery_method = self.env['delivery.carrier'].create({
                'name': shipping_code,
                'product_id': shipping_product.id,
                'is_create_from_ecommerce': True
            })
        return delivery_method

    def _find_or_create_partner(self, address_data, address_type):
        """Find or create a partner based on the provided address data.
        The contact partner is searched based on all the personal information and only if the
        email is provided in address_data. A match thus only occurs if the customer had already made a
        previous order and if the personal information provided by the API did not change in the
        meantime. If there is no match, a new contact partner is created.

        :param dict address_data: The address data to find or create the partner from.
        :param str address_type: The type of the partner - 'contact', 'invoice', 'delivery', 'other'.
        :return: The found or created partner as a `res.partner` record.
        :rtype: recordset of `res.partner`
        """
        name = address_data.get("name")
        email = address_data.get("email")
        phone = address_data.get("phone")
        street = address_data.get("street")
        street2 = address_data.get("street2")
        zip_code = address_data.get("zip")
        city = address_data.get("city")
        state_code = address_data.get("state_code")
        country_code = address_data.get("country_code")
        country = self.env["res.country"].search([
            ("code", "=", country_code)
        ], limit=1)
        state = self.env["res.country.state"].search([
            ("country_id", "=", country.id),
            "|", ("code", "=ilike", state_code), ("name", "=ilike", state_code),
        ], limit=1)

        partner_vals = {
            "name": name or f"{self.ecommerce_channel_id.name} Customer # {address_data.get('customer_id')}",
            "email": email,
            "phone": phone,
            "street": street,
            "street2": street2,
            "zip": zip_code,
            "city": city,
            "state_id": state.id,
            "country_id": country.id,
            "customer_rank": 1,
            "type": address_type,
            "is_company": address_data.get("is_company"),
            "vat": address_data.get("vat"),
            "company_id": self.company_id.id,
        }

        # Search for an existing partner based on the personal information and email.
        partner = self.env["res.partner"].search([
            *self.env["res.partner"]._check_company_domain(self.company_id),
            ("name", "=", name),
            ("email", "=", email),
        ], limit=1) if email else None
        if partner and not (
            partner.phone == phone
            and partner.street == street
            and (not partner.street2 or partner.street2 == street2)
            and partner.zip == zip_code
            and partner.city == city
            and partner.state_id.id == state.id
            and partner.country_id.id == country.id
        ):
            partner_vals.update({"parent_id": partner.id})
            partner = self.env["res.partner"].search([
                *self.env["res.partner"]._check_company_domain(self.company_id),
                ("parent_id", "=", partner.id),
                ("type", "=", address_type),
                ("name", "=", name),
                ("street", "=", street),
                "|", ("street2", "=", False), ("street2", "=", street2),
                ("zip", "=", zip_code),
                ("city", "=", city),
                ("country_id", "=", country.id),
                ("state_id", "=", state.id),
            ], limit=1)
        if not partner:
            partner = self.env["res.partner"].with_context(tracking_disable=True).create(partner_vals)
        return partner

    def _find_or_create_partners_from_data(self, order_data):
        """Find or create the contact and delivery partners based on the provided customer data.

        :param dict order_data: The order data to find or create the partners from.
        :return: The contact and delivery partners, as `res.partner` records. When the contact
                 partner acts as delivery partner, the records are the same.
        :rtype: tuple[recordset of `res.partner`, recordset of `res.partner`]
        """

        billing_address = order_data.get("billing_address")
        shipping_address = order_data.get("shipping_address")
        billing_partner = self.env["res.partner"]  # invoice_partner contact_partner
        shipping_partner = self.env["res.partner"]  # delivery_partner

        is_billing_address_present = billing_address and any(billing_address.values())
        is_shipping_address_present = shipping_address and any(shipping_address.values())
        if not is_billing_address_present and not is_shipping_address_present:
            default_partner_name = f'{self.ecommerce_channel_id.name} Customer ' + order_data.get('reference')
            default_partner = self.env['res.partner'].create({
                'name': default_partner_name
            })
            return default_partner, default_partner

        billing_partner = self._find_or_create_partner(
            billing_address if is_billing_address_present else shipping_address, "invoice")
        if not is_shipping_address_present:
            return billing_partner, billing_partner
        shipping_partner = self._find_or_create_partner(shipping_address, "delivery")
        for other_address in order_data.get("other_addresses") or []:
            self._find_or_create_partner(other_address, "other")

        # if partners have no state, despite receiving state code
        # then create an activity to set state because in case of
        # fulfillment by merchant state_code is needed.
        state_code = order_data.get("billing_address", {}).get("state_code")
        if billing_partner and state_code and not billing_partner.state_id:
            billing_partner._ecommerce_create_activity_set_state(self.user_id.id, state_code)
        state_code = order_data.get("shipping_address", {}).get("state_code")
        if shipping_partner and state_code and not shipping_partner.state_id:
            shipping_partner._ecommerce_create_activity_set_state(self.user_id.id, state_code)
        return billing_partner, shipping_partner

    def _find_or_create_pricelist(self, currency):
        """Find or create the pricelist based on the currency.

        :param recordset currency: The currency of the pricelist, as a `res.currency` record.
        :return: The pricelist.
        :rtype: recordset of `product.pricelist`
        """
        pricelist = self.env["product.pricelist"].with_context(active_test=False).search([
            *self.env["product.pricelist"]._check_company_domain(self.company_id),
            ("currency_id", "=", currency.id),
        ], limit=1)
        if not pricelist:
            pricelist = self.env["product.pricelist"].with_context(tracking_disable=True).create({
                "name": f"{self.ecommerce_channel_id.name} Pricelist {currency.name}",
                "active": False,
                "currency_id": currency.id,
                "company_id": self.company_id.id,
            })
        return pricelist

    def _find_or_create_location(self, identifier, name=None):
        """Find & update or create the ecommerce location based on the identifier of location.

        :param str identifier: The location identifier of ecommerce location.
        :param str name: Name of ecommerce location.
        :return: The ecommerce location.
        :rtype: recordset of `ecommerce.location`
        """
        location = self.ecommerce_location_ids.filtered(
            lambda location: location.ecommerce_location_identifier == str(identifier))
        if name and location and location.name != name:
            location.name = name
        elif not location:
            location = self.env["ecommerce.location"].create({
                "name": name,
                "ecommerce_location_identifier": identifier,
                "ecommerce_account_id": self.id,
                "matched_location_id": self.location_id.id,
            })
        return location

    # === HELPER METHODS === #

    # FIXME: should this be on ecommerce.offer?
    def _get_product_url(self, offer):
        """Override this method to return the ecommerce's merchant portal product page URL.

        :rtype: str
        """
        return ""

    def _process_order_data(self, order_data):
        """Process the provided order data and return the matching sales order, if any.

        If no matching sales order is found, a new one is created if it is in a 'synchronizable'
        If the matching sales order already exists and the E-commerce order was canceled.

        :param dict order_data: The order data to process.
        :return: The matching ecommerce order, if any, as a `sale.order` record.
        :rtype: recordset of `sale.order`
        """
        self.ensure_one()

        ecommerce_order_identifier = order_data.get("id")
        order = self.sale_order_ids.filtered(lambda order:
            order.ecommerce_order_identifier == str(ecommerce_order_identifier))
        status = order_data.get("status") or "confirmed"  # Default to `confirmed`
        fulfillments = order_data.get("fulfillments")
        if not order:  # order not found.
            if status == "confirmed":
                order = self._create_order_from_data(order_data)
                if self.fulfilled_by == 'ecommerce' and fulfillments:
                    location_id = self._get_order_location(order_data)
                    self._find_or_create_moves(order, location_id, fulfillments)
                order.with_context(mail_notrack=True).action_lock()
                _logger.info(
                    "Created a new sales order with order reference %(ref)s for %(code)s account"
                    " with id %(id)s.", {"ref": ecommerce_order_identifier, "code": self.channel_code, "id": self.id}
                )
            else:
                self.log_xml(
                    message="Ignored order with reference %s because of status %s for %s account with id %s." %
                    (ecommerce_order_identifier, status, self.ecommerce_channel_id.name, self.id),
                    func='_process_order_data',
                    level='Info'
                )
        else:  # The sales order already exists
            if self.fulfilled_by == 'ecommerce' and fulfillments:
                location_id = self._get_order_location(order_data)
                self._find_or_create_moves(order, location_id, fulfillments)
            if status == "canceled" and order.state != "cancel":
                order.with_context(canceled_by_ecommerce=True)._action_cancel()
                _logger.info(
                    "Cancelled sales order with order reference %(ref)s for %(code)s account with id"
                    " %(id)s.", {"ref": ecommerce_order_identifier, "code": self.channel_code, "id": self.id}
                )
            else:
                _logger.info(
                    "Ignored already synchronized sales order with order reference %(ref)s for"
                    " ecommerce account with id %(id)s.", {"ref": ecommerce_order_identifier, "id": self.id}
                )
        if self.fulfilled_by == 'odoo' and fulfillments:
            order._create_activity_resolve_fulfillment_conflict(self.user_id.id)
        return order

    def _create_order_from_data(self, order_data):
        """ Create a new sales order based on the provided order data.

        :param dict order_data: The order data to create a sales order from.
        :return: The newly created sales order.
        :rtype: record of `sale.order`
        """
        order_vals = self._prepare_order_values(order_data)
        order = self.env["sale.order"].with_context(
            mail_create_nosubscribe=True
        ).with_company(self.company_id).create(order_vals)
        return order

    def _prepare_order_values(self, order_data):
        ecommerce_order_identifier = order_data.get("id")
        currency_code = order_data.get('currency_code')
        if currency_code:
            currency = self.env['res.currency'].with_context(active_test=False).search(
                [('name', '=', currency_code)], limit=1
            )
        else:
            currency = self.company_id.currency_id
        contact_partner, delivery_partner = self._find_or_create_partners_from_data(order_data)
        fiscal_position = self.env["account.fiscal.position"].with_company(
            self.company_id
        )._get_fiscal_position(contact_partner, delivery_partner)
        order_lines_values = self._prepare_order_lines_values(
            order_data, currency, fiscal_position
        )
        order_vals = {
            "origin": f"{self.ecommerce_channel_id.name} Order # {ecommerce_order_identifier}",
            "state": "sale",
            "locked": self.fulfilled_by == "ecommerce" and self.support_shipping,  # sale order is created in locked state for fulfilled_by ecommerce and support shipping for avoid creation of pickings during action_lock().
            "date_order": order_data.get("date_order") and dateutil.parser.parse(order_data.get("date_order")).replace(tzinfo=None) or None,  # default current date.
            "partner_id": contact_partner.id,
            "partner_shipping_id": delivery_partner.id,
            "pricelist_id": self._find_or_create_pricelist(currency).id,
            "order_line": [Command.create(order_line_values) for order_line_values in order_lines_values],
            "invoice_status": "no",
            "require_signature": False,
            "require_payment": False,
            "fiscal_position_id": fiscal_position.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "team_id": self.team_id.id,
            "ecommerce_order_identifier": ecommerce_order_identifier,
            "ec_order_ref": order_data.get("reference"),
            "ecommerce_account_id": self.id,
        }
        order_vals["warehouse_id"] = self._get_order_location(order_data).warehouse_id.id

        return order_vals

    def _prepare_order_lines_values(self, order_data, currency, fiscal_pos):
        """Prepare the values for the order lines to create based on E-commerce data.

        :param dict order_data: The order data related to the item data.
        :param record currency: The currency of the sales order, as a `res.currency` record.
        :param record fiscal_pos: The fiscal position of the sales order, as an
                                  `account.fiscal.position` record.
        :return: The order lines values.
        :rtype: dict
        """
        order_lines_values = []
        lines_data = order_data.get("order_lines") or []
        for line_data in lines_data:
            offer = self._find_or_create_offer(line_data.get("product_data"))
            qty_ordered = float(line_data.get("qty_ordered") or 0.0)
            price_unit = float(line_data.get("price_unit") or 0.0)
            price_subtotal = float(line_data.get("price_subtotal", price_unit * qty_ordered))
            tax_amount = float(line_data.get("tax_amount") or 0.0)
            product_taxes = offer.matched_product_id.taxes_id.filtered_domain(
                [*self.env["account.tax"]._check_company_domain(self.company_id)]
            )
            taxes = fiscal_pos.map_tax(product_taxes) if fiscal_pos else product_taxes
            subtotal = self._recompute_subtotal(
                price_subtotal, tax_amount, taxes, currency
            )
            discount_amount = float(line_data.get("discount_amount", 0))
            discount_tax = float(line_data.get("discount_tax", 0))
            discount_subtotal = self._recompute_subtotal(
                discount_amount, discount_tax, taxes, currency
            )
            order_lines_values.append({
                "name": self.env._(line_data.get("description") or f'[{offer.sku}] {offer.name}'),
                "product_id": offer.matched_product_id.id,
                "product_uom_qty": qty_ordered,
                "price_unit": (subtotal / qty_ordered) if qty_ordered else 0,
                "discount": (discount_subtotal / subtotal) * 100 if subtotal else 0,
                "tax_ids": [Command.link(tax.id) for tax in taxes],
                "display_type": line_data.get("display_type", False),
                "ecommerce_line_identifier": str(line_data.get("id")),
            })
        discount_lines = order_data.get('discount_lines') or []
        for discount_line in discount_lines:
            discount_product = self._find_matching_product(
                None, 'ecommerce_default_discount', 'E-commerce Discount', 'service'
            )
            price_unit = float(discount_line.get("price_unit") or 0.0)
            tax_amount = float(discount_line.get("tax_amount") or 0.0)
            product_taxes = discount_product.taxes_id.filtered_domain(
                [*self.env["account.tax"]._check_company_domain(self.company_id)]
            )
            taxes = fiscal_pos.map_tax(product_taxes) if fiscal_pos else product_taxes
            subtotal = self._recompute_subtotal(
                price_unit, tax_amount, taxes, currency
            )
            order_lines_values.append({
                "name": self.env._(discount_line.get("description") or f'[{self.ecommerce_channel_id.name}] Discount'),
                "product_id": discount_product.id,
                "product_uom_qty": 1.0,
                "price_unit": (-1 * subtotal) if subtotal else 0,
                "tax_ids": [Command.link(tax.id) for tax in taxes],
            })

        shipping_lines = order_data.get("shipping_lines") or []
        for shipping_line in shipping_lines:
            shipping_code = shipping_line.get("shipping_code")
            shipping_product = self._find_matching_product(
                shipping_code, 'ecommerce_default_shipping', 'E-commerce Shipping', 'service'
            )
            price_unit = float(shipping_line.get("price_unit") or 0.0)
            tax_amount = float(shipping_line.get("tax_amount") or 0.0)
            product_taxes = shipping_product.taxes_id.filtered_domain(
                [*self.env["account.tax"]._check_company_domain(self.company_id)]
            )
            taxes = fiscal_pos.map_tax(product_taxes) if fiscal_pos else product_taxes
            subtotal = self._recompute_subtotal(
                price_unit, tax_amount, taxes, currency
            )
            discount_amount = float(shipping_line.get("discount_amount", 0))
            discount_tax = float(shipping_line.get("discount_tax", 0))
            discount_subtotal = self._recompute_subtotal(
                discount_amount, discount_tax, taxes, currency
            )
            order_lines_values.append({
                "name": self.env._(shipping_line.get("description") or f'[{shipping_code}] Shipping'),
                "product_id": shipping_product.id,
                "product_uom_qty": 1.0,
                "price_unit": subtotal if subtotal else 0,
                "discount": (discount_subtotal / subtotal) * 100 if subtotal else 0,
                "tax_ids": [Command.link(tax.id) for tax in taxes],
                "ecommerce_line_identifier": str(shipping_line.get("id")),
            })

        return order_lines_values

    @api.model
    def _recompute_subtotal(self, subtotal, tax_amount, taxes, currency):
        """Recompute the subtotal from the tax amount and the taxes.

        As it is not always possible to find the right tax record for a tax rate computed from the
        tax amount because of rounding errors or because of multiple taxes for a given rate, the
        taxes on the product are used instead.

        To achieve this, the subtotal is recomputed from the taxes for the total to match that of
        the order in E-commerce Platform. If the taxes used are not identical to that used by E-commerce Platform, the
        recomputed subtotal will differ from the original subtotal.

        :param float subtotal: The original subtotal to use for the computation of the base total.
        :param float tax_amount: The original tax amount to use for the computation of the base
                                 total.
        :param recordset taxes: The final taxes to use for the computation of the new subtotal, as
                                an `account.tax` recordset.
        :param recordset currency: The currency used by the rounding methods, as a `res.currency`
                                   record.
        :return: The new subtotal.
        :rtype: float
        """
        total = subtotal + tax_amount
        taxes_res = taxes.with_context(force_price_include=True).compute_all(
            total, currency=currency
        )
        subtotal = taxes_res["total_excluded"]
        for tax_res in taxes_res["taxes"]:
            tax = self.env["account.tax"].browse(tax_res["id"])
            if tax.price_include:
                subtotal += tax_res["amount"]
        return subtotal

    def _get_order_location(self, order_data):
        """ Get location based on the provided order_data

        :param dict order_data: The order data related to the item data.
        :return: Stock Location
        :rtype: record of `stock.location`
        """
        if not self.ecommerce_channel_id.support_location:
            return self.location_id
        location_identifier = order_data.get('location_id')
        if not location_identifier:
            if len(self.ecommerce_location_ids) == 1:
                return self.ecommerce_location_ids.matched_location_id
            else:
                return self.location_id
        ecommerce_location = self._find_or_create_location(location_identifier)
        return ecommerce_location.matched_location_id

    def _find_matching_product(
        self, internal_reference, default_xmlid, default_name, default_type, fallback=True
    ):
        """ Find the matching product for a given internal reference.

        If no product is found for the given internal reference, we fall back on the default
        product. If the default product was deleted, we restore it.

        Note: self.ensure_one()

        :param str internal_reference: The internal reference of the product to be searched.
        :param str default_xmlid: The xmlid of the default product to use as fallback.
        :param str default_name: The name of the default product to use as fallback.
        :param str default_type: The product type of the default product to use as fallback.
        :param bool fallback: Whether we should fall back to the default product when no product
                              matching the provided internal reference is found.
        :return: The matching product.
        :rtype: recordset of `product.product`
        """
        product = self.env['product.product'].search([
            *self.env['product.product']._check_company_domain(self.company_id),
            ('default_code', '=', internal_reference),
        ], limit=1) if internal_reference else self.env['product.product']
        if not product and fallback:  # Fallback to the default product
            product = self.env.ref('odoo_ecommerce.%s' % default_xmlid, raise_if_not_found=False)
        if not product and fallback:  # Restore the default product if it was deleted
            product = self.env['product.product']._restore_data_product(
                default_name, default_type, default_xmlid
            )
        return product

    def _post_process_after_picking_update_success(self, picking, identifier):
        """
        This method is called after a picking is successfully updated to the E-commerce.

        :param picking: Record of `stock.picking` that was updated.
        :param identifier: E-commerce picking identifier returned by the E-commerce
                        after a successful update.
        """
        picking.ecommerce_picking_identifier = str(identifier)
        picking.ecommerce_sync_status = 'done'
        _logger.info(
            "Picking %s updated successfully to %s.",
            picking.name, self.ecommerce_channel_id.name
        )
        message_post = _("This picking has been successfully updated to the %s.", self.ecommerce_channel_id.name)
        picking.message_post(body=message_post)

    def _post_process_after_picking_update_failed(self, picking, error):
        """
        This method is called when a picking fails to be updated to the E-commerce.

        :param picking: Record of `stock.picking` that failed to be updated.
        :param error: Error message describing the failure.
        """
        picking.ecommerce_sync_status = 'error'
        message_post = self.env._("Error during update this picking to %s: %s", self.ecommerce_channel_id.name, error)
        picking.message_post(body=message_post)
        self._handle_sync_failure(
            flow="picking_update", error_messages=[{'ec_order_ref': picking.ecommerce_order_identifier, 'message': str(error).split('DETAIL')[0]}]
        )
        self.log_xml(
            "Error occurred while update picking with id %s on %s account with id %s "
            "Error description: %s" %
            (picking.id, self.ecommerce_channel_id.name, self.id, str(error).split('DETAIL')[0]),
            '_post_process_after_picking_update_failed',
            'server'
        )

    # === ABSTRACT METHODS === #

    def _fetch_products_from_ecommerce(self):
        """Override this method in each ecommerce module to
        fetch products from the ecommerce and return them.

        This method should return a dictionary with the following structure:
        {
            "products": [{
                "sku": "Stock Keeping Unit",
                "name": "Name of Product in E-commerce Platform",
                "ec_product_identifier": "Product/Offer ID in E-commerce Platform",
                "ec_product_template_identifier": "Product Template ID in E-commerce Platform",
                ...other ecommerce-specific offer fields as needed
            },...],
        }

        :rtype: dict
        """
        return {}

    def _fetch_orders_from_ecommerce(self):
        """Override this method in ecommerce modules to
        fetch orders from the ecommerce and return them in following common format.

        :return: An order structure dictionary with the following keys:
        "orders": list of orders sorted by write_date in ascending order
            - id (str): Unique identifier for the order on the ecommerce platform.
            - reference (str): Unique order reference for merchant (eg: S00018, #00018)
            - create_date (str): Creation date of the order.
            - write_date (str): Last updated date of the order in '%Y-%m-%d %H:%M:%S' format.
            - date_order (str): Order confirmation date in '%Y-%m-%d %H:%M:%S' format.
            - status (str): Order status with following possible values:
                - 'confirmed': pending, processing, on-hold, confirmed, completed
                - 'canceled': canceled, failed, trash, fraud
            - currency_code (str): Order currency code (e.g.: 'INR', 'USD').
            - shipping_price (str): Original shipping cost before any discounts.
            - shipping_tax_amount (str): Tax applied on the original shipping cost.
            - shipping_discount (str): Discount applied to the shipping cost.
            - shipping_discount_tax (str): Tax reduction corresponding to the shipping discount.
            - location_id (str): Identifier of the ecommerce location (ID, code, or reference) used to decrement stock quantity from the corresponding location in Odoo.

            - customer_id (str): ID, code or reference of the customer on ecommerce platform that uniquely identifies them.
            - billing_address (dict): Billing address fields:
                - name (str): Full name of the buyer or customer.
                - email (str): Email address of the buyer.
                - phone (str)
                - street (str)
                - street2 (str)
                - zip (str)
                - city (str)
                - state_code (str)
                - country_code (str)
                - is_company (bool): Whether the address is a company or not.
                - vat (str): If it is a company, VAT/Tax ID of it.
            - shipping_address (dict): Shipping address with same structure as above (required if fulfillment by merchant and not billing_address).
            - other_addresses (list of dict): Additional addresses (if any), same structure as above.

            - order_lines (list of dict): Order line items. Each item includes:
                - id (int): Internal line identifier.
                - description (str): Description of the product.
                - product_data (dict): Product details:
                    - name (str): Name of the product.
                    - sku (str): SKU of the product.
                    - ec_product_id (str): Unique identifier of the product in the ecommerce platform.
                    - (other ecommerce-specific ecommerce.offer attributes as needed)
                - uom (str): Unit of measure for the product.
                - qty_ordered (float): Quantity of the item ordered.
                - qty_shipped (float): Quantity of the item that has been shipped.
                - qty_delivered (float): Quantity of the item delivered to the customer.
                - qty_returned (float): Quantity of the item returned.
                - qty_refunded (float): Quantity of the item refunded.
                - qty_canceled (float): Quantity of the item canceled.
                - price_unit (float): Unit sale price of product excluding tax.
                - price_subtotal (float): Total price excluding tax.
                - price_total (float): Total price including tax.
                - discount_amount (float): Discount amount exluding tax.
                - discount_tax (float): Tax reduction corresponding to the discount.
                - tax_amount (float): Total tax amount applied to the item.
                - tax_percent (float): Tax percentage applied to the item.

            - shipping_lines (list of dict): Shipping line items. Each item includes:
                - id (int): Internal line identifier.
                - description (str): Description of the shipping line.
                - shipping_code (str): Shipping method code.(used to find product for shipping line)
                - price_unit (float): Price of particular shipping line.
                - discount_amount (float): Discount amount exluding tax.
                - discount_tax (float): Tax reduction corresponding to the discount.
                - tax_amount (float): Total tax amount applied to this shipping line.

            - discount_lines (list of dict): Discount line items. Each item includes:
                - description (str): Description of the discount line.
                - price_unit (float): Discount price of particular discount line excluding tax.
                - tax_amount (float): Total tax amount applied to this discount line.

            - fulfillments (list of dict): Fulfillments, Each fulfillment includes:
                - ecommerce_picking_identifier (int): Internal fulfillment identifier.
                - status (str): Fulfillment status with following possible values:
                    'confirmed': pending, processing, on-hold, confirmed, completed
                    'canceled': canceled, failed, trash, fraud
                - line_items (list of dict): line items of fulfillment. Each item includes:
                    - ecommerce_line_identifier (int): Internal line identifier of sale order.
                    - ecommerce_move_identifier (int): Internal fulfillment move identifier.
                    - quantity (int): Quantity fulfilled on this fulfillment for particular line item.
                - carrier_id (str): Name of delivery carrier.
                - tracking_number (str): Tracking number of fulfillment.
                - location_id (str): Identifier of the ecommerce location (ID, code, or reference) used to decrement stock quantity from the corresponding location in Odoo.
                - shipping_address (dict): Shipping address with same structure as billing_address of order.

        :rtype: dict
        """
        return {}

    def _fetch_order_from_ecommerce_by_order_ref(self, ecommerce_order_ref):
        """Override this method in the ecommerce modules to
        fetch orders from the ecommerce by order reference and
        return them in the same format as `_fetch_orders_from_ecommerce`.

        :return: An order structure dictionary with the same keys as `_fetch_orders_from_ecommerce`.
        """
        return {}

    def _fetch_locations_from_ecommerce(self):
        """ Override this method in ecommerce module to
        fetch locations from the ecommerce and return them.

        This method should return a dictionary with the following structure:
        {
            "locations": [{
                "id": "Unique identifier of ecommerce location",
                "name": "Name of Location in E-commerce platform",
            },...],
        }
        :rtype: dict
        """
        return {}

    def _update_pickings_to_ecommerce(self, pickings):
        """
        Override this method to update pickings

        :param pickings: stock.picking recordset to be updated to the E-commerce platform.

        Note:
            Each e-commerce platform must implement this logic appropriately.

            - If your E-commerce platform supports updating multiple pickings at once:
                * Update all pickings in a single request.
                * After processing, call `_post_process_after_picking_update_success` for successful pickings.
                * Call `_post_process_after_picking_update_failed` for failed pickings.

            - If your E-commerce platform does not support updating multiple pickings at once:
                * Update each picking individually.
                * On success, call `_post_process_after_picking_update_success`.
                * On failure, call `_post_process_after_picking_update_failed`.

            - If an error occurs for a single picking:
                * Do not raise the error at the base level.
                * Catch the error and call `_post_process_after_picking_update_failed` for that picking.
        """
        return {}

    def _update_inventory_to_ecommerce(self, inventory_data):
        """
        Override this method in each ecommerce model and implement the logic for updating inventory.

        Note: This method replace the quantity of particular product for particular location on Ecommerce platform.

        :param inventory_data: A list of dictionary containing inventory information to update.
            [
                {
                    'offer': record of ecommerce.offer,
                    'quantity': float,  # Quantity of the product to update
                    'location': record of ecommerce.location,  # location on which offer's inventory will be updated (not set if locations are not supported).
                },
                ...
            ]

        :rtype: dict
        """
        return {}

    def _handle_sync_failure(self, flow, data={}, error_messages=False, email_template_xmlid=None):
        """Send a mail to the responsible persons to report a synchronization failure.

        :param str flow: The flow for which the failure mail is requested. Supported flows are:
                        `inventory_update`, `order_sync`, `picking_update`.
        :param error_messages: A string for `order_sync` and `inventory_update`,
                              or a list of dictionaries for `picking_update`, where each item contains ec_order_ref and message.
        :return: None
        """
        self.ensure_one()
        _logger.error(
            "Failed to execute %s flow for %s Account %s with id %s: Error: %s",
            flow, self.ecommerce_channel_id.name, self.name, self.id, str(error_messages).split('DETAIL')[0]
        )
        flow_to_email_template_mapper = {
            "inventory_update": "odoo_ecommerce.inventory_update_failure",
            "order_sync": "odoo_ecommerce.order_sync_failure",
            "picking_update": "odoo_ecommerce.picking_update_failure",
        }
        mail_template_id = email_template_xmlid or flow_to_email_template_mapper.get(flow)
        if not mail_template_id:
            _logger.error("Unknown flow %s for failure notification.", flow)
            return

        mail_template = self.env.ref(mail_template_id, raise_if_not_found=False)
        if not mail_template:
            _logger.warning("The mail template with xmlid %s has been deleted.", mail_template_id)
        else:
            responsible_emails = {user.email for user in filter(
                None, (self.user_id, self.env.ref('base.user_admin', raise_if_not_found=False))
            ) if user.email}
            if not responsible_emails:
                _logger.error("No responsible email found for handle %s failure.", flow)
                return
            mail_template.with_context(**{
                "email_to": ','.join(responsible_emails),
                "ec_account_id": self.id,
                "ec_channel_name": self.ecommerce_channel_id.name,
                "ec_account_name": self.name,
                "ec_channel_code": self.channel_code,
                "error_messages": error_messages,
                **data,
            }).send_mail(self.env.user.id)
            _logger.info("Sent synchronization failure notification email to %s", ', '.join(responsible_emails))
