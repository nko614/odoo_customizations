# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import contextlib
import hashlib
import hmac
import json
import logging
import requests
import time
import urllib.parse
import uuid

from odoo.tools.urls import urljoin as url_join
from odoo.addons.odoo_ecommerce.utils import ECommerceApiError

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


def get_admin_access_token(base_url, username, password):
    """Obtain an admin access token using admin login credentials."""
    url = url_join(base_url, "rest/V1/integration/admin/token")
    payload = {
        "username": username,
        "password": password,
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text.strip('"')
    except requests.exceptions.HTTPError as e:
        message = e.response.text
        with contextlib.suppress(json.JSONDecodeError):
            message = e.response.json().get("message") or message
        _logger.exception("HTTP error occurred: %s", message)
        raise ECommerceApiError(message) from e
    except requests.exceptions.RequestException as e:
        _logger.exception("Error authenticating with Magento")
        raise ECommerceApiError(f"Connection to Magento server failed: {e}") from e


def _percent_encode(value):
    """Percent-encode a string for OAuth signing."""
    return urllib.parse.quote(str(value), safe="~")


def build_oauth_header(method, url, consumer_key, consumer_secret, token, token_secret, query_params=None):
    """Build the OAuth 1.0a Authorization header for Magento API requests."""
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        "oauth_token": token,
    }
    all_params = dict(oauth_params)
    if query_params:
        for k, v in query_params.items():
            all_params[k] = v
    encoded_params = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        method.upper(),
        _percent_encode(url),
        _percent_encode(encoded_params),
    ])
    key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"
    digest = hmac.new(
        key.encode(),
        base_string.encode(),
        hashlib.sha256
    ).digest()
    oauth_params["oauth_signature"] = base64.b64encode(digest).decode()
    header = "OAuth " + ", ".join(
        f'{k}="{_percent_encode(v)}"' for k, v in oauth_params.items()
    )
    return header


def make_paginated_request(ec_account, method, route, params=None, page_size=100, current_page=1):
    """Handle pagination when fetching Magento resources."""
    items = []
    total_count = None
    while total_count is None or (current_page - 1) * page_size < total_count:
        page_params = {
            **(params or {}),
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[currentPage]": current_page,
        }
        data = make_request(ec_account, method, route, page_params)
        if not data.get("items"):
            break
        if total_count is None:
            total_count = data.get("total_count", 0)
        current_page += 1
        items.extend(data.get("items", []))
    return items


def make_request(ec_account, method, route, params=None, payload=None, **kwargs):
    """Send a request to the Magento REST API.

    :param ec_account: The magento ecommerce.account record for credentials.
    :param method: HTTP method
    :param route: API route
    :param params: Query parameters
    :param payload: JSON payload for POST/PUT requests
    :param refresh_token_on_401: Whether to refresh the token on 401 Unauthorized
    :rtype dict
    :return: The JSON response from Magento or an error dictionary.
    """
    base_url = ec_account.magento_base_url.rstrip("/")  # Ensure no trailing slash
    # URL WITHOUT query (for signing)
    signing_url = url_join(base_url, f"rest/V1{route}")
    # URL WITH query (for HTTP request)
    query_string = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted((params or {}).items())
    )
    request_url = signing_url
    if query_string:
        request_url = f"{signing_url}?{query_string}"
    headers = {}
    if ec_account.magento_auth_method == "token":
        headers["Authorization"] = f"Bearer {ec_account.magento_admin_access_token}"
    else:  # ec_account.magento_auth_method == "oauth"
        headers["Authorization"] = build_oauth_header(
            method=method,
            url=signing_url,
            consumer_key=ec_account.magento_oauth_consumer_key,
            consumer_secret=ec_account.magento_oauth_consumer_secret,
            token=ec_account.magento_oauth_access_token,
            token_secret=ec_account.magento_oauth_access_token_secret,
            query_params=params,
        )
    try:
        # Magento REST API version: 2.4.8-admin
        response = requests.request(method, request_url, headers=headers,  # params=params
            json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if ec_account.magento_auth_method == "token" and e.response.status_code == 401 and kwargs.get("refresh_token_on_401", True):
            _logger.exception("Unauthorized access to Magento API. Will try to fetch a new token if this is due to expired token.")
            access_token = get_admin_access_token(base_url, ec_account.magento_admin_username, ec_account.magento_admin_password)
            ec_account.magento_admin_access_token = access_token
            return make_request(ec_account, method, route, params, payload, refresh_token_on_401=False)
        message = e.response.text
        with contextlib.suppress(json.JSONDecodeError):
            message = e.response.json().get("message") or message
        _logger.exception("HTTP error occurred in Magento: %s", message)
        err = ECommerceApiError(message)
        err.http_status = e.response.status_code
        raise err from e
    except requests.exceptions.RequestException as e:
        _logger.exception("Error calling Magento API")
        raise ECommerceApiError(f"Error calling Magento API: {e}") from e
    except json.JSONDecodeError as e:
        _logger.exception("Failed to decode JSON response from Magento.")
        raise ECommerceApiError(f"Failed to decode JSON response from Magento: {e}") from e
