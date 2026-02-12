from odoo import fields, models


class LinkedinImportLog(models.Model):
    _name = 'linkedin.import.log'
    _description = 'LinkedIn Import Log'
    _order = 'date_import desc'

    name = fields.Char(
        string='Import',
        compute='_compute_name',
        store=True,
    )
    date_import = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    records_received = fields.Integer(string='Received', readonly=True)
    records_created = fields.Integer(string='Created', readonly=True)
    records_updated = fields.Integer(string='Duplicates Skipped', readonly=True)
    records_failed = fields.Integer(string='Failed', readonly=True)
    state = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
    ], string='Status', readonly=True)
    error_details = fields.Text(string='Error Details', readonly=True)
    raw_payload = fields.Text(string='Raw Payload', readonly=True)

    def _compute_name(self):
        for log in self:
            dt = log.date_import or fields.Datetime.now()
            log.name = f"LinkedIn Import {dt.strftime('%Y-%m-%d %H:%M:%S')}"
