# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    tracking_number = fields.Char(string="Tracking Number", help="Tracking number for the purchase order.")
    sale_line_id = fields.Many2one('sale.order.line', string="Source Sale Order Line")
    custom_printing_service_id = fields.Many2one('product.product', string="Printing Service")
    custom_section_name = fields.Char(string="Section Name")
    is_printing_po = fields.Boolean(string="Is Printing PO")
    custom_so_id = fields.Many2one('sale.order', string="Sale Order Link") 

    def assign_dropship_partners(self, sale_order):
        """
        Dynamically assign the partner_id for dropshipments based on POs sequence.
        """
        purchase_orders = self.env['purchase.order'].search([
            ('origin', '=', sale_order.name)
        ], order='id asc')

        for index, po in enumerate(purchase_orders):
            # Fetch the related dropshipments for the current PO
            related_pickings = self.env['stock.picking'].search([
                ('purchase_id', '=', po.id),
                ('picking_type_id.code', '=', 'dropship')
            ])
            partner_to_assign = None

            for next_index in range(index + 1, len(purchase_orders)):
                next_po = purchase_orders[next_index]
                # Check if any product in the next PO has `product_service_type` as 'service'
                service_products = next_po.order_line.filtered(
                    lambda line: line.product_id.product_service_type == 'printing'
                )
                if service_products:
                    partner_to_assign = next_po.partner_id
                    break

            # If no suitable vendor found and this is the last PO, assign sale order partner
            if not partner_to_assign:
                if index == len(purchase_orders) - 1:  # Check if it's the last PO
                    partner_to_assign = sale_order.partner_id
                else:
                    partner_to_assign = sale_order.partner_id

            # Update the partner_id in related dropshipments
            if partner_to_assign:
                related_pickings.write({'partner_id': partner_to_assign.id})

    def _compute_access_url(self):
        for order in self:
            page_name = self.env.context.get('page_name', '')  # Retrieve page name from context
            if page_name == 'my_purchase_orders':
                order.access_url = '/my/custom_purchase_orders/%s' % (order.id)
            else:
                order.access_url = '/my/purchase/%s' % (order.id)

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()

        sale_orders = self.mapped('order_line.sale_order_id')

        purchase_orders = sale_orders._get_purchase_orders()
        simple_pos = purchase_orders.filtered(lambda po: self._is_simple_po(po))
        simple_printing_pos = purchase_orders.filtered(lambda po: self._is_simple_printing_po(po)).sorted('id')
        printing_pos = purchase_orders.filtered(lambda po: self._is_printing_po(po)).sorted('id')
        for po in self:
            if self._is_simple_po(po):
                related_pickings = self.env['stock.picking'].search([
                ('purchase_id', '=', po.id),
                ('picking_type_id.code', '=', 'dropship')
                 ])
                if related_pickings:
                    if simple_printing_pos:
                        first_simple_printing_po = simple_printing_pos[0]
                        related_pickings.write({'partner_id': first_simple_printing_po.partner_id.id})
                    elif printing_pos:
                        first_printing_po = printing_pos[0]
                        related_pickings.write({'partner_id': first_printing_po.partner_id.id})
            elif self._is_simple_printing_po(po):
                if simple_pos:
                   self._ensure_no_unconfirmed_pos(simple_pos, po, "simple product POs")

                self._ensure_po_sequence(simple_printing_pos, po, "simple+printing POs")

                current_index = next((i for i, p in enumerate(simple_printing_pos) if p.id == po.id), None)
                if current_index is not None and current_index < len(simple_printing_pos) - 1:
                    next_simple_printing_po = simple_printing_pos[current_index + 1]
                    po._assign_dropship_partner(next_simple_printing_po.partner_id.id)
                else:
                    if printing_pos:
                        first_printing_po = printing_pos[0]
                        po._assign_dropship_partner(first_printing_po.partner_id.id)
                    else:
                        po._assign_dropship_partner(sale_orders.partner_id.id)

            elif self._is_printing_po(po):
                if simple_pos:
                    self._ensure_no_unconfirmed_pos(simple_pos, po, "simple product POs")
                if simple_printing_pos:
                    self._ensure_no_unconfirmed_pos(simple_printing_pos, po, "simple+printing POs")

                self._ensure_po_sequence(printing_pos, po, "printing POs")

                current_index = next((i for i, p in enumerate(printing_pos) if p.id == po.id), None)

                if current_index is not None and current_index < len(printing_pos) - 1:
                    # Not the last Printing PO
                    next_printing_po = printing_pos[current_index + 1]
                    po._assign_dropship_partner(next_printing_po.partner_id.id)
                else:
                    # Last Printing PO
                    po._assign_dropship_partner(sale_orders.partner_id.id)
        return res

    def _is_simple_po(self, po):
        product_types = po.order_line.filtered(
            lambda line: line.product_id.product_service_type != 'delivery'
        ).mapped('product_id.product_service_type')
        return all(pt == 'finished' for pt in product_types)

    def _is_simple_printing_po(self, po):
        product_types = po.order_line.filtered(
            lambda line: line.product_id.product_service_type != 'delivery'
        ).mapped('product_id.product_service_type')
        has_supplier = any(pt == 'finished' for pt in product_types)
        has_service = any(pt == 'printing' for pt in product_types)
        return len(product_types) >= 2 and has_supplier and has_service

    def _is_printing_po(self, po):
        product_types = po.order_line.mapped('product_id.product_service_type')
        return all(pt == 'printing' for pt in product_types)

    def _ensure_no_unconfirmed_pos(self, pos, current_po, pos_type):
        if not self.company_id.purchase_validation:
            return  # Skip validation if purchase validation is disabled

        unconfirmed_pos = pos.filtered(lambda p: p.state != 'purchase')
        if unconfirmed_pos and unconfirmed_pos[0] != current_po:
            raise UserError(f"Please confirm all {pos_type} before confirming {current_po.name}.")

    def _ensure_po_sequence(self, pos, current_po, pos_type):
        if not self.company_id.purchase_validation:
            return  # Skip validation if purchase validation is disabled

        previous_pos = pos.filtered(lambda p: p.id < current_po.id and p.state != 'purchase')
        if previous_pos:
            raise UserError(f"Please confirm {pos_type} in sequence. Confirm {previous_pos[-1].name} first.")

    def _assign_dropship_partner(self, partner_id):
        # dropship_pickings = self.picking_ids.filtered(
        #     lambda p: p.picking_type_id.code == 'dropship' and p.state not in ['done', 'cancel'])
        dropship_pickings = self.picking_ids.filtered(
            lambda p: (p.picking_type_id.code == 'dropship' or p.service_to_purchase) and p.state not in ['done', 'cancel'])
        # dropship_pickings = self.picking_ids.filtered(
        #     lambda p:p.state not in ['done', 'cancel'])
        picking_type = self.env.ref('stock_dropshipping.route_drop_shipping')
        dropship_pickings.write({'picking_type_id':picking_type.id,'partner_id': partner_id})

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)

        # Check if tracking_number or date_planned are updated
        if 'tracking_number' in vals or 'date_planned' in vals:
            template = self.env.ref('purchase.email_template_edi_purchase_done')
            for current_po in self:
                sale_order = current_po._get_sale_orders()
                next_po = self.env['purchase.order'].sudo().search(
                    [('id', '>', current_po.id)], order='id ASC', limit=1
                )
                if next_po and current_po.origin and current_po.origin == next_po.origin:
                    email_values = {'email_to': next_po.partner_id.email}
                    template.sudo().send_mail(current_po.id, force_send=False, email_values=email_values)

                elif next_po and next_po.origin != current_po.origin:
                    if sale_order and sale_order.partner_id:
                        email_values = {'email_to': sale_order.partner_id.email}
                        template.sudo().send_mail(current_po.id, force_send=False, email_values=email_values)

                elif not next_po and current_po.origin:
                    sale_order = self.env['sale.order'].sudo().search([
                        ('name', '=', current_po.origin)
                    ], limit=1)
                    if sale_order and sale_order.partner_id:
                        email_values = {'email_to': sale_order.partner_id.email}
                        template.sudo().send_mail(current_po.id, force_send=False, email_values=email_values)

        return res