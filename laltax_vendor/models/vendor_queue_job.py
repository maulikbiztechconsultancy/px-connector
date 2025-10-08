# -*- coding: utf-8 -*
from odoo import models, fields, api, Command, _
import xmlrpc.client
import base64
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import logging
import json
import html
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = "product.template"


    def get_laltax_product_data(self, pim_config_id):
        cr = self.env.cr
        attribute_ids = pim_config_id.attribute_line_fields.attribute_id.ids
        # Use %s with tuple or list
        cr.execute(
            "SELECT name, id, attribute_id FROM product_attribute_value WHERE attribute_id IN %s",
            (tuple(attribute_ids),)
        )
        attribute_values = {}
        for line in pim_config_id.attribute_line_fields:
            attr = line.attribute_id
            if attr:
                for val in attr.value_ids:
                    key = val.code_refrence
                    attribute_values[key] = {
                        'id': val.id,
                        'name': val.name,
                        'attribute_id': attr.id,
                    }
        cr.execute("""
                SELECT reference_id, id FROM product_category WHERE pim_config_id = %s
            """, (pim_config_id.id,))
        categories = dict(cr.fetchall())
        return attribute_values, categories

class QueueJob(models.Model):
    _inherit = "queue.job"

    def laltax_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def laltax_product_import_data(self):
        _logger.info("-\n\n------START-1212121--get_laltax_data---%s", datetime.now())
        pim_config_id = self.pim_config_id
        attribute_values, categories = self.env['product.template'].get_laltax_product_data(pim_config_id)
        cr = self.env.cr
        cr.execute(
            """
            SELECT sub_reference, reference, result
            FROM queue_job
            WHERE state = 'process' AND model_id = %s AND pim_config_id = %s
            """,
            (self.env.ref('product.model_product_template').id, pim_config_id.id)
        )
        rows = cr.fetchall()
        # Unzip into two separate lists
        sub_references, references, results = zip(*rows) if rows else ([], [], [])
        # Convert to lists
        references = list(references)
        results = list(results)
        templates = {}
        if references:
            cr.execute(
                """
                SELECT model_code,id
                FROM product_template
                WHERE model_code in %s
                """,
                (tuple(references),)
            )
            rows = cr.fetchall()
            if rows:
                templates = dict(rows)
        product_attribute_dict = {}
        for result in results:
            # Loop through each print detail in result
            self.process_single_lal_product_result(result, templates, attribute_values, categories, pim_config_id,product_attribute_dict)
        _logger.info("------END-------%s", datetime.now())

    def process_laltax_product_attributes(self, result, templates, attribute_values, product_attribute_dict):
        model_code = result.get('lt_ProductCode')
        template_id = templates.get(model_code)

        for attr_data in ['lt_ItemColour', 'lt_Size']:
            value_key = result.get(attr_data)
            value_data = attribute_values.get(value_key)
            if not value_data:
                continue

            if template_id not in product_attribute_dict:
                product_attribute_dict[template_id] = {}

            self._create_or_update_product_template_attribute_line(
                template_id,
                value_data['attribute_id'],
                value_data['id'],
                product_attribute_dict
            )

    def process_single_lal_product_result(self, result, templates, attribute_values, categories, pim_config_id, product_attribute_dict):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        model_code = result.get('lt_ProductCode')

        if model_code not in templates:
            if result.get('lt_Category'):
                cat_code = result.get('lt_Category')[0].get('code')
                cat_id = categories.get(cat_code, False)
            else:
                cat_id = 1
            template_data.update({
                'product_add_mode': 'matrix',
                'is_storable': True,
                'categ_id': cat_id,
                'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
            })
            template_id = self.create_row_product_template(template_data)
            templates[model_code] = template_id.id
        else:
            template_id = self.env['product.template'].browse(int(templates.get(model_code)))

        self.process_laltax_product_attributes(result, templates, attribute_values, product_attribute_dict)
        template_id.pim_config_id = pim_config_id.id
        variants = template_id.product_variant_ids
        if result.get('lt_PrintDetails', []) and pim_config_id.printing_product:
            print_details = result.get('lt_PrintDetails', [])
            self.process_print_product_for_laltex(result, variants ,pim_config_id, print_details)
        if result.get('lt_ShippingCharge', []) and pim_config_id.shipping_product:
            self._laltax_shipping_product_create(result)
        update_variant = variants[0] if variants else self.env['product.product']
        attribute_color = result.get('lt_ItemColour')
        if attribute_color:
            attribute_color_data = attribute_values.get(attribute_color)
            for variant in variants:
                value_ids = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.id')
                if attribute_color_data and attribute_color_data['id'] in value_ids:
                    update_variant = variant

        if update_variant:
            if result.get('lt_ProductPrice', []):
                self._laltax_process_pricelist_row_product_data(update_variant, pim_config_id, result.get('lt_ProductPrice', []))
            variant_data = template_data.copy()
            variant_data.update({
                'default_code': result.get('lt_ProductCodeItemCode'),
                'json_data_varaint': str(result),
            })
            if result.get("lt_ItemImages"):
                variant_data.update({'image': result.get("lt_ItemImages")})
                # image_data = self._get_image_data(result.get("lt_ItemImages"))
                # variant_data.update({'image_1920': image_data})
            update_variant.write(variant_data)

        self.env['queue.job'].search([('sub_reference', '=', result.get('lt_ProductCodeItemCode'))], limit=1).write({
            'state': 'done',
            'records': update_variant.id
        })
        self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())


    def _laltax_process_pricelist_row_product_data(self, product, pim_config_id, pricing_datas):
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
            self.env.cr.execute("""
                DELETE FROM product_pricelist_item
                WHERE pricelist_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pricelist.id, product_variant.id, pim_config_id.id))
            self.env.cr.commit()

        # Vendor items
        if pim_config_id.create_pricelist in ('vendor', 'both'):
            self.env.cr.execute("""
                DELETE FROM product_supplierinfo
                WHERE partner_id = %s AND product_id = %s AND pim_config_id = %s
            """, (pim_config_id.partner_id.id, product_variant.id, pim_config_id.id))
            self.env.cr.commit()

        for pricing_data in pricing_datas:
            min_qty = float(pricing_data.get('MinQuantity') or 1.0)
            prices = pricing_data.get('Price', '0')
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
                    pricelist_items_to_create.append({
                        'product_id': product_variant.id,
                        'fixed_price': price,
                        'pim_config_id': pim_config_id.id,
                        'price': price,
                        'min_quantity': min_qty,
                        'pricelist_id': pricelist.id,
                        'currency_id': pim_config_id.converted_currency_id.id,
                        'applied_on': '0_product_variant',
                    })

            # Vendor mode
            if pim_config_id.create_pricelist in ('vendor', 'both'):
                if min_qty not in seen_keys_vendor:
                    seen_keys_vendor.add(min_qty)
                    supplierinfo_to_create.append({
                        'partner_id': pim_config_id.partner_id.id,
                        'product_id': product_variant.id,
                        'pim_config_id': pim_config_id.id,
                        'min_qty': min_qty,
                        'price': base_price,
                        'currency_id': pim_config_id.converted_currency_id.id,
                    })

        # Write updates
        if pricelist_items_to_create:
            self.env['product.pricelist.item'].sudo().create(pricelist_items_to_create)

        if supplierinfo_to_create:
            self.env['product.supplierinfo'].sudo().create(supplierinfo_to_create)


    def _find_printing_product_variant_for_laltax(self):
        _logger.info("-\n\n------START-1212121--get_laltax_data---%s", datetime.now())
        queue_jobs = self.env['queue.job'].search([('pim_config_id', '=', 8), ('state', '=', 'process')])

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
                    job.write({'state': 'done'})
                else:
                    _logger.warning(f" No matching variant found for product: {product_name}")
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
    def _find_printing_product_variant_for_laltax(self):
        _logger.info("-\n\n------START-1212121--get_laltax_data---%s", datetime.now())
        queue_jobs = self.env['queue.job'].search([('pim_config_id', '=', 8), ('state', '=', 'process')])

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
        queue_jobs = self.env['queue.job'].search([('pim_config_id', '=', 5), ('state', '=', 'process')])

        for job in queue_jobs:
            vendor_name = job.pim_config_id.partner_id.name if job.pim_config_id.partner_id else ''
            try:
                result = job.result
                if isinstance(result, str):
                    result = json.loads(html.unescape(result))
            except Exception as e:
                _logger.warning(f"Failed to parse result for job {job.id}: {e}")
                continue

            # Get raw product from psli_ProductCode
            raw_product_code = result.get('psli_ProductCode', '').strip()
            raw_product = self.env['product.product'].search([
                '|',
                ('default_code', '=', raw_product_code),
                ('model_code', '=', raw_product_code)
            ], limit=1)

            if not raw_product:
                _logger.warning(f"No raw product found with code: {raw_product_code}")
                continue
            raw_product.description_sale = result.get('psli_Description', '')

            # Get printing products
            print_details = result.get('psli_Prices', [])
            if isinstance(print_details, str):
                print_details = json.loads(html.unescape(print_details))

            main_product_name = result.get('psli_ProductName', '').strip()

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
