# -*- coding: utf-8 -*-
# Part of BiztechCS. See LICENSE file for full copyright and licensing details.

from odoo import http 
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
import base64
import ast

class PrintErpWebsiteSale(WebsiteSale):

    @http.route(['/my/artwork/approval'], type='json', auth='public', website=True)
    def artwork_approval(self, **kw):
        for line_id, datas in kw.get('data').items():
            comments = []
            if any(data['approval_status'] == 'reject' for data in datas):
                status = 'reject'
            elif any(data['approval_status'] == 'accept_with_change' for data in datas):
                status = 'accept_with_change'
            else:
                status = 'accept'
            for data in datas:
                comment = data.get('comment', '').strip()
                if comment:
                    comments.append(comment)
            all_comments = '\n'.join(comments)
            sale_line_id = request.env['sale.order.line'].sudo().browse(int(line_id))
            sale_line_id.update({'product_approval_status':status,'artwork_comment':all_comments})

        submit_type = kw.get('submit_type')
        kw_order_id = int(kw.get('order_id'))
        order = request.env['sale.order'].sudo().browse(kw_order_id)
        # For all Product Line apporve dwithout select any status
        if kw.get('isChecked'):
            for sale_line in order.order_line.filtered(lambda x: x.product_service_type == 'finished' and x.show_cpq):
                sale_line.update({'product_approval_status':'accept'})
                order.update({'state':'approved'})
        else:
            if all(line.product_approval_status in ['accept','accept_with_change']  for line in order.order_line.filtered(lambda x: x.product_service_type == 'printing')):
                order.update({'state':'approved'})
        template = request.env.ref(
            'pimcore_customization.email_template_confirmation_artwork_files_to_salesperson')
        # template.sudo().send_mail(order.id, True)
        if template:
            template.sudo().send_mail(order.id, force_send=True)
            body_html = template._render_field('body_html', [order.id])[order.id]
            order.message_post(body=body_html,subject=template.subject,message_type='comment',subtype_xmlid='mail.mt_note',)
        if order.state == 'approved':
            template_approved = request.env.ref('pimcore_customization.email_template_sale_order_approved')
            if template_approved:
                template_approved.sudo().send_mail(order.id, force_send=True)
                body_html = template_approved._render_field('body_html', [order.id])[order.id]
                order.message_post(body=body_html,subject=template_approved.subject,message_type='comment',subtype_xmlid='mail.mt_note',)
        order.artwork_page_url = False

    @http.route(['/shop/order_artwork/'], type='http', auth="public", website=True, csrf=False)
    def artwork_design_status(self, **kw):
        dict_str = base64.b64decode(kw.get('value')).decode('utf-8')
        data = ast.literal_eval(dict_str)
        kw_value = dict(data)
        token_varified = False
        order_id = request.env['sale.order'].sudo().browse(
            int(kw_value.get('order_id'))) if kw_value.get('order_id') else False
        if order_id.artwork_page_url and order_id.artwork_page_url in http.request.httprequest.full_path:
            token_varified = True

        required_approval = False
        send_approval_mail = False
        submit_type = False
        if kw_value.get('required_approval'):
            required_approval = True
        if kw.get('send_approval_mail') and kw.get('submit_type'):
            send_approval_mail = True
            submit_type = kw.get('submit_type')

        return request.render('pimcore_customization.artwork_approval_template', {
                                'sale_order': order_id,
                                'required_approval': required_approval,
                                'send_approval_mail': send_approval_mail,
                                'submit_type': submit_type,
                                'token_varified': token_varified})

    @http.route(['/update/artwork/order'], type='json', auth='public', website=True, csrf=False)
    def update_artwork_order(self, **kw):
        submit_type = kw.get('submit_type')
        order = request.env['sale.order'].sudo().browse(
            kw.get('order_id'))
        template = request.env.ref(
            'pimcore_customization.email_template_confirmation_artwork_files_to_salesperson')
        template.sudo().send_mail(order.id, True)
        order.artwork_page_url = False