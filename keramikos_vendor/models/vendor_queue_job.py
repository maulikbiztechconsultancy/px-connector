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

    def get_keramikos_product_data(self, pim_config_id):
        cr = self.env.cr
        cr.execute("""
                SELECT reference_id, id FROM product_category WHERE pim_config_id = %s
            """, (pim_config_id.id,))
        categories = dict(cr.fetchall())
        return categories

class QueueJob(models.Model):
    _inherit = "queue.job"

    def keramikos_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def keramikos_product_import_data(self):
        _logger.info("-\n\n------START-1212121--get_keramikos_data---%s", datetime.now())
        pim_config_id = self.pim_config_id
        categories = self.env['product.template'].get_keramikos_product_data(pim_config_id)
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
                WHERE model_code in %s AND pim_config_id = %s
                """,
                (tuple(references),pim_config_id.id)
            )
            rows = cr.fetchall()
            if rows:
                templates = dict(rows)
        for result in results:
            # Loop through each print detail in result
            self.process_single_keramikos_product_result(result, templates, categories, pim_config_id)
        _logger.info("------END-------%s", datetime.now())

    def process_single_keramikos_product_result(self, result, templates, categories, pim_config_id):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        model_code = result.get('kera_Prodcode')

        if model_code not in templates:
            if result.get('kera_CategoryName'):
                cat_code = result.get('kera_CategoryName')[0].get('code')
                cat_id = categories.get(cat_code, {})
            else:
                cat_id = 1
            template_data.update({
                'is_storable': True,
                'categ_id': cat_id if cat_id else 1,
                'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
            })
            new_template = self.create_row_product_template(template_data)
            templates[model_code] = new_template.id


        template_id = self.env['product.template'].browse(int(templates.get(model_code)))
        variants = template_id.product_variant_ids
        if template_id:
            template_id.product_add_mode = 'configurator' if len(variants) == 1 else 'matrix'
        if result.get('kera_PrintTypes') and pim_config_id.printing_product:
            print_details = result.get('kera_PrintTypes', [])
            self.keramikos_process_print_product(result, variants ,pim_config_id, print_details)
        if result.get('kera_DespatchPrices') and pim_config_id.shipping_product:
            self._keramikos_shipping_product_create(result)

        update_variant = variants[0] if variants else self.env['product.product']
        if update_variant:
            variant_data = template_data.copy()
            variant_data.update({
                'default_code': result.get('kera_Prodcode'),
                'json_data_varaint': str(result),
            })
            if result.get("kera_ImageUri"):
                variant_data.update({'image':result.get("kera_ImageUri")})
                image_data = self._get_image_data(result.get("kera_ImageUri"))
                variant_data.update({'image_1920': image_data,'image':result.get("kera_ImageUri")})

            update_variant.write(variant_data)

            self.env['queue.job'].search([('sub_reference', '=', result.get('kera_Prodcode'))], limit=1).write({
                'state': 'done',
                'records': update_variant.id
            })
            self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())

    def _process_keramikos_shipping_pricelist_data(self, product, pim_config_id, pricing_datas):
        product_variant = product.product_variant_ids
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
            min_qty = float(pricing_data.get('QuantityFrom') or 1.0)
            prices = pricing_data.get('Cost', '0')
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
                        'applied_on': '0_product_variant'
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
        if supplierinfo_to_create:
            product_variant.write({'seller_ids': supplierinfo_to_create,'service_to_purchase': True,'pim_config_id': pim_config_id.id})


