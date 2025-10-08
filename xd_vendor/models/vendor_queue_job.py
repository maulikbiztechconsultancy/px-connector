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


    def get_xd_product_data(self, pim_config_id):
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

    def xd_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def xd_product_import_data(self):
        _logger.info("-\n\n------START-1212121--get_xd_data---%s", datetime.now())
        pim_config_id = self.pim_config_id
        attribute_values, categories = self.env['product.template'].get_xd_product_data(pim_config_id)
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
            self.process_single_xd_product_result(result, templates, attribute_values, categories, pim_config_id,product_attribute_dict)
        _logger.info("------END-------%s", datetime.now())

    def process_xd_product_attributes(self, result, templates, attribute_values, product_attribute_dict):
        model_code = result.get('xd_ModelCode')
        template_id = templates.get(model_code)

        for attr_name in ['xd_Color', 'xd_TextileSize']:
            value_list = result.get(attr_name)
            if not value_list:
                continue

            if isinstance(value_list, list):
                value_key = '_'.join(value_list)
            else:
                value_list = [value_list]
                value_key = value_list[0]

            value_data = attribute_values.get(value_key)
            if not value_data:
                # Value does not exist — create it
                code_reference = value_key
                if len(value_list) > 1:
                    self.env.cr.execute("""
                        SELECT name FROM product_attribute_value
                        WHERE code_refrence IN %s
                    """, (tuple(value_list),))
                    fetched_names = [row[0].get('en_US') if isinstance(row[0], dict) else str(row[0]) for row in self.env.cr.fetchall()]
                    value_name = '/'.join(fetched_names) or code_reference
                else:
                    value_name = value_key

                # Resolve attribute_id (example assumes color=7, size=8, adjust accordingly)
                attribute_id = self.vendor_job_id.pim_config_id.attribute_line_fields.filtered(lambda x: x.attribute_id.name == attr_name).attribute_id

                value_id = self.env['product.attribute.value'].create({
                    'attribute_id': attribute_id.id,
                    'name': value_name,
                    'code_refrence': code_reference,
                }).id

                value_data = {
                    'code_refrence': code_reference,
                    'name': value_name,
                    'id': value_id,
                    'attribute_id': attribute_id.id,
                }
                attribute_values[value_key] = value_data  # Update for future reuse

            if template_id not in product_attribute_dict:
                product_attribute_dict[template_id] = {}

            self._create_or_update_product_template_attribute_line(
                template_id,
                value_data['attribute_id'],
                value_data['id'],
                product_attribute_dict
            )

    def process_single_xd_product_result(self, result, templates, attribute_values, categories, pim_config_id, product_attribute_dict):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        model_code = result.get('xd_ModelCode')

        if model_code not in templates:
            if result.get('xd_categories'):
                cat_code = result.get('xd_categories')[0].get('code')
                cat_id = categories.get(cat_code, {})
            else:
                cat_id = 1
            full_name = template_data.get('name', '')
            base_name = full_name.split(',')[0].strip()
            template_data.update({
                'name':base_name,
                'is_storable': True,
                'categ_id': cat_id if cat_id else 1,
                'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
            })
            new_template = self.create_row_product_template(template_data)
            templates[model_code] = new_template.id
        template_id = self.env['product.template'].browse(int(templates.get(model_code)))
        if template_data:
            full_name = template_data.get('name', '')
            base_name = full_name.split(',')[0].strip()
            template_data.update({'name': base_name,})
            template_id.name = base_name
        self.process_xd_product_attributes(result, templates, attribute_values, product_attribute_dict)
        variants = template_id.product_variant_ids
        if template_id:
            template_id.product_add_mode = 'configurator' if len(variants) == 1 else 'matrix'
        if result.get('xd_PrintData', []) and pim_config_id.printing_product:
            print_details = result.get('xd_PrintData', [])
            self.process_xd_print_product(result, variants ,pim_config_id, print_details)

        update_variant = variants[0] if variants else self.env['product.product']
        attribute_color = result.get('xd_Color')
        if attribute_color:
            attr_key = '_'.join(attribute_color) if isinstance(attribute_color, list) else attribute_color
            attribute_color_data = attribute_values.get(attr_key)
            for variant in variants:
                value_ids = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.id')
                if attribute_color_data and attribute_color_data['id'] in value_ids:
                    update_variant = variant

        if update_variant:
            if result.get('xd_ProductPrice', []):
                pricing_data = result.get('xd_ProductPrice')
                self._xd_process_pricelist_row_product_data(update_variant, pim_config_id,pricing_data)
            variant_data = template_data.copy()
            variant_data.update({
                'default_code': result.get('xd_ModelCodeItemCode'),
                'json_data_varaint': str(result),
            })
            if result.get("xd_MainImage"):
                variant_data.update({'image':result.get("xd_MainImage")})
                image_data = self._get_image_data(result.get("xd_MainImage"))
                variant_data.update({'image_1920': image_data,'image':result.get("xd_MainImage")})

            update_variant.write(variant_data)

            self.env['queue.job'].search([('sub_reference', '=', result.get('xd_ModelCodeItemCode'))], limit=1).write({
                'state': 'done',
                'records': update_variant.id
            })
            self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())

    def extract_pricing(self, data, price_type):
        result = []
        for i in range(1, 10):
            qty = data.get(f'xd_Qty{i}')
            price = data.get(f'xd_ItemPrice{price_type}_Qty{i}')
            if qty is not None and price is not None:
                result.append({'Quantity': qty, 'Price': price})
        return result

    def _xd_process_pricelist_row_product_data(self, product, pim_config_id,data):
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

        # Extract pricing
        pricing_datas_sales = self.extract_pricing(data, 'Gross') if pim_config_id.create_pricelist in ('sales',
                                                                                                        'both') else []
        pricing_datas_vendor = self.extract_pricing(data, 'Net') if pim_config_id.create_pricelist in ('vendor',
                                                                                                       'both') else []

        # SALES PRICELIST
        for pricing_data in pricing_datas_sales:
            min_qty = float(pricing_data.get('Quantity') or 1.0)
            base_price = self._sanitize_price_string(pricing_data.get('Price', '0'))
            if currency != to_currency:
                base_price = self._get_currency_convert_amount(currency, float(base_price), to_currency)
            try:
                base_price = float(base_price or 0.0)
            except ValueError:
                base_price = 0.0

            margin_percent = pim_config_id.sale_margin or 0.0
            sale_price = base_price + (base_price * margin_percent / 100.0)

            key_sales = (product_variant.id, min_qty)
            if key_sales not in seen_keys_sales:
                seen_keys_sales.add(key_sales)
                pricelist_items_to_create.append((0, 0, {
                    'product_id': product_variant.id,
                    'fixed_price': sale_price,
                    'pim_config_id': pim_config_id.id,
                    'price': sale_price,
                    'min_quantity': min_qty,
                    'currency_id': to_currency.id,
                    'applied_on': '0_product_variant'
                }))

        # VENDOR PRICELIST
        for pricing_data in pricing_datas_vendor:
            min_qty = float(pricing_data.get('Quantity') or 1.0)
            base_price = self._sanitize_price_string(pricing_data.get('Price', '0'))
            if currency != to_currency:
                base_price = self._get_currency_convert_amount(currency, float(base_price), to_currency)
            try:
                base_price = float(base_price or 0.0)
            except ValueError:
                base_price = 0.0

            if min_qty not in seen_keys_vendor:
                seen_keys_vendor.add(min_qty)
                supplierinfo_to_create.append((0, 0, {
                    'partner_id': pim_config_id.partner_id.id,
                    'product_id': product_variant.id,
                    'pim_config_id': pim_config_id.id,
                    'min_qty': min_qty,
                    'price': base_price,
                    'currency_id': to_currency.id,
                }))

        # Write updates
        if pricelist_items_to_create:
            pricelist.write({'item_ids': pricelist_items_to_create})
        if supplierinfo_to_create:
            product_variant.write({'seller_ids': supplierinfo_to_create})

