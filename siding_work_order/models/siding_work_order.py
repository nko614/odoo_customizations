from odoo import models, fields, api
import base64


class SidingWorkOrder(models.Model):
    _name = 'x_siding_work_order'
    _description = 'Siding Work Order'
    _order = 'date_order desc, id desc'
    
    name = fields.Char(string='Work Order', required=True)
    date_order = fields.Date(string='Date')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    
    # Scope (top-left checkboxes)
    scope_whole_house = fields.Boolean(string='Whole House')
    scope_walls_only = fields.Boolean(string='Walls Only')
    scope_soffit_fascia_only = fields.Boolean(string='Soffit/Fascia Only')
    scope_stone = fields.Boolean(string='Stone')
    scope_stucco = fields.Boolean(string='Stucco')
    scope_repair = fields.Boolean(string='Repair')
    scope_gutters_to_follow = fields.Boolean(string='Gutters to Follow')
    scope_painting_to_follow = fields.Boolean(string='Painting to Follow')
    
    # Customer (res.partner reference)
    partner_id = fields.Many2one('res.partner', string='Customer', required=False)
    
    # Installation Address (can be different from customer's default address)
    installation_street = fields.Char(string='Installation Street')
    installation_city = fields.Char(string='Installation City')
    installation_state = fields.Char(string='Installation State')
    installation_zip = fields.Char(string='Installation Zip')
    
    # Customer fields (auto-populated from partner)
    customer_name = fields.Char(string='Customer Name(s)', related='partner_id.name', readonly=False, store=True)
    mailing_street = fields.Char(string='Mailing Street', related='partner_id.street', readonly=False, store=True)
    mailing_city = fields.Char(string='Mailing City', related='partner_id.city', readonly=False, store=True)
    mailing_state = fields.Char(string='Mailing State', related='partner_id.state_id.code', readonly=False, store=True)
    mailing_zip = fields.Char(string='Mailing Zip', related='partner_id.zip', readonly=False, store=True)
    customer_email = fields.Char(string='Customer Email', related='partner_id.email', readonly=False, store=True)
    phone_primary = fields.Char(string='Phone (Primary)', related='partner_id.phone', readonly=False, store=True)
    phone_alt = fields.Char(string='Phone (Alt)')
    
    # BODY OF HOUSE — LIFETIME VINYL & FIBERGLASS
    vinyl_alside_charter_oak = fields.Boolean(string='Alside Charter Oak')
    vinyl_alside_prodigy = fields.Boolean(string='Alside Prodigy')
    vinyl_alside_other = fields.Char(string='Alside Other (specify)')
    vinyl_mastic_quest = fields.Boolean(string='Mastic Quest')
    vinyl_ascend_fiberglass = fields.Boolean(string='Ascend Fiberglass')
    vinyl_mastic_other = fields.Char(string='Mastic Other (specify)')
    vinyl_siding_color = fields.Char(string='Siding Color')
    vinyl_siding_profile = fields.Selection([
        ('straight_lap', 'Straight Lap'),
        ('dutch_lap', 'Dutch Lap'),
        ('bb', 'B&B / Board & Batten')
    ], string='Siding Profile')
    vinyl_size_in = fields.Char(string='Size (inches)')
    vinyl_sqft = fields.Float(string='Sq Ft Siding')
    vinyl_corner_color_mode = fields.Selection([
        ('same', 'Same as Siding'),
        ('white', 'White'),
        ('other', 'Other')
    ], string='Corner Color')
    vinyl_corner_color_other = fields.Char(string='Corner Color (Other)')
    
    # BODY OF HOUSE — LIFETIME STEEL
    steel_alside_satinwood_select = fields.Boolean(string='Alside Satinwood Select')
    steel_revere_cedar_wood = fields.Boolean(string='Revere Cedar Wood')
    steel_other = fields.Char(string='Other (Steel)')
    steel_siding_color = fields.Char(string='Siding Color')
    steel_siding_profile = fields.Selection([
        ('straight_lap', 'Straight Lap'),
        ('dutch_lap', 'Dutch Lap'),
        ('bb', 'B&B / Board & Batten')
    ], string='Siding Profile')
    steel_size_in = fields.Char(string='Size (inches)')
    steel_sqft = fields.Float(string='Sq Ft Siding')
    
    # BODY OF HOUSE — HARDBOARD
    hb_james_hardie_plank = fields.Boolean(string='James Hardie Plank')
    hb_james_hardie_panels = fields.Boolean(string='James Hardie Panels')
    hb_color_plus = fields.Boolean(string='Color Plus')
    hb_james_hardie_cemplank = fields.Boolean(string='James Hardie Cemplank')
    hb_collins_tru_wood = fields.Boolean(string='Collins Tru Wood')
    hb_lp_smartsiding = fields.Boolean(string='LP Smartsiding')
    hb_diamond_kote = fields.Boolean(string='Diamond Kote')
    hb_real_cedar = fields.Boolean(string='Real Cedar')
    hb_other = fields.Char(string='Other (Hardboard)')
    hb_batten_spacing = fields.Selection([
        ('12', '12"'),
        ('16', '16"'),
        ('24', '24"')
    ], string='Batten Spacing')
    hb_siding_color = fields.Char(string='Siding Color')
    hb_siding_profile = fields.Char(string='Siding Profile')
    hb_size_in = fields.Char(string='Size (inches)')
    hb_sqft = fields.Float(string='Sq Ft Siding')
    
    # STUCCO
    stucco_whole_house = fields.Boolean(string='Stucco Whole House')
    stucco_partial = fields.Boolean(string='Stucco Partial')
    stucco_mesh_overlay = fields.Boolean(string='Mesh Overlay')
    stucco_remove_reinstall = fields.Boolean(string='Remove/Reinstall')
    stucco_location_desc = fields.Text(string='Stucco Location/Description')
    
    # TRIM AREAS — SOFFIT
    soffit_replace = fields.Boolean(string='Soffit Replace')
    soffit_cover = fields.Boolean(string='Soffit Cover')
    soffit_vinyl = fields.Boolean(string='Soffit Vinyl')
    soffit_aluminum = fields.Boolean(string='Soffit Aluminum')
    soffit_vented_for_eaves = fields.Boolean(string='Vented for Eaves')
    soffit_brand_james_hardie = fields.Boolean(string='James Hardie')
    soffit_brand_lp = fields.Boolean(string='LP')
    soffit_brand_collins_tru_wood = fields.Boolean(string='Collins Tru Wood')
    soffit_size = fields.Selection([
        ('0_12', '0–12"'),
        ('13_24', '13–24"'),
        ('24_48', '24–48"'),
        ('other', 'Other')
    ], string='Soffit Size')
    soffit_size_other = fields.Char(string='Soffit Size (Other)')
    soffit_lin_ft = fields.Float(string='Soffit Linear FT')
    soffit_sq_ft = fields.Float(string='Soffit SQ FT')
    soffit_color = fields.Char(string='Soffit Color')
    
    # WINDOW TRIM
    window_trim_hardie = fields.Boolean(string='Window Trim: Hardie')
    window_trim_miratec = fields.Boolean(string='Window Trim: Miratec')
    window_trim_other = fields.Char(string='Window Trim: Other')
    window_trim_color = fields.Char(string='Window Trim Color')
    
    # WRAPS / TRIM
    wrap_no_windows = fields.Boolean(string='Wrap: No Windows')
    wrap_no_windows_color = fields.Char(string='No Windows Color')
    wrap_no_entry_doors = fields.Boolean(string='Wrap: No Entry Doors')
    wrap_no_entry_doors_color = fields.Char(string='No Entry Doors Color')
    wrap_no_garage_doors = fields.Boolean(string='Wrap: No Garage Doors')
    wrap_no_garage_doors_color = fields.Char(string='No Garage Doors Color')
    wrap_ft_post_wraps = fields.Float(string='FT. Post Wraps')
    wrap_ft_post_wraps_color = fields.Char(string='Post Wraps Color')
    wrap_ft_beam_wrap = fields.Float(string='FT. Beam Wrap')
    wrap_ft_beam_wrap_color = fields.Char(string='Beam Wrap Color')
    wrap_base_only = fields.Boolean(string='Base Only')
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            # Always sync installation address with mailing address
            self.installation_street = self.partner_id.street
            self.installation_city = self.partner_id.city
            self.installation_state = self.partner_id.state_id.code if self.partner_id.state_id else False
            self.installation_zip = self.partner_id.zip
    
    def action_print_and_attach(self):
        """Generate PDF and attach to related sale order"""
        self.ensure_one()
        
        # First, just trigger the report download
        report_action = self.env.ref('siding_work_order.report_siding_work_order').report_action(self)
        
        # If there's a sale order, also create the attachment
        if self.sale_order_id:
            try:
                # Get the report
                report = self.env.ref('siding_work_order.report_siding_work_order')
                
                # Generate PDF content
                pdf_content, _ = report.sudo()._render_qweb_pdf(self.ids)
                
                # Check if attachment already exists and delete it
                existing_attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sale.order'),
                    ('res_id', '=', self.sale_order_id.id),
                    ('name', '=', f'Work_Order_{self.name}.pdf')
                ])
                if existing_attachment:
                    existing_attachment.unlink()
                
                # Create new attachment
                attachment = self.env['ir.attachment'].create({
                    'name': f'Work_Order_{self.name}.pdf',
                    'type': 'binary',
                    'datas': base64.b64encode(pdf_content),
                    'res_model': 'sale.order',
                    'res_id': self.sale_order_id.id,
                })
                
                # Add a notification to the report action
                report_action['context'] = {
                    'notification': {
                        'type': 'success',
                        'message': f'PDF attached to Sale Order {self.sale_order_id.name}',
                    }
                }
            except Exception as e:
                # Log the error but still return the report
                pass
        
        return report_action