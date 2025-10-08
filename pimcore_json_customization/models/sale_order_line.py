# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_product_added_from_json = fields.Boolean()
    parent_sale_line_id = fields.Many2one('sale.order.line')
    printing_line_id = fields.Many2one('printing.colors.and.sizes')
    delivery_line_id = fields.Many2one('shipping.products')

    def write(self, vals):
        if self.env.context.get('avoid_recursion'):
            return super().write(vals)

        res = super().write(vals)

        if 'product_uom_qty' in vals:
            for line in self.filtered(lambda x: x.is_product_added_from_json):
                line.with_context(avoid_recursion=True)._update_for_json_service_line_qty(line.order_id)
        return res

    def _update_for_json_service_line_qty(self, order):
        for raw_sale_line in order.order_line.filtered(lambda l: l.is_product_added_from_json and not l.parent_sale_line_id):
            related_service_lines = order.order_line.filtered(
                lambda l: l.parent_sale_line_id == raw_sale_line and l.product_service_type not in ['delivery', 'extra_charges']
            )
            related_service_lines.with_context(avoid_recursion=True).sudo().write({
                'product_uom_qty': raw_sale_line.product_uom_qty
            })
