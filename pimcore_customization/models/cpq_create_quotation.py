# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from datetime import date

class Cpq_createQuotationLines(models.Model):
    _name = 'cpq.create.quotation.lines'
    _description = 'Cpq Create Quotation Lines'

    display_type = fields.Selection([('line_section', "Section")], default=False)
    name = fields.Char('Description', required=True)
    product_template_id = fields.Many2one(comodel_name='product.template', string="Product")
    product_id = fields.Many2one(comodel_name='product.product', string="Product Variant")
    product_uom_qty = fields.Float(string="Quantity", default=0)
    price_unit = fields.Monetary(string="Price Unit")
    price_total = fields.Monetary(string="Total", store=True)
    quotation_product_line_id = fields.Many2one(comodel_name='cpq.create.quotation', string="Quotation Id")
    currency_id = fields.Many2one("res.currency", related='quotation_product_line_id.currency_id', string="Currency", readonly=True, required=True)

class CpqCreateQuotation(models.Model):
    _name = 'cpq.create.quotation'
    _description = "Cpq Create Quotation"

    partner_id = fields.Many2one('res.partner', string="Select Customer", required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    product_lines = fields.One2many('cpq.create.quotation.lines', 'quotation_product_line_id', string="Product Lines")
    client_order_ref = fields.Char(string='Customer Reference')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True,related="pricelist_id.currency_id")
    wizard_id = fields.Many2one(comodel_name='cpq.product.info', string="Wizard Id")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        context = self.env.context
        order_date = context.get('order_date') or date.today()
        list_data = self.data_retrive_of_selected_lines(context.get('estimation_id'), context.get('currency_id'),order_date)

        if context.get('currency_id', False):
            res.update({'currency_id': int(context.get('currency_id'))})
        res.update({
            'product_lines': list_data,
            'company_id': self.env.company.id,
        })
        return res

    def data_retrive_of_selected_lines(self, estimation_id, currency_id, order_date):
        line_list = []
        grand_total = 0
        estimation = self.env['cpq.product.info'].browse(estimation_id)
        currency = self.env['res.currency'].browse(currency_id)

        for wizard_id in estimation:
            section_line = {
                'display_type': 'line_section',
                'name': wizard_id.product_template_id.name or "Section",
                'product_id': False,
                'product_uom_qty': 0,
            }
            line_list.append((0, 0, section_line))

            total_qty = sum(variant.product_qty for variant in wizard_id.product_variant_line)
            for variant in wizard_id.product_variant_line:
                if variant.product_qty > 0:
                    total = (variant.product_variant.lst_price * variant.product_qty)
                    grand_total += total
                    price_unit = self.get_product_price(variant.product_variant, variant.product_qty, order_date)
                    line_list.append((0, 0, {
                        'product_id': variant.product_variant.id,
                        'name': variant.product_variant.display_name,
                        'product_template_id': wizard_id.product_template_id.id,
                        'product_uom_qty': variant.product_qty,
                        'price_unit': price_unit if price_unit else variant.product_variant.lst_price,
                        'price_total': total
                    }))

            products_to_process = wizard_id.printing_product_ids | wizard_id.delivery_product_ids
            for product in products_to_process:
                price_unit = product.lst_price
                product_qty = total_qty if product in wizard_id.printing_product_ids else 1
                total = price_unit * product_qty
                grand_total += total
                line_list.append((0, 0, {
                    'product_id': product.id,
                    'name': product.display_name,
                    'product_template_id': product.product_tmpl_id.id,
                    'price_unit': price_unit,
                    'product_uom_qty': total_qty if product in wizard_id.printing_product_ids else 1,
                    'price_total': total
                }))

        return line_list

    def action_create_sale_order(self):
        sale_order_vals = {
            'partner_id': self.partner_id.id,
            'pricelist_id': self.pricelist_id.id,
            'client_order_ref': self.client_order_ref,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
        }

        sale_order = self.env['sale.order'].with_context(cpq=True).create(sale_order_vals)
        order_line_data = self.data_retrive_of_selected_lines(self.env.context.get('estimation_id'), self.env.context.get('currency_id'),sale_order.date_order)
        final_line_data = [(item[0], item[1], {**item[2], 'show_cpq': True}) for item in order_line_data]

        if final_line_data:
            sale_order.with_context(cpq=True).write({'order_line': final_line_data})

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': sale_order.id,
            'target': 'current',
        }

    @api.onchange('currency_id')
    def onchange_pricelist_is(self):
        for val in self.product_lines:
            if not val.price_total:
                continue
            total = val.product_uom_qty * val.product_id.lst_price
            price_unit= val.product_id.lst_price
            converted_total =  self.env.company.currency_id._convert(total, self.currency_id ,self.env.company,date.today())
            converted_price_unit =  self.env.company.currency_id._convert(price_unit, self.currency_id ,self.env.company,date.today())
            val.price_total = converted_total
            val.price_unit = converted_price_unit

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