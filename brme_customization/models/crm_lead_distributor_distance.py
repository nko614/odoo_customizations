from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)
_logger.warning(">>> LOADING CrmLeadDistributorDistance model")  # 👈 DEBUG LINE


class CrmLeadDistributorDistance(models.Model):
    _name = "crm.lead.distributor.distance"
    _description = "CRM Lead Distributor Distance"

    distributor_id = fields.Many2one('res.partner', string="Distributor")
    distance_km = fields.Float(string="Distance (km)")
    lead_id = fields.Many2one('crm.lead', string="Lead")
