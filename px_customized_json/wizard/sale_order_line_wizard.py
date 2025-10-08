# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _, Command
from odoo.exceptions import UserError
from datetime import datetime


class SaleLinePropertiesWiz(models.TransientModel):
    _inherit = 'sale.line.properties.wiz'

    raw_product_line_ids = fields.One2many('raw.product.variant.line', 'wizard_id', string='Raw Product Variant lines')
    raw_product_variant_ids = fields.Many2many('product.product','raw_product_rel','raw_id','product_id', compute='_compute_raw_product_variant_ids', string="Selected Raw Product Variants")
    product_id = fields.Many2one('product.product', domain="[('id', 'in', raw_product_variant_ids)]")
    is_product_has_config_id = fields.Boolean('Is product has config',  compute='_compute_is_product_has_config_id', store=True)
    is_printing_data_missing = fields.Boolean(string='Prinitng Data Missing', compute="_compute_is_printing_data_missing")
    is_shipping_data_missing = fields.Boolean(string='Shipping Data Missing', compute="_compute_is_shipping_data_missing")
    selection_line_ids = fields.One2many('printing.selection.line', 'wizard_id', string="Selections")
    printing_location_id = fields.Many2one('printing.locations', domain="[('id', 'in', allowed_printing_location_ids)]", string='Printing Location')
    printing_method_id = fields.Many2one('printing.methods',  domain="[('id', 'in', allowed_printing_method_ids)]", string='Printing Method')
    printing_color_and_size_id = fields.Many2one('printing.colors.and.sizes', domain="[('id', 'in', printing_allowed_color_size_ids)]", string='Printing Colors & Sizes')
    shipping_id = fields.Many2one('shipping.products', domain="[('product_template_id', '=', product_template_id)]", string='Shipping products')
    setup_charge_product_lines = fields.One2many('setup.charges.product.line', 'wizard_id', string="Setup Charges Product Lines")
    printing_allowed_color_size_ids = fields.Many2many('printing.colors.and.sizes', compute='_compute_allowed_color_size_ids')
    allowed_printing_location_ids = fields.Many2many('printing.locations', compute='_compute_allowed_printing_locations', string='Allowed Locations')
    allowed_printing_method_ids = fields.Many2many('printing.methods', compute='_compute_allowed_printing_methods', string='Allowed Methods')

    @api.depends('printing_method_id')
    def _compute_allowed_color_size_ids(self):
        for rec in self:
            rec.printing_allowed_color_size_ids = False
            if rec.printing_method_id:
                rec.printing_allowed_color_size_ids = self.env['printing.colors.and.sizes'].search([
                    '|',
                    ('color_method_id', '=', rec.printing_method_id.id),
                    ('size_method_id', '=', rec.printing_method_id.id)
                ])

    @api.depends('product_id')
    def _compute_allowed_printing_locations(self):
        for rec in self:
            rec.allowed_printing_location_ids = False
            if rec.product_id:
                rec.allowed_printing_location_ids = self.env['printing.locations'].search([
                    ('product_id', '=', rec.product_id.id)
                ])

    @api.depends('printing_location_id')
    def _compute_allowed_printing_methods(self):
        for rec in self:
            rec.allowed_printing_method_ids = False
            if rec.printing_location_id:
                rec.allowed_printing_method_ids = self.env['printing.methods'].search([
                    ('location_id', '=', rec.printing_location_id.id)
                ])

    @api.depends('product_id')
    def _compute_is_printing_data_missing(self):
        for wiz in self:
            if wiz.is_product_has_config_id:
                wiz.is_printing_data_missing = not (
                    wiz.product_id.printing_location_ids
                    and wiz.product_id.printing_method_ids
                    and wiz.product_id.printing_color_and_size_ids
                )
            else:
                wiz.is_printing_data_missing = False

    @api.depends('product_id')
    def _compute_is_shipping_data_missing(self):
        for wiz in self:
            wiz.is_shipping_data_missing = False
            if wiz.is_product_has_config_id and wiz.product_id:
                variants = wiz.product_template_id.product_variant_ids
                has_shipping_data = any(variant.shipping_product_ids for variant in variants)
                wiz.is_shipping_data_missing = not has_shipping_data

    @api.depends('product_template_id', 'product_template_id.supplier_id')
    def _compute_is_product_has_config_id(self):
        for rec in self:
            rec.is_product_has_config_id = bool(rec.product_template_id.supplier_id)

    @api.depends('raw_product_line_ids', 'raw_product_line_ids.product_id')
    def _compute_raw_product_variant_ids(self):
        for rec in self:
            rec.raw_product_variant_ids = rec.raw_product_line_ids.product_id.ids

    @api.onchange('product_template_id')
    def _onchange_product_template_id(self):
        for rec in self:
            if rec.product_template_id and rec.product_template_id.supplier_id and len(rec.product_template_id.product_variant_ids) == 1:
                rec.product_id = rec.product_template_id.product_variant_id.id
            else:
                rec.product_id = rec.raw_product_line_ids[0].product_id.id if rec.raw_product_line_ids else False

    @api.onchange('printing_location_id')
    def _onchange_printing_location_id(self):
        for rec in self:
            rec.printing_method_id = False
            rec.printing_color_and_size_id = False

    @api.onchange('printing_method_id')
    def _onchange_printing_method_id(self):
        for rec in self:
            rec.printing_color_and_size_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            rec.printing_location_id = False
            rec.printing_method_id = False
            rec.printing_color_and_size_id = False
            if rec.product_id:
                rec.product_id._create_printing_data_from_json()

    @api.model
    def default_get(self, fields):
        """Set default values for the wizard based on context."""
        res = super(SaleLinePropertiesWiz, self).default_get(fields)

        product_template_id = self.env.context.get('default_product_tmpl_id')
        if product_template_id:
            res['product_template_id'] = product_template_id
            product_templ_id = self.env['product.template'].browse(product_template_id)
            if product_templ_id and product_templ_id.supplier_id:
                product_quantities = self.env.context.get('product_quantities')
                lines = []
                if product_quantities:
                    for product_id_str, qty in product_quantities.items():
                        try:
                            product_id = int(product_id_str)
                        except ValueError:
                            continue 
                        lines.append(Command.create({
                            'product_id': product_id,
                            'qty': qty,
                        }))
                elif product_templ_id.product_variant_ids and len(product_templ_id.product_variant_ids) == 1:
                    lines.append(Command.create({
                            'product_id': product_templ_id.product_variant_id.id,
                            'qty': 1.0,
                        }))
                res['raw_product_line_ids'] = lines
                return res
        return res

    def action_add_selection(self):
        """Button to add current selection to One2many lines"""
        self.ensure_one()
        if not (self.printing_location_id and self.printing_method_id):
            raise UserError("Please select at least Location and Method")

        # Duplication check
        for l in self.selection_line_ids:
            if (
                l.printing_location_id == self.printing_location_id
                and l.printing_method_id == self.printing_method_id
                and l.printing_color_and_size_id == self.printing_color_and_size_id
            ):
                raise UserError("This combination already exists!")

        self.env['printing.selection.line'].create({
            'wizard_id': self.id,
            'product_id': self.product_id.id,
            'printing_location_id': self.printing_location_id.id,
            'printing_method_id': self.printing_method_id.id,
            'printing_color_and_size_id': self.printing_color_and_size_id.id if self.printing_color_and_size_id else False,
        })

        setup_charge_value = self.printing_color_and_size_id.setup_charge if self.printing_color_and_size_id else self.product_template_id.supplier_id.printing_product_id.standard_price
        # Check if product already exists in setup_charge_product_lines
        existing_line = self.setup_charge_product_lines.filtered(lambda l: l.product_id == self.product_id)
        if existing_line:
            existing_line.setup_charge += setup_charge_value
        else:
            self.env['setup.charges.product.line'].create({
                'wizard_id': self.id,
                'product_id': self.product_id.id,
                'setup_charge': setup_charge_value,
            })

        # Reset after adding (optional)
        self.printing_location_id = False
        self.printing_method_id = False
        self.printing_color_and_size_id = False

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",  # ensures it stays popup
        }

    def _calculate_purchase_price(self, selection_line, qty):
        # Added by Radhika: Calculate purchase price for printing products using tier-based pricing
        pim_config = self.product_template_id.supplier_id
        tiers = selection_line.printing_color_and_size_id and selection_line.printing_color_and_size_id.qty_price_ids or False
        return self.env['sale.order.line']._get_converted_tier_price(
            tiers,
            qty,
            self.sale_order_id,
            pim_config,
        )

    def _calculate_delivery_purchase_price(self):
        """Calculate purchase price for delivery product using shipping_id.qty_price_ids"""
        # Added by Radhika: Delivery product tier-based pricing similar to printing products
        if not self.shipping_id:
            return 0.0
        pim_config = self.product_template_id.supplier_id
        tiers = self.shipping_id.qty_price_ids
        qty = 1
        return self.env['sale.order.line']._get_converted_tier_price(
            tiers,
            qty,
            self.sale_order_id,
            pim_config,
        )


    def add_printing_product_from_json(self):
        sale_order = self.sale_order_id

        is_product_has_single_variant = bool(self.product_template_id and len(self.product_template_id.product_variant_ids) == 1)
        raw_line = self.env['sale.order.line']

        # Find the last sequence number in the order
        last_existing_line = self.env['sale.order.line'].search(
            [('order_id', '=', sale_order.id)], order='sequence desc', limit=1
        )
        seq = last_existing_line.sequence if last_existing_line else 10

        # Demo printing product (from XML)
        printing_product = self.product_template_id.supplier_id.printing_product_id
        setup_charge_product = self.product_template_id.supplier_id.setup_product_id
        sale_order_line = self.env['sale.order.line']
        created_lines = self.env['sale.order.line']
        all_created_lines = self.env['sale.order.line']

        seq += 1
        sale_order_line.create({
            'display_type': 'line_section',
            'order_id': sale_order.id,
            'name': self.product_template_id.name,
            'sequence': seq,
            'show_cpq': True,
        })

        for raw_product_line in self.raw_product_line_ids.filtered(lambda x: x.product_id.id in self.selection_line_ids.product_id.ids):
            seq += 1
            extra_margin = raw_product_line.product_id.supplier_id.extra_margin or 0.0
            if not is_product_has_single_variant and raw_product_line.product_id.product_tmpl_id.product_add_mode == 'matrix':
                raw_line = sale_order_line.create({
                    'order_id': sale_order.id,
                    'product_id': raw_product_line.product_id.id,
                    'name': raw_product_line.product_id.name,
                    'product_template_id': raw_product_line.product_id.product_tmpl_id.id,
                    'product_uom_qty': raw_product_line.qty,
                    'sequence': seq,
                    'is_product_added_from_json': True,
                    'show_cpq': True,
                })

            # Loop through selections
            for sl in self.selection_line_ids.filtered(lambda x: x.product_id.id == raw_product_line.product_id.id):
                qty = raw_product_line.qty
                purchase_price = self._calculate_purchase_price(sl, qty)

                # Always add printing product line (for this selection)
                desc_parts = []
                desc_parts.append(f"{raw_product_line.product_id.display_name}")
                if sl.printing_location_id:
                    desc_parts.append(f"Location: {sl.printing_location_id.name}")
                if sl.printing_method_id:
                    desc_parts.append(f"Method: {sl.printing_method_id.name}")
                if sl.printing_color_and_size_id and sl.printing_color_and_size_id.color_name:
                    desc_parts.append(f"Color: {sl.printing_color_and_size_id.color_name}")
                if sl.printing_color_and_size_id and sl.printing_color_and_size_id.size_name:
                    desc_parts.append(f"Size: {sl.printing_color_and_size_id.size_name}")

                printing_description = "\n".join(desc_parts) if desc_parts else "Printing Service"

                seq += 1
                printing_line = sale_order_line.create({
                    'order_id': sale_order.id,
                    'product_id': printing_product.id,
                    'name': printing_description,
                    'product_uom_qty': qty,
                    'price_unit': printing_product.list_price,
                    'sequence': seq,
                    'parent_sale_line_id': raw_line.id,
                    'is_product_added_from_json': not is_product_has_single_variant,
                    'show_cpq': True,
                    'purchase_price': purchase_price,
                    'printing_line_id': sl.printing_color_and_size_id.id,
                })
                all_created_lines |= printing_line

            setup_charge_product_lines =  self.setup_charge_product_lines.filtered(lambda x: x.product_id.id == raw_product_line.product_id.id)
            setup_charge =  setup_charge_product_lines.setup_charge if setup_charge_product_lines else 0.0
            sale_price = setup_charge * (1 + extra_margin / 100.0)

            if setup_charge_product_lines:
                seq += 1
                sale_line_id = sale_order_line.create({
                        'order_id': sale_order.id,
                        'product_id': setup_charge_product.id,
                        'name': raw_product_line.product_id.display_name,
                        'product_uom_qty': 1,
                        'purchase_price': setup_charge,
                        'sequence': seq,
                        'parent_sale_line_id': raw_line.id,
                        'is_product_added_from_json': not is_product_has_single_variant,
                        'show_cpq': True,
                    })
                sale_line_id.price_unit = sale_price
                all_created_lines |= sale_line_id

        for raw_product_line in self.raw_product_line_ids.filtered(lambda x: x.product_id.id not in self.selection_line_ids.product_id.ids):
            seq += 1
            if not is_product_has_single_variant and raw_product_line.product_id.product_tmpl_id.product_add_mode == 'matrix':
                sale_order_line.create({
                    'order_id': sale_order.id,
                    'product_id': raw_product_line.product_id.id,
                    'name': raw_product_line.product_id.name,
                    'product_template_id': raw_product_line.product_id.product_tmpl_id.id,
                    'product_uom_qty': raw_product_line.qty,
                    'sequence': seq,
                    'is_product_added_from_json': not is_product_has_single_variant,
                    'show_cpq': True,
                    'price_unit': purchase_price,
                    'purchase_price': purchase_price,
                })
                all_created_lines |= extra_raw_line

        # Trigger price computation for all created lines to ensure purchase_price is calculated
        if all_created_lines:
            all_created_lines.with_context(force_price_recomputation=True)._compute_price_unit()

        delivery_product = self.product_template_id.supplier_id.shpping_product_id

        if delivery_product and not self.is_shipping_data_missing:
            seq += 1
            # Calculate purchase price for delivery product using qty_price_ids
            delivery_purchase_price = self._calculate_delivery_purchase_price()
            delivery_line = sale_order_line.create({
                'order_id': sale_order.id,
                'product_id': delivery_product.id,
                'name': f"{self.product_template_id.name}\n{self.shipping_id.name or ''}",
                'product_uom_qty': 1,
                'price_unit': delivery_product.list_price,
                'sequence': seq,
                'delivery_line_id': self.shipping_id.id,
                'is_product_added_from_json': not is_product_has_single_variant,
                'show_cpq': True,
                'purchase_price': delivery_purchase_price,
            })
            delivery_line.with_context(force_price_recomputation=True)._compute_price_unit()
            all_created_lines |= delivery_line

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'context': {'view_type': 'form'},
            'view_mode': 'form',
        }


class PrintingSelectionLine(models.TransientModel):
    _name = 'printing.selection.line'
    _description = 'Selected Printing Combination (wizard line)'

    wizard_id = fields.Many2one('sale.line.properties.wiz', ondelete='cascade')
    product_id = fields.Many2one('product.product')
    printing_location_id = fields.Many2one('printing.locations', string='Printing Location')
    printing_method_id = fields.Many2one('printing.methods', string='Printing Method')
    printing_color_and_size_id = fields.Many2one('printing.colors.and.sizes', string='Printing Colors & Sizes')


class RawProductVariantLine(models.TransientModel):
    _name = 'raw.product.variant.line'
    _description = 'Raw Product Variant Line'

    wizard_id = fields.Many2one('sale.line.properties.wiz', ondelete='cascade')
    product_id = fields.Many2one('product.product')
    qty = fields.Float()


class SetupChargeProductLine(models.TransientModel):
    _name = 'setup.charges.product.line'
    _description = 'Setup Charges Product Lines'

    wizard_id = fields.Many2one('sale.line.properties.wiz', ondelete='cascade')
    product_id = fields.Many2one('product.product')
    setup_charge = fields.Float()
    repeat_charge = fields.Float()
    extra_charge = fields.Float()
