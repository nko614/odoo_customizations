from odoo import models, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_margin_percentage(self):
        """Calculate overall margin percentage for the order."""
        self.ensure_one()
        if not self.amount_untaxed:
            return 0.0
        return (self.margin / self.amount_untaxed) * 100

    def action_confirm(self):
        threshold = float(
            self.env["ir.config_parameter"].sudo().get_param("margin_alert.threshold", "0")
        )
        mode = self.env["ir.config_parameter"].sudo().get_param("margin_alert.mode", "warn")

        if threshold <= 0:
            return super().action_confirm()

        for order in self:
            margin_pct = order._get_margin_percentage()
            if margin_pct >= threshold:
                continue

            if mode == "block":
                raise UserError(
                    _('Order %s has a margin of %.1f%%, which is below the minimum of %.1f%%. '
                      'Confirmation is blocked. Adjust pricing before confirming.')
                    % (order.name, margin_pct, threshold)
                )

            if mode == "warn" and not self.env.context.get("margin_alert_confirmed"):
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Low Margin Warning"),
                    "res_model": "sale.order",
                    "res_id": order.id,
                    "view_mode": "form",
                    "target": "current",
                    "context": {**self.env.context, "margin_alert_confirmed": True},
                    "views": [(False, "form")],
                    "help": _("Margin is %.1f%%. Click Confirm again to proceed.") % margin_pct,
                }

        return super().action_confirm()
