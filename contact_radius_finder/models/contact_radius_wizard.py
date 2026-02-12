import requests
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ContactRadiusWizard(models.TransientModel):
    _name = 'contact.radius.wizard'
    _description = 'Find Contacts Within Radius'

    source_location_id = fields.Many2one(
        'res.partner',
        string='Source Location',
        help='Select the contact to use as the source location'
    )
    radius_miles = fields.Float(
        string='Radius (miles)',
        required=True,
        default=10.0,
        help='Distance in miles to search for contacts'
    )

    def _get_api_key(self):
        """Get Google Maps API key"""
        return 'REDACTED_API_KEY'

    def _get_contact_address(self, contact):
        """Format contact address for Google Maps API"""
        address_parts = []
        if contact.street:
            address_parts.append(contact.street)
        if contact.street2:
            address_parts.append(contact.street2)
        if contact.city:
            address_parts.append(contact.city)
        if contact.state_id:
            address_parts.append(contact.state_id.name)
        if contact.zip:
            address_parts.append(contact.zip)
        if contact.country_id:
            address_parts.append(contact.country_id.name)

        return ", ".join(address_parts) if address_parts else False

    def _calculate_distances_batch(self, origin, destinations_map):
        """Calculate distances in batch using Google Maps Distance Matrix API

        Args:
            origin: Source address string
            destinations_map: Dict mapping contact IDs to their addresses

        Returns:
            Dict mapping contact IDs to their distances in miles
        """
        api_key = self._get_api_key()
        if not api_key:
            raise UserError("Google Maps API key not configured")

        base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

        # Prepare destinations list
        contact_ids = list(destinations_map.keys())
        destinations_list = [destinations_map[cid] for cid in contact_ids]
        destinations_str = "|".join(destinations_list)

        params = {
            'origins': origin,
            'destinations': destinations_str,
            'units': 'imperial',  # Use miles
            'key': api_key
        }

        try:
            _logger.info(f"Batch API call for {len(contact_ids)} destinations")
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            distances = {}

            if result.get('status') == 'OK':
                rows = result.get('rows', [])
                if rows and rows[0].get('elements'):
                    elements = rows[0]['elements']
                    for i, element in enumerate(elements):
                        if i < len(contact_ids):
                            contact_id = contact_ids[i]
                            if element.get('status') == 'OK':
                                distance_meters = element['distance']['value']
                                distance_miles = distance_meters * 0.000621371
                                distances[contact_id] = distance_miles
                            else:
                                _logger.warning(f"Could not calculate distance for contact {contact_id}: {element.get('status')}")
            else:
                _logger.error(f"Batch API error: {result.get('status')} - {result.get('error_message', 'No error message')}")

            return distances

        except Exception as e:
            _logger.error("Error in batch distance calculation: %s", str(e))
            return {}

    def action_find_contacts(self):
        """Find all contacts within the specified radius"""
        self.ensure_one()

        _logger.warning("="*50)
        _logger.warning("ACTION FIND CONTACTS CALLED")
        _logger.warning(f"Source location ID: {self.source_location_id}")
        _logger.warning(f"Radius: {self.radius_miles}")
        _logger.warning("="*50)

        if not self.source_location_id:
            _logger.error("No source location selected!")
            raise UserError("Please select a source location")

        if self.radius_miles <= 0:
            _logger.error("Invalid radius!")
            raise UserError("Radius must be greater than 0")

        # Get the source location address
        source_address = self._get_contact_address(self.source_location_id)
        if not source_address:
            raise UserError("The selected source location does not have a complete address")

        _logger.info(f"Source address: {source_address}")

        # Get all contacts with addresses (excluding the source location itself)
        all_contacts = self.env['res.partner'].search([
            ('street', '!=', False),
            ('id', '!=', self.source_location_id.id),
        ])

        _logger.info(f"Total contacts to check: {len(all_contacts)}")

        # Build a map of contact IDs to addresses
        contact_address_map = {}
        for contact in all_contacts:
            contact_address = self._get_contact_address(contact)
            if contact_address:
                contact_address_map[contact.id] = contact_address
            else:
                _logger.warning(f"Skipping contact {contact.name} - no address")

        # Process in batches of 25 (Google Maps API limit)
        BATCH_SIZE = 25
        contacts_within_radius = []
        contact_ids = list(contact_address_map.keys())

        for i in range(0, len(contact_ids), BATCH_SIZE):
            batch_ids = contact_ids[i:i+BATCH_SIZE]
            batch_map = {cid: contact_address_map[cid] for cid in batch_ids}

            _logger.info(f"Processing batch {i//BATCH_SIZE + 1}: {len(batch_map)} contacts")

            # Get distances for this batch
            distances = self._calculate_distances_batch(source_address, batch_map)

            # Filter by radius
            for contact_id, distance in distances.items():
                if distance <= self.radius_miles:
                    contacts_within_radius.append(contact_id)
                    contact_name = self.env['res.partner'].browse(contact_id).name
                    _logger.info(f"Contact {contact_name} is {distance:.2f} miles away - INCLUDED")

        _logger.info(f"Found {len(contacts_within_radius)} contacts within radius")

        if not contacts_within_radius:
            raise UserError(f"No contacts found within {self.radius_miles} miles of {self.source_location_id.name}. Check server logs for details.")

        # Sort by stored total_invoiced_amount field
        _logger.info("Reading invoice totals from stored field for sorting...")
        contact_invoice_totals = []
        for contact_id in contacts_within_radius:
            partner = self.env['res.partner'].browse(contact_id)
            contact_invoice_totals.append((contact_id, partner.total_invoiced_amount))
            _logger.info(f"Contact {partner.name}: ${partner.total_invoiced_amount:,.2f}")

        # Sort by invoice total (descending)
        contact_invoice_totals.sort(key=lambda x: x[1], reverse=True)
        sorted_contact_ids = [x[0] for x in contact_invoice_totals]

        _logger.info(f"Contacts sorted by invoice total (highest first)")
        title_suffix = "highest invoice totals first"

        # Log the final sorted list
        _logger.warning("="*50)
        _logger.warning("FINAL SORTED LIST:")
        for i, (contact_id, total) in enumerate(contact_invoice_totals, 1):
            partner_name = self.env['res.partner'].browse(contact_id).name
            _logger.warning(f"{i}. {partner_name} - ${total:,.2f}")
        _logger.warning("="*50)

        # Return directly to filtered list view of contacts with custom view
        tree_view_id = self.env.ref('contact_radius_finder.view_partner_tree_invoice_total').id

        return {
            'type': 'ir.actions.act_window',
            'name': f'Contacts within {self.radius_miles} miles ({len(sorted_contact_ids)} found - sorted {title_suffix})',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'views': [(tree_view_id, 'list'), (False, 'form')],
            'domain': [('id', 'in', sorted_contact_ids)],
            'target': 'current',
        }

