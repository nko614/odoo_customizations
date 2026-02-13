# import requests
# import logging
# from odoo import models, _

# _logger = logging.getLogger(__name__)


# class DeliveryOptimizerMapsHelper(models.AbstractModel):
#     _name = "delivery.optimizer.maps.helper"
#     _description = "Delivery Route Optimizer Google Maps Proxy Helper"

#     def get_distance_matrix(self, origin, destinations):
#         """Proxy call to Server for Google Maps Distance Matrix."""
#         url = "https://vikuno.com/api/google/distance-matrix"
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "application/json",
#             "User-Agent": "Odoo-Delivery-Optimizer/1.0",
#         }

#         # Format addresses
#         def fmt(addr):
#             return f"{addr.street}, {addr.city}, {addr.state_id.name or ''}, {addr.zip}, {addr.country_id.name or ''}"

#         data = {"origin": fmt(origin), "destinations": [fmt(d) for d in destinations]}
#         try:
#             response = requests.post(url, json=data, headers=headers, timeout=15)
#             response.raise_for_status()
#             result = response.json()
#             if result.get("status") == "OK":
#                 return result
#             else:
#                 _logger.error("Google Maps API error: %s", result.get("status"))
#                 return False
#         except Exception as e:
#             _logger.info(
#                 "Error calling Google Maps API. A Subscription is required.  Post install, go to https://vikuno.com/ to subscribe: %s",
#                 str(e),
#             )
#             return False
