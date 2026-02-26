# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ecommerce_picking_identifier = fields.Char(
        string="E-commerce Picking Identifier", readonly=True, copy=False)
    ecommerce_sync_status = fields.Selection(
        string="E-commerce Synchronization Status",
        help="The synchronization status of the delivery order to the ecommerce platform:\n"
             "- Pending: The delivery order has been confirmed and will soon be synchronized.\n"
             "- Done: The delivery details have been processed.\n"
             "- Error: The synchronization of the delivery order failed.",
        selection=[
            ('pending', "Pending"),
            ('done', "Done"),
            ('error', "Error"),
        ],
        readonly=True,
        default='pending',
    )

    ecommerce_order_identifier = fields.Char(
        related='sale_id.ecommerce_order_identifier',
    )
    fulfilled_by = fields.Selection(related='ec_account_id.fulfilled_by')
    ec_account_id = fields.Many2one(related='sale_id.ecommerce_account_id', store=True)
    support_update_picking = fields.Boolean(compute='_compute_support_update_picking')

    _unique_ec_account_ec_picking_identifier = models.Constraint(
        'UNIQUE(ec_account_id, ecommerce_picking_identifier)',
        "E-commerce picking identifier should be unique per ecommerce account.",
    )

    @api.depends('state')
    def _compute_support_update_picking(self):
        for picking in self:
            ecommerce_account_id = picking.sale_id and picking.sale_id.ecommerce_account_id
            picking.support_update_picking = (
                picking.state == 'done' and
                ecommerce_account_id and
                ecommerce_account_id.active and
                ecommerce_account_id.ecommerce_channel_id.support_shipping and
                ecommerce_account_id.fulfilled_by == 'odoo'
            )

    # === ACTION METHODS ===#

    def action_update_pickings_to_ecommerce(self):
        return self.env['ecommerce.account']._update_pickings_to_ecommerce_via_pickings(self.filtered(lambda picking: picking.support_update_picking))

    def action_update_failed_pickings_to_ecommerce(self):
        failed_pickings = self.filtered(
            lambda picking: picking.state == 'done' and picking.ecommerce_sync_status == 'error',
        )
        return self.env['ecommerce.account']._update_pickings_to_ecommerce_via_pickings(failed_pickings.filtered(lambda picking: picking.support_update_picking))

    # === BUSINESS METHODS ===#

    def _check_carrier_details_compliance(self):
        """ Check that a picking has a `carrier_tracking_ref`.

        This allows to block a picking to be validated as done if the `carrier_tracking_ref` is
        missing. This is necessary because some E-commerce platform requires a tracking reference based
        on the carrier.

        :raise: UserError if `carrier_id` or `carrier_tracking_ref` is missing
        """
        ecommerce_pickings_sudo = self.sudo().filtered(
            lambda p: p.sale_id
            and p.sale_id.ecommerce_account_id
            and p.picking_type_code == 'outgoing'
        )  # In sudo mode to read the field on sale.order
        for picking_sudo in ecommerce_pickings_sudo:
            support_shipping = picking_sudo.ec_account_id.ecommerce_channel_id.support_shipping
            if support_shipping and not picking_sudo.carrier_id.name:
                raise UserError(self.env._(
                    "%s requires that a tracking reference is provided with each picking. You "
                    "need to assign a carrier to this picking.",
                    picking_sudo.ec_account_id.ecommerce_channel_id.name,
                ))
            if support_shipping and not picking_sudo.carrier_tracking_ref:
                raise UserError(self.env._(
                    "%s requires that a tracking reference is provided with each picking. "
                    "Since the current carrier doesn't automatically provide a tracking reference, "
                    "you need to set one manually.",
                    picking_sudo.ec_account_id.ecommerce_channel_id.name,
                ))
        return super()._check_carrier_details_compliance()
