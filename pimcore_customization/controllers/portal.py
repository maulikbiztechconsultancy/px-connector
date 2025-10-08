# -*- coding: utf-8 -*-
# Part of BiztechCS. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

class PortalPurchaseOrders(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'purchase_count' in counters:
            values['purchase_count'] = request.env['purchase.order'].sudo().search_count([
                ('partner_id', '=', request.env.user.partner_id.id)
            ])
        return values

    @http.route(['/my/custom_purchase_orders', '/my/custom_purchase_orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_purchase_order_pimcore_customization(self, search=None, search_in='All'):
        searchbar_inputs = {
            'All': {'label': 'All', 'input': 'All', 'domain': []},
            'Vendor': {'label': 'Vendor', 'input': 'Vendor', 'domain': [('partner_id.name', 'ilike', search)]},
            'Status': {'label': 'Status', 'input': 'Status', 'domain': [('state', 'ilike', search)]},
        }

        # Add filter for purchase orders with specific states 
        state_filter = [('state', 'in', ['purchase', 'done', 'cancel'])]

        search_domain = searchbar_inputs[search_in]['domain'] + [
                ('partner_id', '=', request.env.user.partner_id.id)
            ]+state_filter

        # Fetch purchase orders for the logged-in user's partner
        purchase_orders = request.env['purchase.order'].sudo().with_context(page_name="my_purchase_orders").search(search_domain)
        return request.render('pimcore_customization.portal_my_home_purchase_orders_views', {
            'custom_purchase_orders': purchase_orders,
            'page_name': 'custom_purchase_orders',
            'search': search,
            'search_in': search_in,
            'searchbar_inputs': searchbar_inputs,
            'default_url': '/my/custom_purchase_orders',
            'my_purchase_orders': True
        })

    @http.route(['/my/custom_purchase_orders/<int:order_id>'], type='http', auth="public", website=True)
    def portal_my_purchase_order_custom(self, order_id=None, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Filter purchase orders based on the logged-in user's partner_id
        user_partner_id = request.env.user.partner_id.id
        if order_sudo.partner_id.id != user_partner_id:
            return request.redirect('/my')

        # Add context for page name
        order_sudo = order_sudo.with_context(page_name='my_purchase_orders')

        # Prepare values for the template
        values = self._purchase_order_get_page_view_values(order_sudo, access_token, **kw)
        values['page_name'] = 'custom_purchase_orders'
        values['purchase_order'] = order_sudo
        values['my_purchase_orders'] = True

        # Render the custom template
        return request.render('pimcore_customization.portal_my_purchase_order_custom', values)

    @http.route(['/purchase/save'], type='http', auth="public", website=True, csrf=False)
    def save_purchase_order(self, **post):
        try:
            order_id = int(post.get('order_id'))
            date_planned = post.get('date_planned')
            tracking_number = post.get('tracking_number')

            # Fetch the current purchase order with sudo
            current_po = request.env['purchase.order'].sudo().browse(order_id)

            if current_po.exists():
                # Update the current purchase order
                current_po.write({
                    'date_planned': date_planned,
                    'tracking_number': tracking_number,
                })
            else:
                return request.redirect('/my')  # Redirect if the order doesn't exist

        except Exception as e:
            return request.redirect('/my')  # Handle unexpected errors

        # Redirect back to the updated purchase order page
        return request.redirect(f'/my/custom_purchase_orders/{order_id}')

