import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from itertools import permutations

_logger = logging.getLogger(__name__)

# Your Google API Key
GOOGLE_API_KEY = "REDACTED_API_KEY"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    optimized_sequence = fields.Char(
        string="Stop #",
        help="Stop number after route optimization",
        copy=False,
    )

    distance_from_warehouse = fields.Float(
        string="Leg Distance (mi)",
        help="Distance from previous stop (or warehouse if first stop / not optimized)",
        copy=False,
        readonly=True,
        digits=(16, 2),
    )

    driving_time_minutes = fields.Integer(
        string="Driving Time (min)",
        help="Estimated driving time from warehouse",
        copy=False,
        readonly=True,
    )

    # Dummy field for the route preview button widget
    route_preview = fields.Boolean(
        string="Route",
        compute="_compute_route_preview",
        store=False,
    )

    @api.depends('partner_id')
    def _compute_route_preview(self):
        """Compute field to enable route preview button"""
        for picking in self:
            picking.route_preview = bool(picking.partner_id)

    total_route_distance = fields.Float(
        string="Total Distance (mi)",
        help="Total distance of the optimized route including return to warehouse",
        copy=False,
        readonly=True,
        digits=(16, 2),
    )

    def _get_google_api_key(self):
        """Get Google API key - can be overridden via system parameter"""
        param_key = self.env["ir.config_parameter"].sudo().get_param("google_maps_api_key")
        return param_key or GOOGLE_API_KEY

    def _format_address(self, partner):
        """Format address for Google Maps API."""
        parts = [
            partner.street or "",
            partner.city or "",
            partner.state_id.name if partner.state_id else "",
            partner.zip or "",
            partner.country_id.name if partner.country_id else "",
        ]
        return ", ".join(p for p in parts if p)

    def _validate_address(self, partner):
        """Validate if a partner has a complete address"""
        if not partner:
            return False
        required_fields = ["street", "city", "zip"]
        return all(partner[field] for field in required_fields)

    def _meters_to_miles(self, meters):
        """Convert meters to miles"""
        return meters * 0.000621371

    def _get_distance_matrix(self, origins, destinations):
        """Get distance matrix from Google Distance Matrix API"""
        api_key = self._get_google_api_key()

        origin_addresses = "|".join(self._format_address(p) for p in origins)
        destination_addresses = "|".join(self._format_address(p) for p in destinations)

        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origin_addresses,
            "destinations": destination_addresses,
            "key": api_key,
            "units": "imperial",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("status") != "OK":
                error_msg = result.get("error_message", result.get("status", "Unknown error"))
                _logger.error(f"Google Distance Matrix API error: {error_msg}")
                raise UserError(_("Google Maps API error: %s") % error_msg)

            return result
        except requests.RequestException as e:
            _logger.error(f"Google Maps API request failed: {str(e)}")
            raise UserError(_("Failed to connect to Google Maps API. Please try again."))

    def _call_route_optimization_api(self, addresses):
        """
        Call Google Route Optimization API to get optimized route.
        Falls back to Distance Matrix + local optimization if Route Optimization fails.
        """
        api_key = self._get_google_api_key()

        # Build shipments for Route Optimization API
        shipments = []
        for i, addr in enumerate(addresses[1:], 1):  # Skip warehouse (index 0)
            shipments.append({
                "deliveries": [{
                    "arrivalLocation": {
                        "latitude": 0,  # Will use address string
                        "longitude": 0,
                    },
                    "duration": "300s",  # 5 min per stop
                }],
                "label": f"delivery_{i}",
            })

        # Try Route Optimization API first
        try:
            url = "https://routeoptimization.googleapis.com/v1/projects/YOUR_PROJECT:optimizeTours"
            # Note: Route Optimization API requires project setup
            # Falling back to Distance Matrix approach which works with standard API key
            raise Exception("Using Distance Matrix fallback")
        except Exception:
            # Use Distance Matrix API with local optimization
            return self._optimize_with_distance_matrix(addresses)

    def _optimize_with_distance_matrix(self, addresses):
        """Optimize route using Distance Matrix API and local algorithms"""
        # Build complete distance matrix
        distance_matrix = {"rows": []}

        for origin in addresses:
            result = self._get_distance_matrix([origin], addresses)
            if not result.get("rows") or not result["rows"][0].get("elements"):
                raise UserError(_("Invalid response from Google Maps API."))
            distance_matrix["rows"].append(result["rows"][0])

        # Find optimal route
        delivery_count = len(addresses) - 1  # Exclude warehouse
        if delivery_count <= 8:
            route = self._brute_force_route(delivery_count, distance_matrix)
        else:
            route = self._nearest_neighbor_route(delivery_count, distance_matrix)

        return route, distance_matrix

    def _brute_force_route(self, count, matrix):
        """Find optimal route by testing all permutations (for small sets)"""
        best_route = None
        min_distance = float("inf")

        for route in permutations(range(1, count + 1)):
            try:
                distance = self._calculate_route_distance(route, matrix)
                if distance < min_distance:
                    min_distance = distance
                    best_route = route
            except Exception:
                continue

        return best_route

    def _nearest_neighbor_route(self, count, matrix):
        """Find route using nearest neighbor heuristic (for larger sets)"""
        route = []
        unvisited = list(range(1, count + 1))
        current = 0  # Start at warehouse

        while unvisited:
            try:
                next_point = min(
                    unvisited,
                    key=lambda x: matrix["rows"][current]["elements"][x]["distance"]["value"],
                )
                route.append(next_point)
                current = next_point
                unvisited.remove(next_point)
            except (KeyError, IndexError) as e:
                _logger.error(f"Error in nearest neighbor: {str(e)}")
                raise UserError(_("Error calculating optimal route."))

        return tuple(route)

    def _calculate_route_distance(self, route, matrix):
        """Calculate total distance for a route including return to warehouse"""
        total = 0
        current = 0  # Start at warehouse

        for point in route:
            element = matrix["rows"][current]["elements"][point]
            if element.get("status") != "OK":
                raise UserError(_("Could not calculate distance between locations."))
            total += element["distance"]["value"]
            current = point

        # Return to warehouse
        return_element = matrix["rows"][current]["elements"][0]
        if return_element.get("status") != "OK":
            raise UserError(_("Could not calculate return distance to warehouse."))
        total += return_element["distance"]["value"]

        return self._meters_to_miles(total)

    def _get_address_key(self, partner):
        """Return a normalized unique key for a delivery address."""
        return (
            (partner.street or "").strip().lower(),
            (partner.street2 or "").strip().lower(),
            (partner.city or "").strip().lower(),
            (partner.state_id.name if partner.state_id else "").strip().lower(),
            (partner.zip or "").strip(),
            (partner.country_id.code if partner.country_id else "").strip().upper(),
        )

    def _get_validated_warehouse(self):
        """Get and validate warehouse address"""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        if not warehouse or not warehouse.partner_id:
            raise UserError(_("Please configure warehouse address first."))
        if not self._validate_address(warehouse.partner_id):
            raise UserError(_("Warehouse address is incomplete. Please add street, city, and ZIP."))
        return warehouse

    def _filter_valid_deliveries(self, deliveries):
        """Filter deliveries with valid addresses"""
        return [
            d for d in deliveries
            if d.partner_id and self._validate_address(d.partner_id)
        ]

    def _assign_stop_numbers(self, route, deliveries, addresses, matrix, total_dist):
        """Assign optimized stop numbers to deliveries"""
        from collections import defaultdict

        # Group deliveries by address
        addr_map = defaultdict(list)
        for d in deliveries:
            key = self._get_address_key(d.partner_id)
            addr_map[key].append(d)

        used_keys = set()
        stop = 1
        prev_idx = 0  # Start from warehouse (index 0)

        for idx in route:
            if idx < 1 or idx >= len(addresses):
                continue

            partner = addresses[idx]
            key = self._get_address_key(partner)

            if key in used_keys:
                continue
            used_keys.add(key)

            deliveries_at_address = addr_map.get(key, [])

            # Calculate distance and driving time from previous stop
            dist = 0
            drive_mins = 0
            if matrix and "rows" in matrix and len(matrix["rows"]) > 0:
                try:
                    element = matrix["rows"][prev_idx]["elements"][idx]
                    dist = self._meters_to_miles(element["distance"]["value"])
                    drive_mins = round(element["duration"]["value"] / 60)
                except Exception:
                    dist = 0
                    drive_mins = 0

            for i, d in enumerate(deliveries_at_address, 1):
                seq = str(stop) if len(deliveries_at_address) == 1 else f"{stop}.{i}"
                d.write({
                    "optimized_sequence": seq,
                    "distance_from_warehouse": dist,
                    "driving_time_minutes": drive_mins,
                    "total_route_distance": total_dist if total_dist else 0,
                })

            prev_idx = idx
            stop += 1

    def action_optimize_route(self):
        """Manual trigger for route optimization on selected deliveries"""
        # Use selected records — filter to outgoing, assigned, with valid addresses
        selected_deliveries = self._filter_valid_deliveries(
            [p for p in self if p.picking_type_id.code == "outgoing" and p.state == "assigned"]
        )

        _logger.info(f"Optimizing {len(selected_deliveries)} selected deliveries")

        if not selected_deliveries:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Eligible Deliveries"),
                    "message": _("No selected outgoing deliveries in 'Ready' state with valid addresses."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        warehouse = self._get_validated_warehouse()
        addresses = [warehouse.partner_id] + [d.partner_id for d in selected_deliveries]

        # Get optimized route
        route, distance_matrix = self._optimize_with_distance_matrix(addresses)

        if not route:
            raise UserError(_("Could not calculate optimal route."))

        # Calculate total route distance
        unique_route = []
        seen_keys = set()
        for idx in route:
            if idx < 1 or idx >= len(addresses):
                continue
            key = self._get_address_key(addresses[idx])
            if key not in seen_keys:
                unique_route.append(idx)
                seen_keys.add(key)

        path = [0] + list(unique_route) + [0]
        total_distance = 0
        for i in range(len(path) - 1):
            from_idx = path[i]
            to_idx = path[i + 1]
            total_distance += distance_matrix["rows"][from_idx]["elements"][to_idx]["distance"]["value"]
        total_distance = self._meters_to_miles(total_distance)

        # Assign stop numbers
        self._assign_stop_numbers(route, selected_deliveries, addresses, distance_matrix, total_distance)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Route Optimized"),
                "message": _("Optimized %d deliveries. Total distance: %.1f miles.") % (len(selected_deliveries), total_distance),
                "type": "success",
                "sticky": False,
            },
        }

    def _get_previous_stop_partner(self):
        """Find the previous stop's partner in the optimized route.
        Returns None if this is stop 1 or not optimized (use warehouse)."""
        self.ensure_one()
        if not self.optimized_sequence:
            return None
        # Parse main stop number (e.g. "2" from "2" or "2.1")
        try:
            main_stop = int(self.optimized_sequence.split('.')[0])
        except (ValueError, AttributeError):
            return None
        if main_stop <= 1:
            return None
        prev_stop = str(main_stop - 1)
        # Find a delivery at the previous stop
        prev_picking = self.search([
            ('optimized_sequence', '=like', prev_stop + '%'),
            ('optimized_sequence', '!=', False),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if prev_picking and prev_picking.partner_id and self._validate_address(prev_picking.partner_id):
            return prev_picking.partner_id
        return None

    def get_single_delivery_route_info(self):
        """Get route info for a single delivery - used by the map popover widget"""
        self.ensure_one()

        if not self.partner_id or not self._validate_address(self.partner_id):
            return {
                'success': False,
                'error': 'Delivery address is incomplete',
            }

        try:
            warehouse = self._get_validated_warehouse()
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

        # Use previous stop as origin if optimized, otherwise warehouse
        prev_partner = self._get_previous_stop_partner()
        origin_partner = prev_partner or warehouse.partner_id
        origin_addr = self._format_address(origin_partner)
        origin_label = prev_partner.name if prev_partner else 'Warehouse'
        delivery_addr = self._format_address(self.partner_id)

        # Get distance and duration from Google
        try:
            result = self._get_distance_matrix([origin_partner], [self.partner_id])
            element = result.get('rows', [{}])[0].get('elements', [{}])[0]

            if element.get('status') != 'OK':
                return {
                    'success': False,
                    'error': 'Could not calculate route',
                }

            distance_meters = element['distance']['value']
            distance_miles = self._meters_to_miles(distance_meters)
            duration_seconds = element['duration']['value']
            duration_minutes = round(duration_seconds / 60)

            # Build Google Maps embed URL (Directions mode)
            api_key = self._get_google_api_key()
            embed_url = (
                f"https://www.google.com/maps/embed/v1/directions"
                f"?key={api_key}"
                f"&origin={origin_addr.replace(' ', '+')}"
                f"&destination={delivery_addr.replace(' ', '+')}"
                f"&mode=driving"
            )

            # Also provide direct link to Google Maps for navigation
            maps_url = (
                f"https://www.google.com/maps/dir/"
                f"{origin_addr.replace(' ', '+')}/{delivery_addr.replace(' ', '+')}"
            )

            return {
                'success': True,
                'picking_id': self.id,
                'picking_name': self.name,
                'partner_name': self.partner_id.name,
                'delivery_address': delivery_addr,
                'warehouse_address': origin_addr,
                'origin_label': origin_label,
                'distance_miles': round(distance_miles, 1),
                'distance_text': element['distance']['text'],
                'duration_minutes': duration_minutes,
                'duration_text': element['duration']['text'],
                'embed_url': embed_url,
                'maps_url': maps_url,
            }

        except Exception as e:
            _logger.error(f"Error getting route info: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }

    def action_view_route_popup(self):
        """Action to open route popup wizard for this delivery"""
        self.ensure_one()
        route_info = self.get_single_delivery_route_info()

        if not route_info.get('success'):
            raise UserError(route_info.get('error', 'Unknown error'))

        return {
            'type': 'ir.actions.act_window',
            'name': f'Route to {self.partner_id.name}',
            'res_model': 'delivery.route.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
                'route_info': route_info,
            },
        }

    def action_open_google_maps_route(self):
        """Open Google Maps with optimized route for selected deliveries"""
        valid_deliveries = self._filter_valid_deliveries(
            [p for p in self if p.picking_type_id.code == "outgoing" and p.state == "assigned"]
        )

        if not valid_deliveries:
            raise UserError(_("No selected outgoing deliveries in 'Ready' state with valid addresses."))

        warehouse = self._get_validated_warehouse()

        addresses = [warehouse.partner_id] + [d.partner_id for d in valid_deliveries]

        # Get optimized route
        route, _ = self._optimize_with_distance_matrix(addresses)

        # Build ordered address list
        ordered_addresses = [warehouse.partner_id]
        seen = set()
        for idx in route:
            if idx < 1 or idx >= len(addresses):
                continue
            partner = addresses[idx]
            key = self._get_address_key(partner)
            if key not in seen:
                seen.add(key)
                ordered_addresses.append(partner)

        # Add warehouse at end for return trip
        ordered_addresses.append(warehouse.partner_id)

        # Build Google Maps URL
        formatted_addresses = [self._format_address(a) for a in ordered_addresses]
        base_url = "https://www.google.com/maps/dir/"
        route_url = base_url + "/".join(addr.replace(" ", "+") for addr in formatted_addresses)

        return {
            "type": "ir.actions.act_url",
            "url": route_url,
            "target": "new",
        }
