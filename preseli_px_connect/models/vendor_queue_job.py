# -*- coding: utf-8 -*
from odoo import models, fields, api, Command
import xmlrpc.client
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import logging
import base64
import requests
import json
_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _inherit = "queue.job"

    def pim_preseli_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def pim_preseli_product_import_data(self):
        _logger.info("-\n\n------START------%s", datetime.now())
        pim_config_id = self.pim_config_id
        categories = self.env['product.template'].get_product_data_preseli(pim_config_id)
        cr = self.env.cr
        cr.execute(
            """
            SELECT sub_reference, reference, result
            FROM queue_job
            WHERE state = 'process' AND model_id = %s AND pim_config_id = %s
            LIMIT 100
            """,
            (self.env.ref('product.model_product_template').id, pim_config_id.id)
        )
        rows = cr.fetchall()
        # Unzip into two separate lists
        sub_references, references, results = zip(*rows) if rows else ([], [], [])
        # Convert to lists
        sub_references = list(sub_references)
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
            templates = dict(cr.fetchall())
        product_attribute_dict = {}
        for result in results:
            self.process_single_product_result(result, templates, pim_config_id)
            if result.get('psli_Prices', []) and pim_config_id.printing_product:
                print_details = result.get('psli_Prices', [])
                main_product_name = result.get('psli_ProductName')
                self.process_print_product_for_preseli(result, pim_config_id, print_details,main_product_name)
        _logger.info("------END-------%s", datetime.now())

    def process_single_product_result(self,  result, templates, pim_config_id):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START-------PRESELI------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        model_code = result.get('rla_Style_Code')
        try:
            catalogue_list = result.get('psli_catalogueId')
            if catalogue_list and isinstance(catalogue_list, list) and len(catalogue_list) > 0:
                cat_id = catalogue_list[0].get('id')
                find_category_id = self.env['product.category'].search([('reference_id', '=', cat_id)], limit=1)
            else:
                find_category_id = None
        except Exception as e:
            _logger.warning("Error while processing product category: %s", str(e))
            find_category_id = None
        
        if not find_category_id:
            find_category_id = self.env['product.category'].search([('pim_config_id', '=', pim_config_id.id)], limit=1)
            if not find_category_id:
                _logger.info("No category exists. Creating fallback category 'All'.")
                find_category_id = self.env['product.category'].create({'name': 'All'})
        try:
            image_urls = json.loads(result.get('psli_Images') or '[]')
            main_image = next((url for url in image_urls if isinstance(url, str) and url), '')
        except Exception as e:
            _logger.warning("Invalid psli_Images or error decoding JSON: %s", str(e))
            main_image = ''

        standard_price = 0.0
        try:
            prices = result.get('psli_Prices', [])
            if prices and isinstance(prices, list) and prices:
                unbranded_found = False
                for price_block in prices:
                    if price_block.get('psli_Name', '').strip().lower() == 'unbranded':
                        price_details = price_block.get('psli_PriceDetails', [])
                        for price_item in price_details:
                            if price_item.get('Type') == 'Product':
                                standard_price = float(price_item.get('Value', 0.0))
                                unbranded_found = True
                                break
                        if unbranded_found:
                            break

                if not unbranded_found:
                    price_details = prices[0].get('psli_PriceDetails', [])
                    for price_item in price_details:
                        if price_item.get('Type') == 'Product':
                            standard_price = float(price_item.get('Value', 0.0))
                            break
        except Exception as e:
            _logger.warning("Failed to extract standard_price: %s", str(e))



        template_data.update({
            'product_add_mode': 'matrix',
            'is_storable': True,
            'categ_id': find_category_id.id,
            'standard_price': standard_price,
            'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)],
            'image_1920': base64.b64encode(requests.get(main_image, timeout=5).content).decode('utf-8') if main_image else '',

        })
        new_template = self.env['product.template'].create(template_data)
        templates[model_code] = new_template.id
        try:
            all_prices = result.get('psli_Prices', [])
            if all_prices:
                unbranded_blocks = [
                    block for block in all_prices
                    if block.get('psli_Name', '').strip().lower() == 'unbranded'
                ]

                skip_service_to_purchase = bool(unbranded_blocks)

                for block in unbranded_blocks:
                    quantity = block.get('psli_Quantity')

                    price_details = block.get('psli_PriceDetails', [])
            
                    product_price_detail = next(
                        (pd for pd in price_details if pd.get('Type') == 'Product'),
                        None
                    )
                    if product_price_detail:
                        self._process_pricelist_data_preseli(
                            new_template,
                            pim_config_id,
                            [product_price_detail],
                            quantity,
                            skip_service_to_purchase=skip_service_to_purchase
                        )
        except Exception as e:
            _logger.warning("Failed to find data: %s", str(e))

                
        existing_vendor = new_template.seller_ids.filtered(lambda v: v.partner_id.id == pim_config_id.partner_id.id)
        if not existing_vendor:
            new_template.write({
                'seller_ids': [(0, 0, {
                    'partner_id': pim_config_id.partner_id.id,
                })]
            })
        
        # --- VARIANT LOGIC ---
        template_id = templates.get(model_code)
        variants = self.env['product.product'].search([
            ('product_tmpl_id', '=', template_id)
        ], order='id desc')

        update_variant = variants[0].id if variants else False
        if update_variant:
            variant_data = template_data.copy()
            variant_data.update({
                'json_data_varaint': str(result),
            })
            variant = self.env['product.product'].browse(update_variant)
            variant.write(variant_data)
        self.env['queue.job'].search([('reference', '=', result.get('psli_ProductCode'))]).write({
            'state': 'done',
        })
        self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------PRESELI--------%s", datetime.now())

        
