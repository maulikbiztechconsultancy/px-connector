# Copyright 2013-2020 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import logging
import random
import json
import requests
import base64
import html
import ast
from datetime import datetime, timedelta
from itertools import product
from odoo.exceptions import UserError
from odoo import _, api, exceptions, fields, models, _
from odoo.osv import expression
from odoo.tools import config, html_escape
from odoo import Command

from odoo.addons.base_sparse_field.models.fields import Serialized

_logger = logging.getLogger(__name__)

PRICELISTS = None
PRODUCTS = None
PRODUCTATTRIBUTEVALUE = None
SALEPRICCELISTITEAMS = None
VENDORPRICCELISTITEAMS = None
PRODUCTLOCATIONSTOCK = None
PRODUCT_ATTRIBUTE_LINES = None


class VendorQueueJob(models.Model):
    _name = "vendor.queue.job"

    name = fields.Char(string="Description")
    method_name = fields.Char(string="Method Name", readonly=True, compute='_compute_method_name_config', store=True)  # Temp
    category_method_name = fields.Char(string="Method Name", readonly=True, compute='_compute_method_name_config',
                                       store=True)  # Temp
    queue_job_lines = fields.One2many('queue.job', 'vendor_job_id')
    pim_config_id = fields.Many2one('pimore.vender.config', compute='_compute_method_name_config', store=True)

    @api.depends('name')
    def _compute_method_name_config(self):
        for rec in self:
            rec.method_name = f'{rec.name}_product_import_data'
            rec.category_method_name = f'{rec.name}_category_import_data'
            rec.pim_config_id = self.env['pimore.vender.config'].search([('vendor_queue_job_id', '=', rec.id)], limit=1).id

    def import_category_job_datas(self):
        if hasattr(self.queue_job_lines, f'{self.category_method_name}'):
            getattr(self.queue_job_lines.filtered(
                lambda rec: rec.model_id.model == 'product.category' and rec.state == 'process'),
                f'{self.category_method_name}')()
        else:
            raise UserError(_(f'Method not found in the System for vendor {self.name.upper()}'))

    def import_product_job_datas(self):
        global PRICELISTS, PRODUCTS, PRODUCTATTRIBUTEVALUE, SALEPRICCELISTITEAMS, VENDORPRICCELISTITEAMS, PRODUCTLOCATIONSTOCK, PRODUCT_ATTRIBUTE_LINES

        PRICELISTS = self.env['product.pricelist'].sudo().search([],order='id')
        PRODUCTS = self.env['product.template'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])
        PRODUCTATTRIBUTEVALUE = self.env['product.attribute.value'].sudo().search([])
        SALEPRICCELISTITEAMS = self.env['product.pricelist.item'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])
        VENDORPRICCELISTITEAMS = self.env['product.supplierinfo'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])
        PRODUCTLOCATIONSTOCK =  self.env['product.location.stock'].sudo().search([])
        PRODUCT_ATTRIBUTE_LINES = self.env['product.template.attribute.line'].sudo().search([])

        if hasattr(self.queue_job_lines, f'{self.method_name}'):
            getattr(self.queue_job_lines.filtered(
                lambda rec: rec.model_id.model == 'product.template' and rec.state == 'process'),
                f'{self.method_name}')()
        else:
            raise UserError(_(f'Method not found in the System for vendor {self.name.upper()}'))


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""

    _name = "queue.job"
    _description = "Queue Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = 'reference'

    name = fields.Char(string="Description", readonly=True)
    user_id = fields.Many2one(comodel_name="res.users", string="User ID")
    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", index=True
    )
    vendor_job_id = fields.Many2one('vendor.queue.job')

    model_id = fields.Many2one('ir.model', string="Model", readonly=True)
    dependencies = Serialized(readonly=True)

    records = fields.Integer()
    priority = fields.Integer()
    result = fields.Json()
    result_text = fields.Text()
    error_reason = fields.Json()
    error_reason_text = fields.Text()

    reference = fields.Char('Reference', readonly=True)
    sub_reference = fields.Char('Sub Reference', readonly=True)

    date_created = fields.Datetime(string="Created Date", readonly=True)
    date_started = fields.Datetime(string="Start Date", readonly=True)
    date_enqueued = fields.Datetime(string="Enqueue Time", readonly=True)
    date_done = fields.Datetime(readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('process', 'Process'),
         ('done', 'Done'),
         ('cancelled', 'Cancelled'),
         ('fail', 'Fail'),
         ], string='State', default='draft')

    def action_draft(self):
        for queue in self:
            queue.state = 'draft'

    def action_cancel(self):
        for queue in self:
            queue.state = 'cancelled'

    def set_display_name(self):
        for queue in self:
            if queue.reference:
                queue.display_name = queue.name + ' [ ' + queue.reference + ' ]'
            else:
                queue.display_name = queue.name

    def _get_currency_convert_amount(self, currency, amount, to_currency):
        return currency._convert(
            amount,
            to_currency,
            self.env.company,
            fields.Date.context_today(self),
        )

    def _sanitize_price_string(self, price_str):
        symbols = ['$', '£', '€']
        for symbol in symbols:
            if isinstance(price_str, str):
                price_str = price_str.replace(symbol, '').strip()
        return price_str

    def _get_or_create_pricelist(self, currency_id, vendor_name):
        global PRICELISTS
        pricelist = next((price for price in PRICELISTS if price.currency_id.id == currency_id), self.env['product.pricelist'])
        if not pricelist:
            pricelist = PRICELISTS.create({
                'name': f'{vendor_name} Pricelist',
                'currency_id': currency_id,
            })
            PRICELISTS |= pricelist
        return pricelist

    def process_print_product(self, result, raw_product_variants, pim_config_id, print_details):
        global PRODUCTS, PRODUCTATTRIBUTEVALUE, PRICELISTS, SALEPRICCELISTITEAMS, VENDORPRICCELISTITEAMS

        vendor_name = pim_config_id.partner_id.name if pim_config_id.partner_id else ''
        currency = pim_config_id.currency_id
        to_currency = pim_config_id.converted_currency_id
        sale_margin = pim_config_id.sale_margin or 0.0
        is_sales = pim_config_id.create_pricelist in ('sales', 'both')
        is_vendor = pim_config_id.create_pricelist in ('vendor', 'both')
        partner_id = pim_config_id.partner_id.id

        printing_attribute_lines = pim_config_id.printing_product_attribute_lines.filtered(
            lambda x: x.stop_variant_creation)
        if printing_attribute_lines:
            printing_attribute_lines.attribute_id.create_variant = 'no_variant'

        # Batch collect product information: use (product_name, print_code) key
        product_infos = {}
        for print_detail in print_details:
            if print_detail.get(pim_config_id.price_list_data):
                printing_product_data = json.loads(html.unescape(print_detail.get(pim_config_id.price_list_data, '')))
                print_code = print_detail.get('printCode', '').strip()
                product_name = printing_product_data.get(pim_config_id.printing_product_name,
                                                         '').strip() + ' BY ' + vendor_name
                product_infos.setdefault((product_name, print_code), []).append(print_detail)

        # Find existing products using (name, model_code)
        product_keys = list(product_infos.keys())
        existing_products = {
            (p.name.strip(), (p.model_code or '').strip()): p
            for p in PRODUCTS
            if (p.name.strip(), (p.model_code or '').strip()) in product_keys
        }

        # Identify missing products and search
        missing_keys = [key for key in product_keys if key not in existing_products]
        if missing_keys:
            domain = ['|'] * (len(missing_keys) - 1)
            for name, code in missing_keys:
                domain += ['&', ('name', '=', name), ('model_code', '=', code)]
            db_products = self.env['product.template'].search(domain)
            for product in db_products:
                key = (product.name.strip(), (product.model_code or '').strip())
                existing_products[key] = product
                PRODUCTS |= product

        # Get/create pricelist
        pricelist = next((p for p in PRICELISTS if p.currency_id.id == to_currency.id), self.env['product.pricelist'])
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': f'{vendor_name} Pricelist',
                'currency_id': to_currency.id
            })
            PRICELISTS |= pricelist

        attribute_value_cache = {}
        all_variants_to_process = []
        all_variant_ids = []
        product_to_variants = {}
        all_product_ids = self.env['product.template']

        for (product_name, print_code), details in product_infos.items():
            attribute_map = {}

            for print_detail in details:
                if print_detail.get(pim_config_id.price_list_data):
                    printing_product_data = json.loads(html.unescape(print_detail.get(pim_config_id.price_list_data, '')))
                    price_dependence = printing_product_data.get('PriceDependence', '')
                    logo_datas = printing_product_data.get('LogoSize', [])

                    for logo_data in logo_datas:
                        for line in pim_config_id.printing_product_attribute_lines:
                            attr, custom_val = line.attribute_id, line.custom_value
                            if not attr or not custom_val:
                                continue
                            if ('LogoSizeCm2' in custom_val and price_dependence != 'Size') or (
                                    'AmountColorsId' in custom_val and price_dependence == 'Size'):
                                continue

                            if ',' in custom_val:
                                parts = [str(logo_data.get(k.strip(), '')).strip() for k in custom_val.split(',')]
                                raw_value = 'x'.join(parts) if all(parts) else None
                            else:
                                raw_value = str(logo_data.get(custom_val, '')).strip()

                            if not raw_value or raw_value == '0.0':
                                continue

                            key = (attr.id, raw_value)
                            if key not in attribute_value_cache:
                                val = next((v for v in PRODUCTATTRIBUTEVALUE if
                                            v.name == raw_value and v.attribute_id.id == attr.id),
                                           self.env['product.attribute.value'])
                                if not val:
                                    val = self.env['product.attribute.value'].create({
                                        'name': raw_value,
                                        'attribute_id': attr.id
                                    })
                                    PRODUCTATTRIBUTEVALUE |= val
                                attribute_value_cache[key] = val
                            attribute_map.setdefault(attr, set()).add(attribute_value_cache[key])

                    for line in pim_config_id.printing_product_attribute_lines:
                        attr, custom_val = line.attribute_id, line.custom_value
                        if not attr or not custom_val:
                            continue
                        if ('LogoSizeCm2' in custom_val and price_dependence != 'Size') or (
                                'AmountColorsId' in custom_val and price_dependence == 'Size'):
                            continue

                        if ',' in custom_val:
                            parts = [str(print_detail.get(k.strip(), '')).strip() for k in custom_val.split(',')]
                            raw_value = 'x'.join(parts) if all(parts) else None
                        else:
                            raw_value = str(print_detail.get(custom_val, '')).strip()

                        if not raw_value or raw_value == '0.0':
                            continue

                        key = (attr.id, raw_value)
                        if key not in attribute_value_cache:
                            val = next(
                                (v for v in PRODUCTATTRIBUTEVALUE if v.name == raw_value and v.attribute_id.id == attr.id),
                                self.env['product.attribute.value'])
                            if not val:
                                val = self.env['product.attribute.value'].create({
                                    'name': raw_value,
                                    'attribute_id': attr.id
                                })
                                PRODUCTATTRIBUTEVALUE |= val
                            attribute_value_cache[key] = val
                        attribute_map.setdefault(attr, set()).add(attribute_value_cache[key])

            product = existing_products.get((product_name.strip(), print_code.strip()))

            if product:
                attr_lines_by_attr = {l.attribute_id.id: l for l in product.attribute_line_ids}
                updates, creates = [], []

                for attr, vals in attribute_map.items():
                    val_ids = [v.id for v in vals]
                    if attr.id in attr_lines_by_attr:
                        line = attr_lines_by_attr[attr.id]
                        existing = set(line.value_ids.ids)
                        new_vals = list(existing.union(val_ids))
                        if existing != set(new_vals):
                            updates.append((line, new_vals))
                    else:
                        creates.append((attr.id, val_ids))

                for line, new_vals in updates:
                    line.write({'value_ids': [Command.set(new_vals)]})

                if creates:
                    product.write({
                        'attribute_line_ids': [
                            Command.create({'attribute_id': attr_id, 'value_ids': [Command.set(val_ids)]})
                            for attr_id, val_ids in creates
                        ]
                    })
            else:
                attribute_lines = [(attr, list(vals)) for attr, vals in attribute_map.items()]
                product = self.env['product.template'].create({
                    'name': product_name,
                    'type': 'service',
                    'product_service_type': 'printing',
                    'attribute_line_ids': [
                        Command.create({'attribute_id': attr.id, 'value_ids': [Command.set([v.id for v in vals])]})
                        for attr, vals in attribute_lines
                    ],
                    'pim_config_id': pim_config_id.id,
                    'model_code': print_code,
                })
                existing_products[(product_name.strip(), print_code.strip())] = product
                PRODUCTS |= product

            if raw_product_variants:
                raw_product_variants.write({'printing_template_ids': [Command.link(product.id)]})

            all_product_ids |= product
            all_deco_prices = []
            for print_detail in details:
                price_data = print_detail.get(pim_config_id.price_list_data, '')
                if price_data:
                    try:
                        data = json.loads(price_data)
                        for logo in data.get('LogoSize', []):
                            price_dependence = data.get('PriceDependence', '')
                            if (price_dependence == 'Size' and not logo.get('LogoSizeCm2')) or \
                                    (price_dependence != 'Size' and not logo.get('AmountColorsId')):
                                continue
                            all_deco_prices.append({
                                'AmountColorsId': logo.get('AmountColorsId'),
                                'LogoSizeCm2': logo.get('LogoSizeCm2'),
                                'SetupCharge': logo.get('SetupCharge'),
                                'PriceDependence': price_dependence,
                                'DecoPrice': logo.get('DecoPrice', [])
                            })
                    except (json.JSONDecodeError, AttributeError):
                        pass

            product_to_variants[product.id] = {
                'product': product,
                'deco_prices': all_deco_prices
            }

        # Second pass: Get all variants in one query and process prices in batch
        if all_product_ids:
            all_variants = all_product_ids.mapped('product_variant_ids')

            # Group variants by product template
            variants_by_template = {}
            for variant in all_variants:
                variants_by_template.setdefault(variant.product_tmpl_id.id, []).append(variant)
                variant.write({'pim_config_id': pim_config_id.id})
                all_variant_ids.append(variant.id)

            # Pre-fetch existing price list items in batch for faster lookup
            sales_items = SALEPRICCELISTITEAMS.filtered(
                lambda x: x.pricelist_id.id == pricelist.id and x.product_id.id in all_variant_ids
            )
            sales_map = {(i.product_id.id, i.min_quantity): i for i in sales_items}

            vendor_items = VENDORPRICCELISTITEAMS.filtered(
                lambda x: x.partner_id.id == partner_id and x.product_id.id in all_variant_ids
            )
            vendor_map = {}
            for item in vendor_items:
                vendor_map.setdefault(item.product_id.id, {})[item.min_qty] = item

            # Batch price updates
            sales_updates = []
            vendor_updates_by_product = {}

            # Process each product's variants with their deco prices
            for product_id, product_data in product_to_variants.items():
                variants = variants_by_template.get(product_id, [])
                if not variants:
                    continue

                product = product_data['product']
                deco_prices = product_data['deco_prices']

                # Pre-compute variant attribute maps for faster lookups
                variant_attrs = {}
                for variant in variants:
                    color_val = ''
                    size_val = ''
                    for attr_value in variant.product_template_attribute_value_ids:
                        if attr_value.attribute_id.name == 'color':
                            color_val = attr_value.product_attribute_value_id.name
                        elif attr_value.attribute_id.name == 'LogoSize':
                            size_val = attr_value.product_attribute_value_id.name
                    variant_attrs[variant.id] = (color_val, size_val)

                # Process each variant's prices
                for variant in variants:
                    color_val, size_val = variant_attrs[variant.id]

                    # Filter matching prices for this variant's attributes
                    matching_prices = []
                    for price in deco_prices:
                        dependence = price.get('PriceDependence')
                        amount_color_id = price.get('AmountColorsId')
                        logo_size = str(price.get('LogoSizeCm2')).strip()

                        if dependence != 'Size':
                            if color_val and color_val == amount_color_id:
                                matching_prices.append(price)
                        else:
                            if size_val and size_val == logo_size:

                                matching_prices.append(price)
                        if color_val == amount_color_id or size_val == logo_size:
                            variant.write({'setup_charge': price.get('SetupCharge')})

                    # Process matching prices
                    seen_sales = set()
                    seen_vendor = set()

                    for price_data in matching_prices:
                        for price_line in price_data.get('DecoPrice', []):
                            min_qty = float(price_line.get('DecoPriceFromQty') or 1.0)
                            raw_price = self._sanitize_price_string(price_line.get('Price', '0'))
                            base_price = float(
                                self._get_currency_convert_amount(currency, float(raw_price), to_currency)
                                if currency != to_currency else raw_price
                            )

                            # Process sales prices (once per quantity)
                            if is_sales and (variant.id, min_qty) not in seen_sales:
                                seen_sales.add((variant.id, min_qty))
                                item = sales_map.get((variant.id, min_qty))
                                sale_price = base_price * (1 + sale_margin / 100.0)

                                if item:
                                    if item.fixed_price != sale_price:
                                        sales_updates.append((1, item.id, {'fixed_price': sale_price, 'price': sale_price}))
                                else:
                                    sales_updates.append((0, 0, {
                                        'product_tmpl_id': variant.product_tmpl_id.id,
                                        'product_id': variant.id,
                                        'fixed_price': sale_price,
                                        'price': sale_price,
                                        'min_quantity': min_qty,
                                        'currency_id': to_currency.id,
                                        'pim_config_id': pim_config_id.id
                                    }))

                            # Process vendor prices (once per quantity)
                            if is_vendor and (variant.id, min_qty) not in seen_vendor:
                                seen_vendor.add((variant.id, min_qty))
                                vendor_map_for_variant = vendor_map.get(variant.id, {})
                                info = vendor_map_for_variant.get(min_qty)

                                vendor_updates = vendor_updates_by_product.setdefault(variant.id, [])

                                if info:
                                    if info.price != base_price:
                                        vendor_updates.append((1, info.id, {'price': base_price}))
                                else:
                                    vendor_updates.append((0, 0, {
                                        'partner_id': partner_id,
                                        'product_tmpl_id': variant.product_tmpl_id.id,
                                        'product_id': variant.id,
                                        'min_qty': min_qty,
                                        'price': base_price,
                                        'currency_id': to_currency.id,
                                        'pim_config_id': pim_config_id.id
                                    }))
            if sales_updates:
                pricelist.write({'item_ids': sales_updates})
                SALEPRICCELISTITEAMS |= pricelist.item_ids

            # Apply all vendor price updates in batch by product
            for variant_id, updates in vendor_updates_by_product.items():
                if updates:
                    variant = self.env['product.product'].browse(variant_id)
                    variant.write({'seller_ids': updates, 'service_to_purchase': True})
                    VENDORPRICCELISTITEAMS |= variant.seller_ids

    def _process_pricelist_row_product_data(self, product, pim_config_id, pricing_datas):
        global PRICELISTS, SALEPRICCELISTITEAMS, VENDORPRICCELISTITEAMS
        product_variant = product
        if not product_variant.exists():
            return
        currency = pim_config_id.currency_id
        to_currency = pim_config_id.converted_currency_id
        pricelist = 1
        seen_keys_sales = set()
        seen_keys_vendor = set()
        pricelist_items_to_create = []
        pricelist_items_to_update = []
        supplierinfo_to_create = []
        supplierinfo_to_update = []

        # Sales items
        if pim_config_id.create_pricelist in ('sales', 'both'):
            sales_items = SALEPRICCELISTITEAMS.filtered(lambda model: model.pricelist_id.id == pricelist.id and model.product_id.id == product_variant.id)
            SALEPRICCELISTITEAMS -= sales_items
            self.env.cr.execute("""
                DELETE FROM product_pricelist_item
                WHERE pricelist_id = %s AND product_id = %s
            """, (pricelist.id, product_variant.id))
            self.env.cr.commit()

        # Vendor items
        if pim_config_id.create_pricelist in ('vendor', 'both'):
            vendor_items = VENDORPRICCELISTITEAMS.filtered(lambda model: model.partner_id.id == pim_config_id.partner_id.id and model.product_id.id == product_variant.id)
            VENDORPRICCELISTITEAMS -= vendor_items
            self.env.cr.execute("""
                DELETE FROM product_supplierinfo
                WHERE partner_id = %s AND product_id = %s
            """, (pim_config_id.partner_id.id, product_variant.id))
            self.env.cr.commit()

        for pricing_data in pricing_datas:
            min_qty = float(pricing_data.get('priceBar') or 1.0)
            prices = pricing_data.get('nettPrice', '0')
            base_price = self._sanitize_price_string(prices)
            price_raw = base_price
            if currency != to_currency:
                price_raw = self._get_currency_convert_amount(currency,float(base_price),to_currency)
            try:
                base_price = float(price_raw or 0.0)
            except ValueError:
                base_price = 0.0

            # Sales mode
            if pim_config_id.create_pricelist in ('sales', 'both'):
                margin_percent = pim_config_id.sale_margin or 0.0
                price = base_price + (base_price * margin_percent / 100.0)
                key_sales = (product_variant.id, min_qty)
                if key_sales not in seen_keys_sales:
                    seen_keys_sales.add(key_sales)
                    pricelist_items_to_create.append((0, 0, {
                        'product_id': product_variant.id,
                        'fixed_price': price,
                        'pim_config_id': pim_config_id.id,
                        'price': price,
                        'min_quantity': min_qty,
                        'currency_id': pim_config_id.converted_currency_id.id,
                    }))

            # Vendor mode
            if pim_config_id.create_pricelist in ('vendor', 'both'):
                if min_qty not in seen_keys_vendor:
                    seen_keys_vendor.add(min_qty)
                    supplierinfo_to_create.append((0, 0, {
                        'partner_id': pim_config_id.partner_id.id,
                        'product_id': product_variant.id,
                        'pim_config_id': pim_config_id.id,
                        'min_qty': min_qty,
                        'price': base_price,
                        'currency_id': pim_config_id.converted_currency_id.id,
                    }))

        # Write updates
        if pricelist_items_to_update or pricelist_items_to_create:
            pricelist.write({'item_ids': pricelist_items_to_update + pricelist_items_to_create})
        if supplierinfo_to_update or supplierinfo_to_create:
            product_variant.write({'seller_ids': supplierinfo_to_update + supplierinfo_to_create})

    def _create_or_update_product_template_attribute_line(self, template_id, attribute_id, value_id, product_attribute_dict):
        global PRODUCT_ATTRIBUTE_LINES

        # [OPTIMIZED] Use global PRODUCT_ATTRIBUTE_LINES instead of search
        line = next(
            (l for l in PRODUCT_ATTRIBUTE_LINES
            if l.product_tmpl_id.id == template_id and l.attribute_id.id == attribute_id),
            self.env['product.template.attribute.line']
        )

        if line:
            if value_id not in line.value_ids.ids:  # Avoid duplicate write
                line.write({'value_ids': [(4, value_id)]})
            product_attribute_dict[template_id][attribute_id] = line.id
        else:
            new_line = self.env['product.template.attribute.line'].create({
                'product_tmpl_id': template_id,
                'attribute_id': attribute_id,
                'value_ids': [(6, 0, [value_id])]
            })
            PRODUCT_ATTRIBUTE_LINES |= new_line
            product_attribute_dict[template_id][attribute_id] = new_line.id

    def _update_stock_location(self, product_id, location, quantity):
        """Optimized method to update stock location"""
        global PRODUCTLOCATIONSTOCK
        ProductLocationStock = self.env['product.location.stock']

        # Find existing line efficiently using cached data
        existing_line = False
        for line in PRODUCTLOCATIONSTOCK:
            if line.product_id.id == product_id and line.location == location:
                existing_line = line
                break

        # Update or create as needed
        if existing_line:
            existing_line.quantity = quantity
        else:
            new_line = ProductLocationStock.sudo().create({
                'product_id': product_id,
                'location': location,
                'quantity': quantity,
            })
            PRODUCTLOCATIONSTOCK |= new_line

    def create_row_product_template(self, template_data):
        global PRODUCTS
        product_template_id = self.env['product.template'].create(template_data)
        PRODUCTS += product_template_id
        return product_template_id

    def _get_image_data(self, imagename):
        image_data = ''
        try:
            response = requests.get(imagename)
            if response.ok:
                image_data = base64.b64encode(response.content).decode('utf-8')
        except Exception as img_exc:
            _logger.warning("Image download failed for %s: %s", imagename, img_exc)
        return image_data

    def _process_pricelist_midocean_row_product_data(self, product, pim_config_id, pricing_datas):
        global PRICELISTS, SALEPRICCELISTITEAMS, VENDORPRICCELISTITEAMS
        product_variant = product
        if not product_variant.exists():
            return
        currency = pim_config_id.currency_id
        to_currency = pim_config_id.converted_currency_id
        pricelist = self._get_or_create_pricelist(to_currency.id, pim_config_id.partner_id.name)
        seen_keys_sales = set()
        seen_keys_vendor = set()
        pricelist_items_to_create = []
        supplierinfo_to_create = []

        # Sales items
        if pim_config_id.create_pricelist in ('sales', 'both'):
            # sales_items = SALEPRICCELISTITEAMS.filtered(lambda model: model.pricelist_id.id == pricelist.id and model.product_id.id == product_variant.id)
            # SALEPRICCELISTITEAMS -= sales_items
            self.env.cr.execute("""
                DELETE FROM product_pricelist_item
                WHERE pricelist_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pricelist.id, product_variant.id,pim_config_id.id))
            self.env.cr.commit()
            SALEPRICCELISTITEAMS = self.env['product.pricelist.item'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])

        # Vendor items
        if pim_config_id.create_pricelist in ('vendor', 'both'):
            # vendor_items = VENDORPRICCELISTITEAMS.filtered(lambda model: model.partner_id.id == pim_config_id.partner_id.id and model.product_id.id == product_variant.id)
            # VENDORPRICCELISTITEAMS -= vendor_items
            self.env.cr.execute("""
                DELETE FROM product_supplierinfo
                WHERE partner_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pim_config_id.partner_id.id, product_variant.id,pim_config_id.id))
            self.env.cr.commit()
            VENDORPRICCELISTITEAMS = self.env['product.supplierinfo'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])

        min_qty = 1
        prices = pricing_datas.get('mid_price', '0')
        if prices:
            prices = float(str(prices).replace(',', '.'))
        base_price = self._sanitize_price_string(prices)
        price_raw = base_price
        if currency != to_currency:
            price_raw = self._get_currency_convert_amount(currency, float(base_price), to_currency)
        try:
            base_price = float(price_raw or 0.0)
        except ValueError:
            base_price = 0.0

        # Sales mode
        if pim_config_id.create_pricelist in ('sales', 'both'):
            margin_percent = pim_config_id.sale_margin or 0.0
            price = base_price + (base_price * margin_percent / 100.0)
            key_sales = (product_variant.id, min_qty)
            if key_sales not in seen_keys_sales:
                seen_keys_sales.add(key_sales)
                pricelist_items_to_create.append((0, 0, {
                    'product_id': product_variant.id,
                    'fixed_price': price,
                    'pim_config_id': pim_config_id.id,
                    'price': price,
                    'min_quantity': min_qty,
                    'currency_id': pim_config_id.converted_currency_id.id,
                }))

        # Vendor mode
        if pim_config_id.create_pricelist in ('vendor', 'both'):
            if min_qty not in seen_keys_vendor:
                seen_keys_vendor.add(min_qty)
                supplierinfo_to_create.append((0, 0, {
                    'partner_id': pim_config_id.partner_id.id,
                    'product_id': product_variant.id,
                    'pim_config_id': pim_config_id.id,
                    'min_qty': min_qty,
                    'price': base_price,
                    'currency_id': pim_config_id.converted_currency_id.id,
                }))

        # Write updates
        if pricelist_items_to_create:
            pricelist.write({'item_ids': pricelist_items_to_create})
            SALEPRICCELISTITEAMS |= pricelist.item_ids
        if supplierinfo_to_create:
            product_variant.write({'seller_ids': supplierinfo_to_create})
            VENDORPRICCELISTITEAMS |= product_variant.seller_ids

    def process_print_product_for_midocean(self, result, raw_product_variants, pim_config_id, print_details):
        """
        Optimized version of the print product import function for MidOcean
        Using a similar pattern to process_xd_print_product to avoid duplicate product creation
        With fixed error handling for None values
        """
        global PRODUCTS, PRODUCT_DICT, PRICELISTS

        # Initialize variables
        vendor_name = pim_config_id.partner_id.name if pim_config_id.partner_id else ''
        currency = pim_config_id.currency_id
        to_currency = pim_config_id.converted_currency_id
        attribute_value_cache = {}

        # Get or create pricelist
        pricelist = next((p for p in PRICELISTS if p.currency_id.id == to_currency.id), self.env['product.pricelist'])
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': f'{vendor_name} Pricelist',
                'currency_id': to_currency.id
            })
            PRICELISTS |= pricelist

        # Set no_variant attributes once
        printing_attribute_lines = pim_config_id.printing_product_attribute_lines.filtered(lambda x: x.stop_variant_creation)
        if printing_attribute_lines:
            printing_attribute_lines.attribute_id.write({'create_variant': 'no_variant'})

        if isinstance(print_details, str):
            print_details = json.loads(html.unescape(print_details))

        # Step 1: Batch collect product information using (product_name, technique_id) as key
        product_infos = {}

        for print_detail in print_details:
            printing_techniques = print_detail.get("Printing_techniques", [])
            if not printing_techniques:
                continue

            for technique in printing_techniques:
                technique_name = technique.get("Description", "").strip()
                technique_id = technique.get("Id")

                if not technique_name:
                    continue

                technique_id_str = str(technique_id).strip() if technique_id else "default"
                product_name = f"{technique_name} {technique_id_str}".strip()

                # Store the data keyed by product name and technique id to avoid duplicates
                key = (product_name, technique_id_str)
                if key not in product_infos:
                    product_infos[key] = {
                        'technique': technique,
                        'print_detail': print_detail,
                        'setup_charge': float(technique.get("Setup", "0").replace(",", ".")),
                        'repeat_charge': float(technique.get("Setup_repeat", "0").replace(",", "."))
                    }

        # Step 2: Find existing products using product name and technique ID
        product_keys = list(product_infos.keys())
        existing_products = {
            (p.name.strip(), (p.model_code or '').strip()): p
            for p in PRODUCT_DICT.values()
            if (p.name.strip(), (p.model_code or '').strip()) in product_keys
        }

        # Step 3: Identify missing products and search the database
        missing_keys = [key for key in product_keys if key not in existing_products]
        if missing_keys:
            domain = ['|'] * (len(missing_keys) - 1)
            for name, code in missing_keys:
                domain += ['&', ('name', '=', name), ('model_code', '=', code)]
            db_products = self.env['product.template'].search(domain)
            for product in db_products:
                key = (product.name.strip(), (product.model_code or '').strip())
                existing_products[key] = product
                PRODUCTS |= product
                PRODUCT_DICT[product.name] = product

        # Preload all attribute values to minimize DB queries
        printing_attributes = pim_config_id.printing_product_attribute_lines.attribute_id
        all_attribute_values = self.env['product.attribute.value'].search([
            ('attribute_id', 'in', printing_attributes.ids)
        ])
        for value in all_attribute_values:
            attribute_value_cache[(value.attribute_id.id, value.name)] = value

        # Step 4: Process each product info - create or update products
        all_product_ids = self.env['product.template']
        product_variant_data = []  # To store variant data for later processing

        for (product_name, technique_id_str), info in product_infos.items():
            technique = info['technique']
            print_detail = info['print_detail']
            setup_charge = info['setup_charge']
            repeat_charge = info['repeat_charge']

            # Build attribute map
            attribute_map = {}

            # Process attributes from technique and print_detail
            for line in pim_config_id.printing_product_attribute_lines:
                attribute = line.attribute_id
                custom_value = line.custom_value

                if not attribute or not custom_value:
                    continue

                if custom_value == 'Max_colours':
                    max_colors_str = technique.get('Max_colours', '0') or '0'
                    try:
                        max_colors = int(max_colors_str)
                    except ValueError:
                        max_colors = 0

                    if max_colors == 0:
                        color_values = ['0']
                    elif max_colors == 1:
                        color_values = ['1']
                    else:
                        color_values = [str(i) for i in range(1, max_colors + 1)]

                    # Process all color values at once
                    for val in color_values:
                        key = (attribute.id, val)
                        if key not in attribute_value_cache:
                            # Create value and update cache
                            new_value = self.env['product.attribute.value'].create({
                                'name': val,
                                'attribute_id': attribute.id
                            })
                            attribute_value_cache[key] = new_value

                        # Add to attribute map
                        attribute_map.setdefault(attribute, set()).add(attribute_value_cache[key])

                elif custom_value == 'Position_id':
                    value_name = str(print_detail.get('Position_id', '')).strip()
                    if value_name:
                        key = (attribute.id, value_name)
                        if key not in attribute_value_cache:
                            value = self.env['product.attribute.value'].search([
                                ('name', '=', value_name),
                                ('attribute_id', '=', attribute.id)
                            ], limit=1)

                            if not value:
                                value = self.env['product.attribute.value'].create({
                                    'name': value_name,
                                    'attribute_id': attribute.id
                                })

                            attribute_value_cache[key] = value

                        # Add to attribute map
                        attribute_map.setdefault(attribute, set()).add(attribute_value_cache[key])

            # Get existing product or create new one
            product = existing_products.get((product_name.strip(), technique_id_str.strip()))

            if product:
                # Update existing product attribute lines
                existing_lines = {line.attribute_id.id: line for line in product.attribute_line_ids}
                updates = []
                creates = []

                for attribute, values in attribute_map.items():
                    value_ids = [v.id for v in values]
                    if attribute.id in existing_lines:
                        line = existing_lines[attribute.id]
                        existing_values = set(line.value_ids.ids)
                        merged_ids = list(set(existing_values).union(set(value_ids)))

                        if existing_values != set(merged_ids):
                            updates.append((line, merged_ids))
                    else:
                        creates.append((attribute.id, value_ids))

                # Apply updates to existing attribute lines
                for line, merged_ids in updates:
                    line.write({'value_ids': [(6, 0, merged_ids)]})

                # Create new attribute lines
                if creates:
                    product.write({
                        'attribute_line_ids': [
                            (0, 0, {'attribute_id': attr_id, 'value_ids': [(6, 0, val_ids)]})
                            for attr_id, val_ids in creates
                        ]
                    })
            else:
                # Create new product with attribute lines
                product_vals = {
                    'name': product_name,
                    'type': 'service',
                    'product_service_type': 'printing',
                    'pim_config_id': pim_config_id.id,
                    'model_code': technique_id_str,
                    'attribute_line_ids': [
                        (0, 0, {
                            'attribute_id': attr.id,
                            'value_ids': [(6, 0, [v.id for v in values])]
                        })
                        for attr, values in attribute_map.items() if values
                    ]
                }
                product = self.env['product.template'].create(product_vals)

                # Update global caches
                existing_products[(product_name.strip(), technique_id_str.strip())] = product
                PRODUCTS |= product
                PRODUCT_DICT[product_name] = product

            # Link with raw product variants if necessary
            if raw_product_variants:
                linked_variant_ids = []
                # Only link variants matching the actual Max_colours values we just processed
                max_colour_values = []
                for attr, values in attribute_map.items():
                    if attr.name == 'PrintingColor':
                        max_colour_values = [v.name for v in values]
                        break

                if max_colour_values:
                    for variant in product.product_variant_ids:
                        # Check if the variant's Max_colours attribute value matches one of the allowed values
                        variant_value_names = [v.name for v in variant.product_template_attribute_value_ids.mapped('product_attribute_value_id')]
                        if any(val in variant_value_names for val in max_colour_values):
                            linked_variant_ids.append(variant.id)

                raw_product_variants.write({
                    'printing_template_ids': [(4, product.id)],
                    'printing_variant_ids': [Command.link(v_id) for v_id in linked_variant_ids]
                })

            # Collect product for later variant processing
            all_product_ids |= product

            # Store variant data for later processing
            product_variant_data.append({
                'product': product,
                'technique': technique,
                'setup_charge': setup_charge,
                'repeat_charge': repeat_charge
            })

        # Step 5: Process variants and pricelist items
        if all_product_ids:
            all_variants = all_product_ids.mapped('product_variant_ids')

            # Mark all variants with pim_config_id
            all_variants.write({'pim_config_id': pim_config_id.id})

            # Clear existing pricelist items if needed
            if all_variants:
                if pim_config_id.create_pricelist in ('sales', 'both'):
                    self.env.cr.execute("""
                        DELETE FROM product_pricelist_item
                        WHERE pricelist_id = %s AND product_id in %s AND pim_config_id = %s
                    """, (pricelist.id, tuple(all_variants.ids), pim_config_id.id))

                if pim_config_id.create_pricelist in ('vendor', 'both'):
                    self.env.cr.execute("""
                        DELETE FROM product_supplierinfo
                        WHERE partner_id = %s AND product_id in %s AND pim_config_id = %s
                    """, (pim_config_id.partner_id.id, tuple(all_variants.ids), pim_config_id.id))

        # Group variants by product template
        variants_by_template = {}
        for variant in all_variants:
            variants_by_template.setdefault(variant.product_tmpl_id.id, []).append(variant)

        # Prepare pricelist items
        pricelist_items = []
        supplier_info = []

        # Process each product's variant data
        for data in product_variant_data:
            product = data['product']
            technique = data['technique']
            setup_charge = data['setup_charge']
            repeat_charge = data['repeat_charge']

            variants = variants_by_template.get(product.id, [])
            if not variants:
                continue

            # Set variant charges
            for variant in variants:
                variant.write({
                    'repeat_charge': repeat_charge,
                    'setup_charge': setup_charge
                })

            # Sort variants by color index
            sorted_variants = variants
            if len(variants) > 1:
                max_colour_attr = self.env['product.attribute'].search([('name', '=', 'PrintingColor')], limit=1)
                if max_colour_attr:
                    sorted_variants = sorted(
                        variants,
                        key=lambda v: int(next(
                            (ptav.product_attribute_value_id.name for ptav in v.product_template_attribute_value_ids
                            if ptav.attribute_id == max_colour_attr),
                            '0'
                        ))
                    )

            # Process pricelist items for variants
            max_colours = int(technique.get("Max_colours", "0") or 0)
            var_costs = technique.get("Var_costs", []) or []  # Add or [] to handle None

            variants_to_flag = self.env['product.product']

            # Process each variant with its color index
            for color_index, variant in enumerate(sorted_variants, start=1):
                processed_qty_sales = set()
                processed_qty_vendor = set()

                for var_cost in var_costs:
                    # Add defensive check for None or missing Scales
                    scales = var_cost.get("Scales") if var_cost else None
                    if not scales:
                        continue

                    # Now iterate over scales safely
                    for scale in scales:
                        # Add defensive checks for each field
                        min_qty_raw = scale.get("Minimum_quantity", "1") if scale else "1"
                        price_raw = scale.get("Price", "0") if scale else "0"
                        next_price_raw = scale.get("Next_price", "0") if scale else "0"

                        # Convert with error handling
                        try:
                            min_qty = int(min_qty_raw.replace('.', '').replace(',', ''))
                        except (ValueError, AttributeError):
                            min_qty = 1

                        try:
                            base_price = float(price_raw.replace(',', '.'))
                        except (ValueError, AttributeError):
                            base_price = 0.0

                        try:
                            if next_price_raw == "":
                                next_price = 0.0
                            else:
                                next_price = float(next_price_raw.replace(',', '.'))
                        except (ValueError, AttributeError):
                            next_price = 0.0

                        price = base_price
                        if max_colours > 0 and color_index > 1:
                            price += next_price * (color_index - 1)

                        if min_qty in processed_qty_sales or min_qty in processed_qty_vendor:
                            continue

                        if currency != to_currency:
                            price = self._get_currency_convert_amount(currency, price, to_currency)

                        margin = pim_config_id.sale_margin or 0.0
                        final_price = price + (price * margin / 100.0)

                        # Prepare sale pricelist items
                        if pim_config_id.create_pricelist in ('sales', 'both'):
                            processed_qty_sales.add(min_qty)
                            pricelist_items.append({
                                'product_id': variant.id,
                                'fixed_price': final_price,
                                'price': final_price,
                                'min_quantity': min_qty,
                                'currency_id': to_currency.id,
                                'pricelist_id': pricelist.id,
                                'applied_on': '0_product_variant',
                                'pim_config_id': pim_config_id.id,
                            })

                        # Prepare vendor pricelist items
                        if pim_config_id.create_pricelist in ('vendor', 'both'):
                            processed_qty_vendor.add(min_qty)
                            supplier_info.append({
                                'partner_id': pim_config_id.partner_id.id,
                                'product_id': variant.id,
                                'pim_config_id': pim_config_id.id,
                                'min_qty': min_qty,
                                'price': price,
                                'currency_id': to_currency.id,
                            })
                            variants_to_flag |= variant

        # Create all pricelist items at once
        if pricelist_items:
            self.env['product.pricelist.item'].sudo().create(pricelist_items)

        # Create all supplier info at once
        if supplier_info:
            self.env['product.supplierinfo'].sudo().create(supplier_info)

        if variants_to_flag:
            variants_to_flag.write({'service_to_purchase': True,})

        return all_variants

    def _collect_attribute_values(self, technique, print_detail, pim_config_id, attribute_map, attribute_value_cache):
        printing_attribute_lines = pim_config_id.printing_product_attribute_lines.filtered(lambda x: x.stop_variant_creation)
        if printing_attribute_lines:
            printing_attribute_lines.attribute_id.create_variant = 'no_variant'

        for line in pim_config_id.printing_product_attribute_lines:
            attribute = line.attribute_id
            custom_value = line.custom_value

            if not attribute or not custom_value:
                continue

            if custom_value == 'Max_colours':
                max_colors_str = technique.get('Max_colours', '0') or '0'
                try:
                    max_colors = int(max_colors_str)
                except ValueError:
                    max_colors = 0

                if max_colors == 0:
                    color_values = ['0']
                elif max_colors == 1:
                    color_values = ['1']
                else:
                    color_values = [str(i) for i in range(1, max_colors + 1)]

                for val in color_values:
                    key = (attribute.id, val)
                    value = attribute_value_cache.get(key)
                    if not value:
                        value = self._get_or_create_attribute_value(val, attribute)
                        attribute_value_cache[key] = value
                    attribute_map.setdefault(attribute, set()).add(value)

            elif custom_value == 'Position_id':
                value_name = str(print_detail.get('Position_id', '')).strip()
                if value_name:
                    key = (attribute.id, value_name)
                    value = attribute_value_cache.get(key)
                    if not value:
                        value = self._get_or_create_attribute_value(value_name, attribute)
                        attribute_value_cache[key] = value
                    attribute_map.setdefault(attribute, set()).add(value)

    def _convert_attribute_map_to_lines(self, attribute_map):
        return [(attribute, list(values)) for attribute, values in attribute_map.items()]

    def _get_or_create_attribute_value(self, value_name, attribute, pim_config_id):
        """Utility to get or create a value for a given attribute."""

        # global PRODUCTATTRIBUTEVALUE
        if not value_name:
            return None
        val = next((val for val in pim_config_id.printing_product_attribute_lines.attribute_id.mapped('value_ids') if val.name == str(value_name) and val.attribute_id.id == attribute.id), self.env['product.attribute.value'])

        if not val:
            val = self.env['product.attribute.value'].create({
                'name': value_name,
                'attribute_id': attribute.id
            })
            # PRODUCTATTRIBUTEVALUE |= val
        return val
    
    def _create_or_update_print_product(self, product, product_name, raw_product_variants, technique_id, pim_config_id, attribute_lines):
        global PRODUCTS
        if product:
            existing_lines = {line.attribute_id.id: line for line in product.attribute_line_ids}
            for attribute, values in attribute_lines:
                value_ids = [v.id for v in values]
                if attribute.id in existing_lines:
                    existing_line = existing_lines[attribute.id]
                    existing_value_ids = existing_line.value_ids.ids
                    merged_ids = list(set(existing_value_ids + value_ids))
                    existing_line.write({'value_ids': [Command.set(merged_ids)]})
                else:
                    product.write({
                        'attribute_line_ids': [Command.create({
                            'attribute_id': attribute.id,
                            'value_ids': [Command.set(value_ids)]
                        })]
                    })
        else:
            vals = {
                'name': product_name,
                'type': 'service',
                'product_service_type': 'printing',
                'pim_config_id': pim_config_id.id,
                'model_code': technique_id,
                'attribute_line_ids': [
                    Command.create({
                        'attribute_id': attribute.id,
                        'value_ids': [Command.set([v.id for v in values])]
                    }) for attribute, values in attribute_lines
                ],
            }
            product = self.env['product.template'].create(vals)
            PRODUCTS |= product
        if raw_product_variants:
            raw_product_variants.write({
                'printing_template_ids': [Command.link(product.id)]
            })

        product.product_variant_ids.write({'pim_config_id': pim_config_id.id})
        return product.product_variant_ids

    def _process_pricelist_for_printing_product_midocean_data(self, product_variant, technique_data, pim_config_id, color_index=1):
        """
        Optimized version that only creates new records or updates existing ones
        without any deletion operations - pure update-or-create logic
        """
        global SALEPRICCELISTITEAMS, VENDORPRICCELISTITEAMS
        if not product_variant:
            return

        currency = pim_config_id.currency_id
        to_currency = pim_config_id.converted_currency_id
        pricelist = self._get_or_create_pricelist(to_currency.id, pim_config_id.partner_id.name)

        max_colours = int(technique_data.get("Max_colours", "0") or 0)
        var_costs = technique_data.get("Var_costs", [])

        # Sales items cleanup
        if pim_config_id.create_pricelist in ('sales', 'both'):
            self.env.cr.execute("""
                DELETE FROM product_pricelist_item
                WHERE pricelist_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pricelist.id, product_variant.id, pim_config_id.id))
            self.env.cr.commit()
            SALEPRICCELISTITEAMS = self.env['product.pricelist.item'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])

        # Vendor items cleanup
        if pim_config_id.create_pricelist in ('vendor', 'both'):
            self.env.cr.execute("""
                DELETE FROM product_supplierinfo
                WHERE partner_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pim_config_id.partner_id.id, product_variant.id, pim_config_id.id))
            self.env.cr.commit()
            VENDORPRICCELISTITEAMS = self.env['product.supplierinfo'].sudo().search([('pim_config_id', '=', self.pim_config_id.id)])

        sale_items_data = []
        vendor_items_data = []

        processed_qty_sales = set()
        processed_qty_vendor = set()

        for var_cost in var_costs:
            for scale in var_cost.get("Scales", []):
                min_qty = int(scale.get("Minimum_quantity", "1").replace('.', '').replace(',', ''))
                base_price = float(scale.get("Price", "0").replace(',', '.'))
                next_price_raw = scale.get("Next_price", "") or "0"
                next_price = float(next_price_raw.replace(',', '.') or 0.0)

                price = base_price
                if max_colours > 0 and color_index > 1:
                    price += next_price * (color_index - 1)

                if min_qty in processed_qty_sales or min_qty in processed_qty_vendor:
                    continue

                if currency != to_currency:
                    price = self._get_currency_convert_amount(currency, price, to_currency)

                margin = pim_config_id.sale_margin or 0.0
                final_price = price + (price * margin / 100.0)

                # Sale pricelist items
                if pim_config_id.create_pricelist in ('sales', 'both'):
                    processed_qty_sales.add(min_qty)
                    sale_items_data.append({
                        'product_id': product_variant.id,
                        'fixed_price': final_price,
                        'price': final_price,
                        'min_quantity': min_qty,
                        'currency_id': to_currency.id,
                        'pricelist_id': pricelist.id,
                        'pim_config_id': pim_config_id.id,
                    })

                # Vendor pricelist items
                if pim_config_id.create_pricelist in ('vendor', 'both'):
                    processed_qty_vendor.add(min_qty)
                    vendor_items_data.append({
                        'partner_id': pim_config_id.partner_id.id,
                        'product_id': product_variant.id,
                        'pim_config_id': pim_config_id.id,
                        'min_qty': min_qty,
                        'price': price,
                        'currency_id': to_currency.id,
                    })

        # Final create and assign to global variables
        if sale_items_data:
            new_sale_items = self.env['product.pricelist.item'].sudo().create(sale_items_data)
            SALEPRICCELISTITEAMS += new_sale_items  # ADDED

        if vendor_items_data:
            new_vendor_items = self.env['product.supplierinfo'].sudo().create(vendor_items_data)
            VENDORPRICCELISTITEAMS += new_vendor_items  # ADDED
    def _fetch_printing_variant_xd(self):
        _logger.info("-\n\n------START-1212121--get_xd_data---%s", datetime.now())
        def normalize(value):
            return str(value).strip().lower() if value else ''

        datas = self.env['queue.job'].search([('pim_config_id', '=', 9), ('state', '=', 'process')],limit=500)
        for data in datas:
            _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
            results = data.result.get('xd_PrintData')
            product = self.env['product.product'].search([
                ('type', '=', 'consu'),
                ('default_code', '=', data.sub_reference),
                ('pim_config_id', '=', data.pim_config_id.id)
            ])
            if data.result.get('xd_TotalCO2Emissions'):
                product.write({'carbon_co2': data.result.get('xd_TotalCO2Emissions'),'description_sale':product.description})   
                # product.write({'carbon_co2': data.result.get('xd_TotalCO2Emissions')})
            # printing_products = self.env['product.product'].search([
            #     ('type', '=', 'service'),
            #     ('pim_config_id', '=', 9)
            # ])
            printing_products = product.printing_template_ids
            if results:
                results = json.loads(html.unescape(results))
                for result in results:
                    printing_datas = result.get('Print_price_data', [])
                    for printing_data in printing_datas:
                        printing_data.update({'PrintPositionCode': result.get('PrintPositionCode')})

                        amount_color_id = normalize(printing_data.get('NrOfColors'))
                        size = normalize(printing_data.get('PrintArea'))
                        full_colour = normalize(printing_data.get('FullColor'))
                        print_position = normalize(result.get('PrintPositionCode'))


                        if full_colour == 'true':
                            amount_color_id = 'fullcolor'

                        matching_variants = printing_products.product_variant_ids.filtered(
                            lambda variant: all([
                                not amount_color_id or amount_color_id in [
                                    normalize(name) for name in variant.product_template_attribute_value_ids.mapped(
                                        'product_attribute_value_id.name')
                                ],
                                not size or size in [
                                    normalize(name) for name in variant.product_template_attribute_value_ids.mapped(
                                        'product_attribute_value_id.name')
                                ],
                                not print_position or print_position in [
                                    normalize(name) for name in variant.product_template_attribute_value_ids.mapped(
                                        'product_attribute_value_id.name')
                                ],
                            ])
                        )

                        for matching_variant in  matching_variants:
                            product.write({
                                'printing_variant_ids': [Command.link(matching_variant.id)]
                            })
            data.write({'state':'done'})
            self.env.cr.commit()
            _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())
        _logger.info("------END-------%s", datetime.now())

    def _fetch_printing_variant_keramikos(self):
        _logger.info("-\n\n------START-1212121--get_keramikos_data---%s", datetime.now())

        def normalize(value):
            return str(value).strip().lower() if value else ''

        datas = self.env['queue.job'].search([('pim_config_id', '=', 8), ('state', '=', 'process')],limit=500)
        for data in datas:
            _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
            results = data.result.get('kera_PrintTypes')
            product = self.env['product.product'].search([
                ('type', '=', 'consu'),
                ('default_code', '=', data.sub_reference),
                ('pim_config_id', '=', data.pim_config_id.id)
            ])
            if data.result.get('kera_Name'):
                product_name = 'Shipping Product For ' + data.result.get('kera_Name')
                shipping_product = self.env['product.product'].search([
                    ('type', '=', 'service'),
                    ('name', '=', product_name),
                    ('pim_config_id', '=', data.pim_config_id.id),
                    ('product_service_type','=','delivery')
                ],limit=1)
                product.write({'shipping_variant_ids':[Command.link(shipping_product.id)]})
            if data.result.get('kera_Description'):
                product.write({'description_sale':data.result.get('kera_Description')})
            printing_products = product.printing_template_ids
            if results:
                for result in results:
                    printing_datas = result.get('kera_PrintPrices', [])
                    printing_datas = json.loads(html.unescape(printing_datas))
                    for printing_data in printing_datas:
                        amount_color_id = normalize(printing_data.get('NumberOfColours'))
                        size = str(result.get('kera_PrintArea')).strip()

                        matching_variants = printing_products.product_variant_ids.filtered(
                            lambda variant: all([
                               amount_color_id in [
                                    normalize(name) for name in variant.product_template_attribute_value_ids.mapped(
                                        'product_attribute_value_id.name')
                                ],
                               not size or  size in [
                                    name for name in variant.product_template_attribute_value_ids.mapped(
                                        'product_attribute_value_id.name')
                                ],
                            ])
                        )
                        for matching_variant in matching_variants:
                            product.write({
                                'printing_variant_ids': [Command.link(matching_variant.id)]
                            })
            data.write({'state': 'done'})
            self.env.cr.commit()
            _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())
        _logger.info("------END-------%s", datetime.now())


    def _fetch_printing_variant_pfconcept(self):
        _logger.info("-\n\n------START-1212121--get_pf_data---%s", datetime.now())

        def normalize(value):
            return str(value).strip().lower() if value else ''

        datas = self.env['queue.job'].search([('pim_config_id', '=', 4), ('state', '=', 'process')],limit=500)
        for data in datas:
            _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
            results = data.result.get('printData')
            product = self.env['product.product'].search([
                ('type', '=', 'consu'),
                ('default_code', '=', data.sub_reference),
                ('pim_config_id', '=', data.pim_config_id.id)
            ])
            if data.result.get('co2footprint'):
                product.write({'carbon_co2': data.result.get('co2footprint')})
            if data.result.get('extDesc'):
                product.write({'description_sale': data.result.get('extDesc')})
            printing_products = product.printing_template_ids
            if results:
                for result in results:
                    printing_datas = result.get('print_price_data', [])
                    if printing_datas:
                        printing_datas = json.loads(html.unescape(printing_datas))
                        logo_datas = printing_datas.get('LogoSize')
                        for logo_data in logo_datas:
                            print_position = str(result.get('impLocation'))
                            amount_color_id = str(logo_data.get('AmountColorsId'))
                            size = str(logo_data.get('LogoSizeCm2'))

                            if amount_color_id and size == '0.0':
                                matching_variants = printing_products.product_variant_ids.filtered(
                                    lambda variant: all([
                                        amount_color_id in [
                                            name for name in variant.product_template_attribute_value_ids.mapped(
                                                'product_attribute_value_id.name')
                                        ],
                                        print_position in [
                                            name for name in variant.product_template_attribute_value_ids.mapped(
                                                'product_attribute_value_id.name')
                                        ],
                                    ])
                                )
                            else:
                                matching_variants = printing_products.product_variant_ids.filtered(
                                    lambda variant: all([
                                        size in [
                                            normalize(name) for name in variant.product_template_attribute_value_ids.mapped(
                                                'product_attribute_value_id.name')
                                        ],
                                       print_position in [
                                            name for name in variant.product_template_attribute_value_ids.mapped(
                                                'product_attribute_value_id.name')
                                        ],
                                    ])
                                )
                            for matching_variant in matching_variants:
                                product.write({
                                    'printing_variant_ids': [Command.link(matching_variant.id)]
                                })
            data.write({'state': 'done'})
            self.env.cr.commit()
            _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())
        _logger.info("------END-------%s", datetime.now())

    def _collect_attribute_values_for_laltex(self, print_detail, pim_config_id, attribute_map, attribute_value_cache):
        # Set 'create_variant' = 'no_variant' for attributes with stop_variant_creation
        printing_attribute_lines = pim_config_id.printing_product_attribute_lines.filtered(lambda x: x.stop_variant_creation)
        # if printing_attribute_lines:
        #     printing_attribute_lines.attribute_id.create_variant = 'no_variant'

        for line in pim_config_id.printing_product_attribute_lines:
            attribute = line.attribute_id
            custom_value = line.custom_value

            if not attribute or not custom_value:
                continue

            # NumColours is like Max_colours in Midocean — creates variants
            if custom_value == 'NumColours':
                print_prices = print_detail.get('PrintPrice', [])
                colors_set = set()

                for price in print_prices:
                    num_colours = str(price.get('NumColours', '')).strip()
                    if num_colours:
                        colors_set.add(num_colours)

                if not colors_set:
                    continue

                for val in sorted(colors_set):
                    key = (attribute.id, val)
                    value = attribute_value_cache.get(key)
                    if not value:
                        value = self._get_or_create_attribute_value(val, attribute, pim_config_id)
                        attribute_value_cache[key] = value
                    attribute_map.setdefault(attribute, set()).add(value)

            # PrintPosition from print_detail
            elif custom_value == 'PrintPosition':
                val = str(print_detail.get('PrintPosition', '')).strip()
                if val:
                    key = (attribute.id, val)
                    value = attribute_value_cache.get(key)
                    if not value:
                        value = self._get_or_create_attribute_value(val, attribute, pim_config_id)
                        attribute_value_cache[key] = value
                    attribute_map.setdefault(attribute, set()).add(value)

            # PrintArea from print_detail
            elif custom_value == 'PrintArea':
                val = str(print_detail.get('PrintArea', '')).strip()
                if val:
                    key = (attribute.id, val)
                    value = attribute_value_cache.get(key)
                    if not value:
                        value = self._get_or_create_attribute_value(val, attribute, pim_config_id)
                        attribute_value_cache[key] = value
                    attribute_map.setdefault(attribute, set()).add(value)


    def _find_printing_product_variant_for_laltax(self):
        _logger.info("-\n\n------START-1212121--get_laltax_data---%s", datetime.now())
        queue_jobs = self.env['queue.job'].search([('pim_config_id', '=', 7), ('state', '=', 'process')], limit=500)

        for job in queue_jobs:
            vendor_name = job.pim_config_id.partner_id.name if job.pim_config_id.partner_id else ''
            try:
                result = job.result
                if isinstance(result, str):
                    result = json.loads(html.unescape(result))
            except Exception as e:
                _logger.warning(f"Failed to parse result for job {job.id}: {e}")
                continue

            print_details = result.get('lt_PrintDetails', [])
            if isinstance(print_details, str):
                print_details = json.loads(html.unescape(print_details))

            raw_product_code = result.get('lt_ProductCodeItemCode', '').strip()
            raw_product = self.env['product.product'].search([('default_code', '=', raw_product_code)], limit=1)
            if not raw_product:
                _logger.warning(f" No raw product found with default_code: {raw_product_code}")
                continue

            raw_product.description_sale = result.get('lt_Description', '')
            if print_details:
                for print_detail in print_details:
                    product_name = print_detail.get('PrintType', '').strip() + ' BY ' + vendor_name
                    product = self.env['product.template'].search([
                        ('name', '=', product_name),
                        ('pim_config_id', '=', job.pim_config_id.id)
                    ], limit=1)

                    if not product:
                        _logger.warning(f"Product template not found for name: {product_name}")
                        continue

                    # Build attribute_map
                    attribute_map = {}
                    attribute_value_cache = {}
                    pim_config = job.pim_config_id

                    self._collect_attribute_values_for_laltex(print_detail, pim_config, attribute_map, attribute_value_cache)

                    # Find matching variant
                    variant = self._find_matching_variant(product, attribute_map)
                    if variant:
                        # Link variant to raw product
                        if variant.id not in raw_product.printing_variant_ids.ids:
                            raw_product.write({
                                'printing_variant_ids': [(4, variant.id)]
                            })
                    else:
                        _logger.warning(f" No matching variant found for product: {product_name}")

            shipping_data = result.get('lt_ShippingCharge', [])
            if shipping_data and job.pim_config_id.shipping_product:
                if isinstance(shipping_data, str):
                    shipping_data = json.loads(html.unescape(shipping_data))

                for ship in shipping_data:
                    ship_name = ship.get('ServiceName')
                    if not ship_name:
                        continue

                    ship_product = self.env['product.template'].search([
                        ('name', '=', ship_name),
                        ('pim_config_id', '=', job.pim_config_id.id)
                    ], limit=1)

                    if not ship_product:
                        _logger.warning(f"Shipping product not found: {ship_name}")
                        continue

                    # Find shipping variant (usually only 1)
                    shipping_variant = ship_product.product_variant_id
                    if shipping_variant and shipping_variant.id not in raw_product.shipping_variant_ids.ids:
                        raw_product.write({
                            'shipping_variant_ids': [(4, shipping_variant.id)]
                        })
            job.write({'state': 'done'})
            self.env.cr.commit()
        _logger.info("------END-------%s", datetime.now())

    def _find_matching_variant(self, product, attribute_map):
        variant_attrs = {
            attr: values
            for attr, values in attribute_map.items()
            if attr.create_variant != 'no_variant'
        }

        for variant in product.product_variant_ids:
            variant_values = set(variant.product_template_attribute_value_ids.mapped('product_attribute_value_id'))
            required_values = set()
            for values in variant_attrs.values():
                required_values.update(values)
            if required_values.issubset(variant_values):
                return variant
        return None

    def _find_printing_product_variant_for_preseli(self):
        _logger.info("------START--get_preseli_data---%s", datetime.now())
        queue_jobs = self.env['queue.job'].search([('pim_config_id', '=', 5), ('state', '=', 'process')], limit=500)

        for job in queue_jobs:
            vendor_name = job.pim_config_id.partner_id.name if job.pim_config_id.partner_id else ''
            try:
                result = job.result
                if isinstance(result, str):
                    result = json.loads(html.unescape(result))
            except Exception as e:
                _logger.warning(f"Failed to parse result for job {job.id}: {e}")
                continue

            # Get raw products from psli_ProductCode
            raw_product_code = result.get('psli_ProductCode', '').strip()

            # CHANGE: Removed limit=1 to get all matching raw products
            raw_products = self.env['product.product'].search([
                '|',
                ('default_code', '=', raw_product_code),
                ('model_code', '=', raw_product_code)
            ])

            if not raw_products:
                _logger.warning(f"No raw product found with code: {raw_product_code}")
                continue

            # Get printing products
            print_details = result.get('psli_Prices', [])
            if isinstance(print_details, str):
                print_details = json.loads(html.unescape(print_details))

            main_product_name = result.get('psli_ProductName', '').strip()

            if print_details:
                for print_detail in print_details:
                    # Skip unbranded entries
                    if print_detail.get('psli_Name', '').strip().lower() == 'unbranded':
                        _logger.info("Skipping unbranded print product.")
                        continue

                    printing_product_name = print_detail.get(job.pim_config_id.printing_product_name, '').strip()
                    product_name = f"{printing_product_name} BY {vendor_name} {main_product_name}"

                    # --- Get Printing Product ---
                    product = self.env['product.template'].search([
                        ('name', '=', product_name),
                        ('pim_config_id', '=', job.pim_config_id.id)
                    ], limit=1)

                    if not product:
                        _logger.warning(f"Printing product not found for name: {product_name}")
                        continue

                    variant = product.product_variant_id
                    if not variant:
                        _logger.warning(f"No variant found in template: {product.name}")
                        continue

                    # CHANGE: Loop through all matching raw products
                    for raw_product in raw_products:
                        raw_product.description_sale = result.get('psli_Description', '')

                        # --- Link Printing Variant ---
                        if variant.id not in raw_product.printing_variant_ids.ids:
                            raw_product.write({
                                'printing_variant_ids': [(4, variant.id)]
                            })
                            _logger.info(f" Linked printing variant '{variant.display_name}' to raw product '{raw_product.default_code}'")

                        # --- Link Delivery Products ---
                        for pd in print_detail.get('psli_PriceDetails', []):
                            if pd.get('Type', '').strip().lower() == 'carriage':
                                carriage_desc = pd.get('Description', '').strip()
                                if not carriage_desc:
                                    continue

                                delivery_product_name = f"{carriage_desc} - {main_product_name} - {printing_product_name}"

                                delivery_template = self.env['product.template'].search([
                                    ('name', '=', delivery_product_name)
                                ], limit=1)

                                if not delivery_template:
                                    continue

                                delivery_variant = delivery_template.product_variant_id
                                if not delivery_variant:
                                    continue

                                if delivery_variant.id not in raw_product.shipping_variant_ids.ids:
                                    raw_product.write({
                                        'shipping_variant_ids': [(4, delivery_variant.id)]
                                    })

            # --- Mark job as done ---
            job.write({'state': 'done'})
            self.env.cr.commit()
        _logger.info("------END--get_preseli_data---%s", datetime.now())
