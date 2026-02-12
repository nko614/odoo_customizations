import logging

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    fsm_mileage = fields.Float(string="Mileage (miles)")
    fsm_mileage_cost = fields.Float(
        string="Mileage Cost",
        compute='_compute_fsm_mileage_cost',
    )

    @api.depends('fsm_mileage')
    def _compute_fsm_mileage_cost(self):
        unit_cost = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'nada_test.fsm_mileage_unit_cost', '0.67'
            )
        )
        for task in self:
            task.fsm_mileage_cost = task.fsm_mileage * unit_cost

    def action_fsm_validate(self, stop_running_timers=False):
        _logger.info("NADA_TEST: action_fsm_validate called for tasks %s", self.ids)
        result = super().action_fsm_validate(stop_running_timers=stop_running_timers)
        _logger.info("NADA_TEST: super returned %s (type: %s)", result, type(result))
        # If super returned a wizard action (stop timers dialog), don't post yet
        if isinstance(result, dict) and result.get('type') == 'ir.actions.act_window':
            _logger.info("NADA_TEST: wizard action returned, skipping mileage post")
            return result
        self._post_mileage_analytic_lines()
        return result

    def _post_mileage_analytic_lines(self):
        unit_cost = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'nada_test.fsm_mileage_unit_cost', '0.67'
            )
        )
        _logger.info("NADA_TEST: _post_mileage_analytic_lines called, unit_cost=%s, tasks=%s", unit_cost, self.ids)
        for task in self:
            _logger.info(
                "NADA_TEST: task %s - mileage=%s, project=%s, account_id=%s",
                task.id, task.fsm_mileage, task.project_id.id, task.project_id.account_id.id if task.project_id.account_id else None,
            )
            if not task.fsm_mileage:
                _logger.info("NADA_TEST: skipping task %s - no mileage", task.id)
                continue
            if not task.project_id.account_id:
                _logger.info("NADA_TEST: skipping task %s - no analytic account on project", task.id)
                continue
            amount = -(task.fsm_mileage * unit_cost)
            try:
                line = self.env['account.analytic.line'].sudo().create({
                    'name': _("Mileage: %(miles)s miles @ $%(rate)s/mi", miles=task.fsm_mileage, rate=unit_cost),
                    'account_id': task.project_id.account_id.id,
                    'unit_amount': task.fsm_mileage,
                    'amount': amount,
                    'date': fields.Date.context_today(task),
                    'partner_id': task.partner_id.id if task.partner_id else False,
                    'company_id': task.company_id.id or task.project_id.company_id.id,
                    'category': 'other',
                })
                _logger.info("NADA_TEST: created analytic line %s for task %s", line.id, task.id)
            except Exception as e:
                _logger.error("NADA_TEST: FAILED to create analytic line for task %s: %s", task.id, e)
