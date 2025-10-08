# -*- coding: utf-8 -*-
# Part of AppJetty. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools, Command
import json
import html


class ProductProduct(models.Model):
    _inherit = 'product.product'

    json_printing_data_varaint = fields.Json()
    json_shipping_data_varaint = fields.Json()
    printing_location_ids = fields.One2many('printing.locations', 'product_id', string='Printing Locations')
    printing_method_ids = fields.One2many('printing.methods', 'product_id', string='Printing Methods')
    printing_color_and_size_ids = fields.One2many('printing.colors.and.sizes', 'product_id', string='Printing Colors & Sizes')
    shipping_product_ids = fields.One2many('shipping.products', 'product_id', string='Shipping Lines')

    def _sanitize_price_string(self, price_str):
        symbols = ['$', '£', '€']
        for symbol in symbols:
            if isinstance(price_str, str):
                price_str = price_str.replace(symbol, '').strip()
        return price_str

    def _create_printing_data_from_json(self):
        self._create_shipping_template_ids()
        printing_locations = self.env["printing.locations"]
        printing_methods = self.env["printing.methods"]
        printing_colors_and_sizes = self.env["printing.colors.and.sizes"]
        for product in self.filtered(lambda x: not (x.printing_location_ids and x.printing_color_and_size_ids)):

            printing_data = product.json_printing_data_varaint or ""
            try:
                parsed_data = json.loads(html.unescape(printing_data))
            except Exception:
                parsed_data = {}

            for pd in parsed_data.get("printData", []):
                # --- Location ---
                location_name = pd.get("location")
                location = None
                if location_name:
                    location = printing_locations.search([
                        ("product_id", "=", product.id),
                        ("name", "=", location_name),
                    ], limit=1)
                    if not location:
                        location = printing_locations.create({
                            "product_id": product.id,
                            "name": location_name,
                        })

                # --- Method ---
                method_name = pd.get("method")
                method = None
                if method_name:
                    method = printing_methods.search([
                        ("product_id", "=", product.id),
                        ("name", "=", method_name),
                        ("location_id", "=", location.id if location else False),
                    ], limit=1)
                    if not method:
                        method = printing_methods.create({
                            "product_id": product.id,
                            "name": method_name,
                            "location_id": location.id if location else False,
                        })
                        if location:
                            location.write({"method_ids": [Command.link(method.id)]})

                # Method-level setup charges (default)
                setup_charges = pd.get("setupCharges", [])
                setup_charge_value = setup_charges[0].get("value", 0.0) if setup_charges else 0.0

                # --- Pricing (Colors) ---
                for cp in pd.get("pricing", {}).get("colorPricing", []):
                    num_colours = cp.get("numColours")

                    cp_setup_charges = cp.get("setupCharges", [])
                    cp_setup_value = cp_setup_charges[0].get("value", setup_charge_value) if cp_setup_charges else setup_charge_value

                    color = printing_colors_and_sizes.search([
                        ("product_id", "=", product.id),
                        ("printing_type", "=", "color"),
                        ("color_name", "=", str(num_colours)),
                        ("location_id", "=", location.id if location else False),
                        ("color_method_id", "=", method.id if method else False),
                    ], limit=1)

                    if not color:
                        color = printing_colors_and_sizes.create({
                            "product_id": product.id,
                            "printing_type": "color",
                            "color_name": str(num_colours),
                            "location_id": location.id if location else False,
                            "color_method_id": method.id if method else False,
                            "setup_charge": cp_setup_value,
                        })

                    # Collect all tiers first
                    qty_price_vals = []
                    for tier in cp.get("tiers", []):
                        qty_from = float(tier.get("colorQuantityFrom") or 1.0)
                        price = self._sanitize_price_string(tier.get("grossPrice", "0"))
                        qty_price_vals.append({
                            "colors_and_sizes_id": color.id,
                            "quantity": qty_from,
                            "price": price,
                        })

                    if qty_price_vals:
                        self.env["printing.qty.price"].create(qty_price_vals)

                    if method:
                        method.write({"color_ids": [Command.link(color.id)]})

                # --- Pricing (Sizes/Areas) ---
                for sp in pd.get("pricing", {}).get("sizePricing", []):
                    size_val = sp.get("size", {}).get("value")

                    sp_setup_charges = sp.get("setupCharges", [])
                    sp_setup_value = sp_setup_charges[0].get("value", setup_charge_value) if sp_setup_charges else setup_charge_value

                    size = printing_colors_and_sizes.search([
                        ("product_id", "=", product.id),
                        ("printing_type", "=", "size"),
                        ("size_name", "=", str(size_val)),
                        ("location_id", "=", location.id if location else False),
                        ("size_method_id", "=", method.id if method else False),
                    ], limit=1)

                    if not size:
                        size = printing_colors_and_sizes.create({
                            "product_id": product.id,
                            "printing_type": "size",
                            "size_name": str(size_val),
                            "location_id": location.id if location else False,
                            "size_method_id": method.id if method else False,
                            "setup_charge": sp_setup_value,
                        })

                    # Collect all tiers first
                    qty_price_vals = []
                    for tier in sp.get("tiers", []):
                        qty_from = float(tier.get("sizeQuantityFrom") or 1.0)
                        price = self._sanitize_price_string(tier.get("grossPrice", "0"))
                        qty_price_vals.append({
                            "colors_and_sizes_id": size.id,
                            "quantity": qty_from,
                            "price": price,
                        })

                    if qty_price_vals:
                        self.env["printing.qty.price"].create(qty_price_vals)

                    if method:
                        method.write({"size_ids": [Command.link(size.id)]})

    def _create_shipping_template_ids(self):
        for product in self.filtered(lambda x: not x.shipping_product_ids):
            printing_data = product.json_shipping_data_varaint or ""
            try:
                parsed_data = json.loads(html.unescape(printing_data))
            except Exception:
                parsed_data = {}

            carrier_name = parsed_data.get("carrier", {})
            if carrier_name:
                for tc in parsed_data.get("tierCharges", []):
                    tier_type = tc.get("type", {})
                    qty_range = tc.get("qty", "1-1")
                    try:
                        qty_max = int(qty_range.split("-")[-1])  # only take max
                    except Exception:
                        qty_max = 1

                    price = self._sanitize_price_string(tc.get("price", "0"))

                    # Product template name = Carrier - Type
                    shipping_name = f"{carrier_name} - {tier_type}" if tier_type else carrier_name

                    # Check if shipping product already exists
                    is_shipping_name_exist = product.shipping_product_ids.filtered(lambda x: x.name == shipping_name)

                    if not is_shipping_name_exist:
                        shipping_id = self.env["shipping.products"].create({
                            "name": shipping_name,
                            "product_id": product.id,
                        })

                        # Create new qty/price line
                        self.env["printing.qty.price"].create({
                            "shipping_id": shipping_id.id,
                            "quantity": qty_max,
                            "price": price,
                        })

    def clear_printing_json_data(self):
        for product in self:
            product.printing_location_ids = False
            product.printing_method_ids = False
            product.printing_color_and_size_ids = False

    def clear_shipping_json_data(self):
        for product in self:
            product.shipping_product_ids =  False


class PrintingLocations(models.Model):
    _name = 'printing.locations'
    _description = "Printing Locations"
    _rec_name = 'name'

    product_id = fields.Many2one('product.product')
    name = fields.Char('Printing Location', translate=True)
    method_ids = fields.Many2many('printing.methods')


class PrintingMethods(models.Model):
    _name = 'printing.methods'
    _description = "Printing Methods"
    _rec_name = 'name'

    product_id = fields.Many2one('product.product')
    location_id = fields.Many2one('printing.locations')
    name = fields.Char('Printing Method', translate=True)
    color_ids = fields.One2many('printing.colors.and.sizes', 'color_method_id', string='Printing Colors')
    size_ids = fields.One2many('printing.colors.and.sizes', 'size_method_id', string='Printing Sizes')


class PrintingColorsAndSizes(models.Model):
    _name = 'printing.colors.and.sizes'
    _description = "Printing Colors And Sizes"
    _rec_name = 'name'

    name = fields.Char("Display Name", compute="_compute_name", store=True)
    product_id = fields.Many2one('product.product')
    printing_type = fields.Selection([('color', 'Color'), ('size', 'Size'), ('both', 'Both')])
    color_name = fields.Char(translate=True)
    size_name = fields.Char(translate=True)
    location_id = fields.Many2one('printing.locations')
    color_method_id = fields.Many2one('printing.methods')
    size_method_id = fields.Many2one('printing.methods')
    vendor_currency_id = fields.Many2one('res.currency', related='product_id.pim_config_id.currency_id')
    setup_charge = fields.Float()
    repeat_charge = fields.Float()
    extra_charge = fields.Float()
    qty_price_ids = fields.One2many('printing.qty.price', 'colors_and_sizes_id', string='Quantity & Price Lines')

    @api.depends('color_name', 'size_name')
    def _compute_name(self):
        for rec in self:
            if rec.color_name and rec.size_name:
                rec.name = f"{rec.color_name} / {rec.size_name}"
            elif rec.color_name:
                rec.name = rec.color_name
            elif rec.size_name:
                rec.name = rec.size_name
            else:
                rec.name = "N/A"


class PrintingQtyPrice(models.Model):
    _name = 'printing.qty.price'
    _description = 'Printing Quantity and Price'
    _rec_name = 'price'

    colors_and_sizes_id = fields.Many2one('printing.colors.and.sizes', string='Parent', ondelete='cascade')
    shipping_id = fields.Many2one('shipping.products', string='Shipping Product', ondelete='cascade')
    quantity = fields.Float()
    price = fields.Float()


class ShippingProducts(models.Model):
    _name = 'shipping.products'
    _description = 'Shipping Products'
    _rec_name = 'name'

    product_id = fields.Many2one('product.product')
    name = fields.Char('Shipping Name', translate=True)
    qty_price_ids = fields.One2many('printing.qty.price', 'shipping_id', string='Quantity & Price Lines')
