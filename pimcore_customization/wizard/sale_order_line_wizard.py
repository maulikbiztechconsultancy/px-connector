# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError

class SaleLinePropertiesWiz(models.TransientModel):
    _name = 'sale.line.properties.wiz'
    _description = 'Line Properties Wizard'

    name = fields.Char(string="Wizard")
    service_product_ids = fields.Many2many('product.product','service_product_rel','service_id','product_id',string="Printing Products", domain=[("product_service_type", '=', 'printing')])
    delivery_product_ids = fields.Many2many('product.product','delivery_product_rel','delivery_id','product_id',string="Delivery Products",domain=[("product_service_type", '=', 'delivery')])
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    step = fields.Selection([('service', 'Service Products'), ('delivery', 'Delivery Products')],string="Step",default='service')
    product_template_id = fields.Many2one('product.template',string="Product Template")

    @api.model
    def default_get(self, fields):
        """Set default values for the wizard based on context."""
        res = super(SaleLinePropertiesWiz, self).default_get(fields)

        sale_order_id = self.env.context.get('active_id')
        if sale_order_id:
            res['sale_order_id'] = sale_order_id

        product_template_id = self.env.context.get('default_product_tmpl_id')
        if product_template_id:
            res['product_template_id'] = product_template_id

        # Clear `printing_thumbnail` for service and delivery products
        return res

    def action_next_step(self):
        """Move to the next step and reopen the wizard."""
        if self.step == 'service':
            self.step = 'delivery'
        elif self.step == 'delivery':
            self.step = 'confirm'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Line Properties Wizard'),
            'res_model': 'sale.line.properties.wiz',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }

    def select_template_properties(self):
        sale_order = self.sale_order_id

        if not sale_order.exists():
             raise UserError('No valid Sale Order found in the context.')

        show_cpq = self.env.context.get('showCpq')
        product_ids = self.env['product.product'].browse(self.env.context.get('product_id_from_js'))
        product_quantities = self.env.context.get('product_quantities', {})
        if not self.product_template_id and not product_ids:
            raise UserError('No selected product template ID found in the context.')

        last_existing_line = self.env['sale.order.line'].search(
            [('order_id', '=', sale_order.id)], order='sequence desc', limit=1
        )
        max_sequence = last_existing_line.sequence if last_existing_line else 10

        new_lines = []

        selected_product = self.env['product.product'].search([('product_tmpl_id', '=',  self.product_template_id.id)], limit=1)
        selected_line_vals = {
            'order_id': sale_order.id,
            'product_id': selected_product.id,
            'product_template_id':  self.product_template_id.id,
            'product_uom_qty': 1,
            'price_unit': 0,
            'sequence': max_sequence + 1,
            'show_cpq':True
        }
        selected_section_lines, max_sequence = sale_order.add_section_and_product(selected_line_vals, max_sequence)
        new_lines.extend(selected_section_lines)

        configurator_id = self.env.context.get("configurator_wizard_id") or False
        if configurator_id:
            configurator = self.env['product.configurator.sale'].browse(configurator_id)
            if configurator.exists():
                values = configurator.action_config_done()
                new_lines.append((0,0,values))

        products_to_process = product_ids | self.service_product_ids | self.delivery_product_ids
        for product in products_to_process:
            price_unit = None
            for quantity in product_quantities.values():
                price = self.get_product_price(product, quantity, sale_order.date_order)
                price_unit = price
            max_sequence += 1
            new_lines.append((0, 0, {
                'product_id': product.id,
                'name': product.display_name,
                'product_uom_qty': product_quantities.get(str(product.id), 1),
                'sequence': max_sequence,
                'printing_thumbnail' : product.printing_thumbnail,
                'printing_thumbnail_name' : product.printing_thumbnail_name,
                'product_service_type' : product.product_service_type,
                'show_cpq': True
            }))

        sale_order.with_context(wizard_data=True).write({'order_line': new_lines}) 

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'context': {'view_type': 'form'},  # Move view_type here
            'view_mode': 'form',
        }

    def get_product_price(self, product, quantity, order_date):
        final_product_price = product.list_price
        data_list = []
        cust_price_lists = self.env['product.pricelist'].search([])  # Get all pricelists
        for pl in cust_price_lists:
            pricelist_item = pl._get_product_rule(product, quantity, uom=product.uom_id, date=order_date)
            if pricelist_item:
                data_list.append(pricelist_item)

        filtered_data_list = [item for item in data_list if item is not False]
        if filtered_data_list:
            cust_product_price_list_items = self.env['product.pricelist.item'].browse(filtered_data_list)
            final_product_price = min(cust_product_price_list_items.mapped('fixed_price'))  # Get the lowest fixed price
        return final_product_price