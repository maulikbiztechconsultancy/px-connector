# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from datetime import date

class ProductVariantLines(models.Model):
    _name = 'product.variant.line'
    _description = "Product Variant Lines"

    product_variant_line_id = fields.Many2one(comodel_name='cpq.product.info', string="Product Variant line", required=True, ondelete='cascade', index=True, copy=False)
    product_template_id = fields.Many2one(string="Product Template",comodel_name='product.template')
    product_variant = fields.Many2one(comodel_name='product.product',string="Product Variant")
    product_qty = fields.Float(string="Quantity",default=0,store=True, readonly=False, required=True)

class CpqProductSectionLine(models.Model):
    _name = 'cpq.product.section.line'
    _description = "Cpq Product Section Line"

    wizard_id = fields.Many2one(comodel_name='cpq.product.info', string="Wizard Id")
    display_type = fields.Selection(selection=[('line_section', "Section")], default=False)
    name = fields.Char('Description', required=True)
    product_template_id = fields.Many2one(comodel_name='product.template', string="Product")
    product_variant_section = fields.Many2one(comodel_name='product.product', string="Product Variant")
    product_qty = fields.Float(string="Quantity", default=0)
    currency_id = fields.Many2one(
    'res.currency',
    string='Currency',
    required=True,
    related='wizard_id.currency_id'
    )
    price_unit = fields.Float(string="Price Unit")
    total = fields.Float(string="Total")

    def action_open_selected_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("pimcore_customization.cpq_product_section_view_form")
        action['res_id'] = self.id
        return action


class CpqProductInfo(models.Model):
    _name = 'cpq.product.info'
    _description = "Cpq Product Information"

    product_template_id = fields.Many2one('product.template', string="Select Product",required=True, domain=[('product_service_type', 'in', ['raw_product', 'finished'])])
    product_image = fields.Binary('Product Image', store=True)
    product_variant_line = fields.One2many(comodel_name='product.variant.line',inverse_name='product_variant_line_id',string="Product Variant Line",copy=True, auto_join=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", related='company_id.currency_id', string="Currency",required=True)
    printing_product_ids = fields.Many2many('product.product', 'service_product_cpq', 'service_id_cpq', 'product_id', string="Printing Products", domain=[("product_service_type", '=', 'printing')])
    delivery_product_ids = fields.Many2many('product.product', 'delivery_product_cpq', 'delivery_id_cpq', 'product_id', string="Delivery Products", domain=[("product_service_type", '=', 'delivery')])
    status = fields.Selection([('configure', 'Configure Product'),('printing', 'Add Printing'),('done', 'Finish'),], string="Status", default="configure")
    cpq_product_section_line = fields.One2many(comodel_name='cpq.product.section.line',inverse_name='wizard_id',string="Cpq Product Section Line")
    grand_total = fields.Monetary(string="Final Price", store=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super(CpqProductInfo, self).default_get(fields_list) or {}
        wizard_id = self.env.context.get('wizard_id')
        currency_id = self.env.context.get('currency_id') or self.env.company.currency_id.id
        if wizard_id:
            wizard = self.env['cpq.product.info'].browse(wizard_id)
            new_lines, grand_total = self._prepare_wizard_lines(wizard)
            defaults.update({
                'cpq_product_section_line': new_lines,
                'grand_total': grand_total,
                'currency_id':currency_id
            })
        return defaults

    @api.onchange('currency_id')
    def onchange_pricelist(self):
        grand_total = 0.0
        for val in self.cpq_product_section_line:
            if not val.price_unit:
                continue
            total = val.product_qty * val.product_template_id.list_price
            price_unit= val.product_template_id.list_price
            converted_total =  self.env.company.currency_id._convert(total, self.currency_id ,self.env.company,date.today())
            converted_price_unit =  self.env.company.currency_id._convert(price_unit, self.currency_id ,self.env.company,date.today())
            val.total = converted_total
            val.price_unit = converted_price_unit
            grand_total += converted_total
        self.grand_total = grand_total


    @api.onchange('product_template_id')
    def _onchange_product_template_id(self):
        if self.product_template_id:
            self.product_image = self.product_template_id.image_1920
            variant_lines = [
                (0, 0, {
                    'product_variant_line_id': self.id,
                    'product_template_id': self.product_template_id.id,
                    'product_variant': variant.id,
                })
                for variant in self.product_template_id.product_variant_ids
            ]
            self.product_variant_line = [(5, 0, 0)] + variant_lines

    def action_next_cpq(self):
        if self.status == 'configure':
            self.status = 'printing'
        elif self.status == 'printing':
            self.status = 'done'
        self.write({'printing_product_ids': self.printing_product_ids, 'delivery_product_ids': self.delivery_product_ids})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cpq.product.info',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {
                'active_wizard_id': self.id,
                'product_template_id': self.product_template_id,
                'product_variants': self.product_variant_line,
                'printing_products': self.printing_product_ids,
                'delivery_products': self.delivery_product_ids,
            },
        }

    def action_back_cpq(self):
        if self.status == 'printing':
            self.status = 'configure'  
        elif self.status == 'done':
            self.status = 'printing'  
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'CPQ Product Info',
            'res_model': 'cpq.product.info',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_add_cpq(self):
        self.write({'delivery_product_ids': self.delivery_product_ids})
        wizard = self
        new_lines, grand_total = self._prepare_wizard_lines(wizard)
        self.write({'grand_total': grand_total})
        return {
            'type': 'ir.actions.client',
            'name': 'Cpq Product List',
            'tag': 'dynamic_estimation_calculator_view',
            'target': 'main',
        }

    @api.model
    def _prepare_wizard_lines(self, wizard):
        new_lines = []
        grand_total = 0

        # Add section line
        new_lines.append((0, 0, {
            'display_type': 'line_section',
            'wizard_id': wizard.id,
            'name': wizard.product_template_id.name if wizard.product_template_id else "Section",
            'product_variant_section': False,
            'product_qty': 0,
        }))

        total_qty = sum(qty.product_qty for qty in wizard.product_variant_line)

        for qty in wizard.product_variant_line:
            if qty.product_qty > 0:
                price_unit = qty.product_variant.lst_price
                total = price_unit * qty.product_qty
                grand_total += total
                new_lines.append((0, 0, {
                    'product_variant_section': qty.product_variant.id,
                    'name': qty.product_variant.display_name,
                    'product_template_id': wizard.product_template_id.id,
                    'product_qty': qty.product_qty,
                    'price_unit': price_unit,
                    'total': total
                }))

        # Add products to process (Printing and Delivery)
        products_to_process = wizard.printing_product_ids | wizard.delivery_product_ids
        for product in products_to_process:
            price_unit = product.lst_price
            product_qty = total_qty if product in wizard.printing_product_ids else 1
            total = price_unit * product_qty
            grand_total += total
            new_lines.append((0, 0, {
                'product_variant_section': product.id,
                'name': product.display_name,
                'product_template_id': product.product_tmpl_id.id,
                'price_unit': price_unit,
                'product_qty': total_qty if product in wizard.printing_product_ids else 1,
                'total': total
            }))
        return new_lines, grand_total