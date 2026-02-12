import requests
import logging
from odoo import models

_logger = logging.getLogger(__name__)

class GoogleMapsHelper(models.AbstractModel):
    _name = 'google.maps.helper'
    _description = 'Google Maps Integration Helper'

    def _get_api_key(self):
        # Hardcoded API key for demo purposes
        return 'AIzaSyBo9jLDlMwV7kKSg_i7RMLAbYoKdbAa5hU'

    def _format_address(self, partner):
        """Format partner address for Google Maps API"""
        address_parts = []
        
        if partner.street:
            address_parts.append(partner.street)
        if partner.street2:
            address_parts.append(partner.street2)
        if partner.city:
            address_parts.append(partner.city)
        if partner.state_id and partner.state_id.name:
            address_parts.append(partner.state_id.name)
        if partner.zip:
            address_parts.append(partner.zip)
        if partner.country_id and partner.country_id.name:
            address_parts.append(partner.country_id.name)
            
        if not address_parts:
            return None
            
        return ", ".join(address_parts)

    def get_distance_matrix(self, origin, destinations):
        """Calculate distances between origin and multiple destinations"""
        api_key = self._get_api_key()
        if not api_key:
            _logger.error("Google Maps API key not configured.")
            return False

        # Format origin address
        origin_str = self._format_address(origin)
        if not origin_str:
            _logger.error("Origin partner %s has no valid address", origin.name)
            return False

        # Format destination addresses
        dest_addresses = []
        valid_destinations = []
        
        for dest in destinations:
            dest_str = self._format_address(dest)
            if dest_str:
                dest_addresses.append(dest_str)
                valid_destinations.append(dest)
            else:
                _logger.warning("Destination partner %s has no valid address, skipping", dest.name)

        if not dest_addresses:
            _logger.error("No valid destination addresses found")
            return False

        # Join destinations with pipe separator
        dest_str = "|".join(dest_addresses)

        base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        params = {
            'origins': origin_str,
            'destinations': dest_str,
            'key': api_key,
            'units': 'metric'  # Use metric units
        }

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('status') == 'OK':
                _logger.info("Successfully retrieved distance matrix for %d destinations", len(dest_addresses))
                return result
            else:
                error_msg = result.get('error_message', 'Unknown error')
                _logger.error("Google Maps API error: %s - %s", result.get('status'), error_msg)
                return False

        except requests.exceptions.Timeout:
            _logger.error("Google Maps API request timed out")
            return False
        except requests.exceptions.RequestException as e:
            _logger.error("Error calling Google Maps API: %s", str(e))
            return False
        except Exception as e:
            _logger.error("Unexpected error calling Google Maps API: %s", str(e))
            return False