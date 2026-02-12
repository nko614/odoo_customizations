import hmac
import json
import logging
from urllib.parse import urlparse

from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.http import request
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url):
    """Normalize LinkedIn URL for consistent deduplication.

    Handles variations like:
      linkedin.com/in/Name/  →  https://linkedin.com/in/name
      https://www.linkedin.com/in/name?foo=bar  →  https://linkedin.com/in/name
    """
    if not url:
        return False
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    path = parsed.path.lower().rstrip('/')
    return f"https://{host}{path}"


def _normalize_record(record):
    """Map PhantomBuster field names to our standard format.

    PhantomBuster sends: profileUrl, firstName, lastName, company,
    headline, jobTitle, location, etc.
    We also accept our own field names directly.
    """
    # Build name from firstName + lastName if 'name'/'fullName' not provided
    name = record.get('name') or record.get('fullName') or ''
    if not name:
        first = (record.get('firstName') or record.get('first_name') or '').strip()
        last = (record.get('lastName') or record.get('last_name') or '').strip()
        name = f"{first} {last}".strip()

    return {
        'name': name,
        'linkedin_url': (record.get('linkedin_url')
                         or record.get('profileLink')
                         or record.get('profileUrl')
                         or record.get('linkedInProfileUrl')
                         or record.get('profile_url')
                         or ''),
        'email': record.get('email') or record.get('mail') or '',
        'phone': record.get('phone') or record.get('phoneNumber') or '',
        'current_company': (record.get('current_company')
                            or record.get('company')
                            or record.get('companyName')
                            or ''),
        'headline': (record.get('headline')
                     or record.get('occupation')
                     or record.get('title')
                     or record.get('jobTitle')
                     or record.get('job')
                     or ''),
    }


class LinkedinWebhookController(http.Controller):

    @http.route('/linkedin/webhook', type='http', auth='public',
                methods=['POST'], csrf=False)
    def linkedin_webhook(self):
        # --- Authenticate ---
        api_key = request.env['ir.config_parameter'].sudo().get_param(
            'linkedin_lead_webhook.api_key'
        )
        received_key = request.httprequest.headers.get('X-API-Key', '')

        if not api_key:
            _logger.warning("LinkedIn webhook called but no API key configured")
            return request.make_json_response(
                {'error': 'Webhook API key not configured. Set it in CRM > Settings.'},
                status=401,
            )

        if not hmac.compare_digest(api_key, received_key):
            return request.make_json_response(
                {'error': 'Unauthorized'},
                status=401,
            )

        # --- Parse payload ---
        try:
            data = request.get_json_data()
        except Exception:
            return request.make_json_response(
                {'error': 'Invalid JSON payload'},
                status=400,
            )

        # Accept single record or array
        records = data if isinstance(data, list) else [data]

        if not records:
            return request.make_json_response(
                {'error': 'Empty payload'},
                status=400,
            )

        # --- Process records ---
        env = request.env(su=True)
        created = 0
        updated = 0
        failed = 0
        errors = []

        # Cache UTM source/medium lookups
        linkedin_source = env.ref('utm.utm_source_linkedin', raise_if_not_found=False)
        linkedin_medium = env.ref('utm.utm_medium_linkedin', raise_if_not_found=False)

        for raw_record in records:
            record = _normalize_record(raw_record)
            try:
                name = (record.get('name') or '').strip()
                linkedin_url = _normalize_linkedin_url(record.get('linkedin_url'))

                if not name or not linkedin_url:
                    failed += 1
                    errors.append(f"Missing name or linkedin_url: {record.get('name', '?')}")
                    continue

                with env.cr.savepoint():
                    result = self._process_record(
                        env, record, name, linkedin_url,
                        linkedin_source, linkedin_medium,
                    )
                    if result == 'created':
                        created += 1
                    else:
                        updated += 1

            except Exception as e:
                failed += 1
                errors.append(f"{record.get('name', '?')}: {str(e)}")
                _logger.error("LinkedIn webhook error for %s: %s", record.get('name'), e)

        # --- Log the import ---
        total = len(records)
        if failed == 0:
            state = 'success'
        elif failed == total:
            state = 'failed'
        else:
            state = 'partial'

        raw = json.dumps(data, indent=2, default=str)
        if len(raw) > 50000:
            raw = raw[:50000] + '\n... (truncated)'

        env['linkedin.import.log'].create({
            'records_received': total,
            'records_created': created,
            'records_updated': updated,
            'records_failed': failed,
            'state': state,
            'error_details': '\n'.join(errors) if errors else False,
            'raw_payload': raw,
        })

        # --- Response ---
        status_code = 200 if failed == 0 else 207
        return request.make_json_response({
            'status': state,
            'received': total,
            'created': created,
            'duplicates_skipped': updated,
            'failed': failed,
            'errors': errors or [],
        }, status=status_code)

    def _process_record(self, env, record, name, linkedin_url,
                        linkedin_source, linkedin_medium):
        """Process a single LinkedIn follower record. Returns 'created' or 'updated'."""
        email = (record.get('email') or '').strip() or False
        normalized_email = email_normalize(email) if email else False
        company = (record.get('current_company') or '').strip() or False
        headline = (record.get('headline') or '').strip() or False
        phone = (record.get('phone') or '').strip() or False

        # --- Find or create partner ---
        partner = env['res.partner'].search(
            [('linkedin_url', '=', linkedin_url)], limit=1,
        )

        if not partner and normalized_email:
            partner = env['res.partner'].search(
                [('email_normalized', '=', normalized_email)], limit=1,
            )

        if partner:
            # Fill blank fields only
            update_vals = {}
            if not partner.linkedin_url and linkedin_url:
                update_vals['linkedin_url'] = linkedin_url
            if not partner.email and email:
                update_vals['email'] = email
            if not partner.phone and phone:
                update_vals['phone'] = phone
            if not partner.company_name and company:
                update_vals['company_name'] = company
            if not partner.function and headline:
                update_vals['function'] = headline
            if update_vals:
                partner.write(update_vals)

            # Check for existing lead
            lead_domain = [
                ('partner_id', '=', partner.id),
                ('type', '=', 'lead'),
            ]
            if linkedin_source:
                lead_domain.append(('source_id', '=', linkedin_source.id))
            if env['crm.lead'].search(lead_domain, limit=1):
                return 'updated'
        else:
            partner = env['res.partner'].create({
                'name': name,
                'linkedin_url': linkedin_url,
                'email': email or False,
                'phone': phone,
                'company_name': company,
                'function': headline,
            })

        # --- Create lead ---
        lead_vals = {
            'name': f"LinkedIn: {name}",
            'type': 'lead',
            'partner_id': partner.id,
            'contact_name': name,
            'partner_name': company,
            'email_from': email or False,
            'phone': phone,
            'function': headline,
            'website': linkedin_url,
            'description': f"LinkedIn Profile: {linkedin_url}",
        }
        if linkedin_source:
            lead_vals['source_id'] = linkedin_source.id
        if linkedin_medium:
            lead_vals['medium_id'] = linkedin_medium.id

        env['crm.lead'].create(lead_vals)
        return 'created'
