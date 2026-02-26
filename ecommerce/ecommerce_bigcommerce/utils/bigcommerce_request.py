# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

import requests

TIMEOUT = 30
LIMIT = 40

_logger = logging.getLogger(__name__)


class BigcommerceRequest:

    def request(self, ecommerce_account, version, endpoint, method, params={}, payload={}):
        store_hash = ecommerce_account.bigcommerce_store_hash
        access_token = ecommerce_account.bigcommerce_access_token
        if not (store_hash and access_token):
            _logger.error("Required credentials are not set yet.")
            return {
                "errors": "Required credentials are not set yet.",
            }
        request_url = f"https://api.bigcommerce.com/stores/{store_hash}/{version}/{endpoint}"
        headers = {
            'X-Auth-Token': access_token,
            'Accept': 'application/json',
        }
        params = dict(params)  # copy to avoid modifying caller dict
        params.setdefault("limit", LIMIT)
        params.setdefault('page', 1)

        if version == 'v2' and endpoint.startswith('orders') and method.upper() == 'GET':
            parts = endpoint.strip('/').split('/')
            if len(parts) == 1:
                # /orders → list of orders
                return self._fetch_all_orders(request_url, headers, params, method, payload)

            if len(parts) == 2:
                # /orders/{id} → single order
                return self._fetch_single_object(request_url, headers, params, method, payload)

            # e.g. /orders/{id}/shipments → list of shipments (no pagination metadata in v2)
            return self._fetch_all_orders(request_url, headers, params, method, payload)

        return self._fetch_with_meta(request_url, headers, params, method, payload)

    def oauth_request(self, method, params={}, payload={}, headers={}):
        """Handles OAuth specific requests."""
        request_url = "https://login.bigcommerce.com/oauth2/token"
        response = self.make_api_call(
            method=method,
            url=request_url,
            params=params,
            headers=headers,
            payload=payload,
            timeout=TIMEOUT,
        )

        if not response:
            return {'errors': "Unexpected error. Please report this to your administrator."}

        try:
            data = response.json()
        except ValueError as e:
            _logger.error("Failed to decode JSON from OAuth API response. Error: %s", e)
            return {'errors': "Failed to decode JSON from OAuth API response."}

        if 'errors' in data:
            return {'errors': data.get('errors')}

        return data

    def _fetch_with_meta(self, url, headers, params, method, payload):
        """Handles APIs that return meta or response in object"""
        combined_data = []
        meta_info = None

        while True:
            response = self.make_api_call(
                method=method,
                url=url,
                params=params,
                headers=headers,
                payload=payload,
                timeout=TIMEOUT,
            )

            if not response:
                return {'errors': "Unexpected error. Please report this to your administrator."}

            try:
                data = response.json()
            except ValueError as e:
                _logger.error("Failed to decode JSON from API response. Error: %s", e)
                return {'errors': "Failed to decode JSON from API response."}

            if 'errors' in data:
                return {'errors': data.get('errors')}

            if isinstance(data, dict) and 'data' in data:
                combined_data.extend(data.get('data', []))

                meta_info = data.get('meta', {}).get('pagination', {})
                current_page = meta_info.get('current_page', 1)
                total_pages = meta_info.get('total_pages', 1)

                if current_page >= total_pages:
                    break
                params['page'] = current_page + 1

            elif isinstance(data, dict):
                return data

            else:
                return {'errors': "Unexpected data format received from API."}

        return {'data': combined_data, 'meta': meta_info}

    def _fetch_all_orders(self, url, headers, params, method, payload):
        """Handles v2 orders API pagination (no meta, returns plain list)."""
        all_orders = []

        while True:
            response = self.make_api_call(
                method=method,
                url=url,
                params=params,
                headers=headers,
                payload=payload,
                timeout=TIMEOUT,
            )

            if not response:
                return {'errors': "Unexpected error. Please report this to your administrator."}

            try:
                data = response.json()
            except ValueError:
                # If decoding fails, it could mean no content (204) or bad response
                if response.status_code == 204 or not response.text.strip():
                    break  # no more orders, stop gracefully
                return {'errors': "Failed to decode JSON from Orders API response."}

            if not isinstance(data, list):
                return {'errors': "Unexpected response format for orders API."}

            if not data:
                break  # no more orders

            all_orders.extend(data)

            if len(data) < params.get('limit', LIMIT):
                break  # last page (didn't hit full limit)

            params['page'] += 1

        return all_orders

    def make_api_call(self, method, url, params, headers, timeout, payload={}):
        response = None
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                timeout=timeout,
                json=payload if payload else None,
            )
            response.raise_for_status()
            return response
        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.MissingSchema,
                requests.exceptions.Timeout, requests.exceptions.HTTPError, requests.exceptions.RequestException, requests.exceptions.InvalidURL) as ex:
            _logger.error("API request failed: %s", ex)
            return response

    def _fetch_single_object(self, url, headers, params, method, payload):
        """Handles single order fetch (returns an object, not a list)."""
        response = self.make_api_call(
            method=method,
            url=url,
            params=params,
            headers=headers,
            payload=payload,
            timeout=TIMEOUT,
        )

        if not response:
            return {'errors': "Unexpected error. Please report this to your administrator."}

        try:
            data = response.json()
        except ValueError as e:
            _logger.error("Failed to decode JSON for single order. Error: %s", e)
            return {'errors': "Failed to decode JSON from API response."}

        if "errors" in data:
            return {'errors': data.get("errors")}

        if not isinstance(data, dict):
            return {'errors': "Unexpected response format for single order API."}

        return data
