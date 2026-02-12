from odoo import models, fields, api
import base64


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'
    
    @api.model
    def default_get(self, fields_list):
        """Override to add work order attachments when sending sale order emails"""
        res = super().default_get(fields_list)
        
        # Check if we're composing an email for a sale order
        if res.get('model') == 'sale.order' and res.get('res_ids'):
            # Parse res_ids which might come as a string or list
            res_ids = res['res_ids']
            if isinstance(res_ids, str):
                # Handle string format like '[28]'
                import ast
                try:
                    res_ids = ast.literal_eval(res_ids)
                except:
                    return res
            
            if not isinstance(res_ids, list):
                res_ids = [res_ids]
            
            if not res_ids:
                return res
                
            sale_order_id = res_ids[0]
            sale_order = self.env['sale.order'].browse(sale_order_id)
            
            # Find related work orders
            work_orders = self.env['x_siding_work_order'].search([
                ('sale_order_id', '=', sale_order.id)
            ])
            
            if work_orders:
                attachment_ids = res.get('attachment_ids', [])
                
                for work_order in work_orders:
                    try:
                        # Check if attachment already exists
                        existing_attachment = self.env['ir.attachment'].search([
                            ('res_model', '=', 'sale.order'),
                            ('res_id', '=', sale_order.id),
                            ('name', '=', f'Work_Order_{work_order.name}.pdf')
                        ], limit=1)
                        
                        if not existing_attachment:
                            # Generate the PDF
                            report = self.env.ref('siding_work_order.report_siding_work_order', raise_if_not_found=False)
                            if not report:
                                report = self.env['ir.actions.report'].search([
                                    ('model', '=', 'x_siding_work_order')
                                ], limit=1)
                            
                            if report:
                                pdf_content, _ = report.sudo()._render_qweb_pdf(work_order.ids)
                                
                                # Create attachment
                                attachment = self.env['ir.attachment'].create({
                                    'name': f'Work_Order_{work_order.name}.pdf',
                                    'type': 'binary',
                                    'datas': base64.b64encode(pdf_content),
                                    'res_model': 'sale.order',
                                    'res_id': sale_order.id,
                                })
                                attachment_ids.append((4, attachment.id, False))
                        else:
                            attachment_ids.append((4, existing_attachment.id, False))
                    except Exception:
                        continue
                
                res['attachment_ids'] = attachment_ids
        
        return res