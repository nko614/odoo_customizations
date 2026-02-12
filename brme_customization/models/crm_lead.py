from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    distributor_distance_ids = fields.One2many(
        'crm.lead.distributor.distance',
        'lead_id',
        string='Closest Distributors',
        help='The 3 closest distributors based on partner address'
    )
    
    distributor_count = fields.Integer(
        string='Distributor Count',
        compute='_compute_distributor_count',
        store=True
    )

    @api.depends('distributor_distance_ids')
    def _compute_distributor_count(self):
        for record in self:
            record.distributor_count = len(record.distributor_distance_ids)

    def action_find_closest_distributors(self):
        """Server action to find and populate closest distributors with distances"""
        for lead in self:
            try:
                # Validation checks
                self._validate_lead_for_distance_calculation(lead)
                
                # Find distributors
                distributors = self._get_valid_distributors(lead)
                
                # Calculate distances
                distance_data = self._calculate_distributor_distances(lead, distributors)
                
                # Update lead with results
                self._update_lead_distributors(lead, distance_data)
                
                # Log and notify
                self._log_and_notify_results(lead, distance_data)
                
            except UserError:
                raise
            except Exception as e:
                _logger.error("Error finding closest distributors for lead %s: %s", lead.name, str(e))
                raise UserError(f"An error occurred while finding closest distributors: {str(e)}")

    def _validate_lead_for_distance_calculation(self, lead):
        """Validate that the lead has the necessary information for distance calculation"""
        if not lead.partner_id:
            raise UserError(f"Lead '{lead.name}' has no partner assigned. Please assign a partner first.")
        
        if not lead.partner_id.street:
            raise UserError(f"Partner '{lead.partner_id.name}' has no address. Please add an address to the partner.")

    def _get_valid_distributors(self, lead):
        """Get all valid distributors with addresses"""
        distributors = self.env['res.partner'].search([
            ('category_id.name', 'ilike', 'Distributor'),
            ('street', '!=', False),
            ('city', '!=', False),
            ('id', '!=', lead.partner_id.id)
        ])
        
        if not distributors:
            raise UserError("No distributors found with valid addresses. Please ensure distributors have the 'Distributor' category and complete addresses.")
        
        return distributors

    def _calculate_distributor_distances(self, lead, distributors):
        """Calculate distances using Google Maps API"""
        maps_helper = self.env['google.maps.helper']
        distance_result = maps_helper.get_distance_matrix(lead.partner_id, distributors)
        
        if not distance_result:
            raise UserError("Failed to get distance matrix. Please check your Google Maps API key configuration.")
        
        return self._process_distance_results(distance_result, distributors)

    def _process_distance_results(self, distance_result, distributors):
        """Process Google Maps API results and return sorted distance data"""
        if not distance_result or 'rows' not in distance_result:
            return []
        
        elements = distance_result['rows'][0].get('elements', [])
        distance_data = []
        
        for i, element in enumerate(elements):
            if i >= len(distributors):
                break
                
            if element.get('status') == 'OK' and 'distance' in element:
                distance_value = element['distance']['value']
                distance_km = round(distance_value / 1000.0, 2)
                distance_data.append({
                    'distributor': distributors[i],
                    'distance_km': distance_km
                })
            elif element.get('status') != 'OK':
                _logger.warning("Distance calculation failed for distributor %s: %s", 
                              distributors[i].name, element.get('status'))
        
        # Sort by distance and return top 3
        distance_data.sort(key=lambda x: x['distance_km'])
        return distance_data[:3]

    def _update_lead_distributors(self, lead, distance_data):
        """Update lead with new distributor distance records"""
        # Remove existing records
        lead.distributor_distance_ids.unlink()
        
        # Create new records
        for data in distance_data:
            self.env['crm.lead.distributor.distance'].create({
                'lead_id': lead.id,
                'distributor_id': data['distributor'].id,
                'distance_km': data['distance_km'],
            })

    def _log_and_notify_results(self, lead, distance_data):
        """Log results and post message to lead"""
        if distance_data:
            distributor_names = [data['distributor'].name for data in distance_data]
            lead.message_post(
                body=f"Found {len(distance_data)} closest distributors: {', '.join(distributor_names)}"
            )
            _logger.info("Updated lead %s with %d closest distributors", lead.name, len(distance_data))
        else:
            lead.message_post(body="No valid distributors found within reachable distance.")
            _logger.warning("No distributors found for lead %s", lead.name)

    @api.model
    def validate_distributor_addresses(self):
        """Utility method to check which distributors have valid addresses"""
        distributors = self.env['res.partner'].search([
            ('category_id.name', 'ilike', 'Distributor')
        ])
        
        valid_distributors = []
        invalid_distributors = []
        
        for distributor in distributors:
            if distributor.street and distributor.city:
                valid_distributors.append(distributor)
            else:
                invalid_distributors.append(distributor)
                _logger.info("Distributor %s missing address info", distributor.name)
        
        _logger.info("Found %d distributors with valid addresses out of %d total", 
                    len(valid_distributors), len(distributors))
        
        if invalid_distributors:
            invalid_names = [d.name for d in invalid_distributors]
            _logger.warning("Distributors missing addresses: %s", ", ".join(invalid_names))
        
        return {
            'valid_count': len(valid_distributors),
            'total_count': len(distributors),
            'invalid_distributors': invalid_distributors,
            'valid_distributors': valid_distributors
        }