from odoo import models, fields, api, Command
import xmlrpc.client
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _inherit = "queue.job"

    def get_product_data(self, pim_config_id):
        cr = self.env.cr
        attribute_ids = pim_config_id.attribute_line_fields.attribute_id.ids
        # Use %s with tuple or list
        cr.execute(
            "SELECT code_refrence, name, id, attribute_id FROM product_attribute_value WHERE attribute_id IN %s",
            (tuple(attribute_ids),)
        )
        attribute_values = {
            row[0]: {
                'name': row[1],
                'id': row[2],
                'attribute_id': row[3]
            }
            for row in cr.fetchall()
        }
        cr.execute("""
    		SELECT reference_id, id FROM product_category WHERE pim_config_id = %s
    	""", (pim_config_id.id,))
        categories = {
            row[0]: {
                'id': row[1],
            } for row in cr.fetchall()
        }
        return attribute_values, categories

    def midocean_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def midocean_product_import_data(self):
        _logger.info("-\n\n------START------%s", datetime.now())
        pim_config_id = self.pim_config_id
        attribute_values, categories = self.get_product_data(pim_config_id)
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
            templates = dict(cr.fetchall())
        product_attribute_dict = {}
        for result in results:
            if result.get('mid_product_name'):
                self.process_single_product_result_midocean(result, templates, attribute_values, categories, pim_config_id, product_attribute_dict)
        _logger.info("------END-------%s", datetime.now())

    def process_single_product_result_midocean(self, result, templates, attribute_values, categories, pim_config_id, product_attribute_dict):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        master_code = result.get('mid_master_code')

        if master_code not in templates:
            cat_code = result.get('mid_category')[0].get('code')
            cat_id = categories.get(cat_code, {}).get('id')
            template_data.update({
                'product_add_mode': 'matrix',
                'is_storable': True,
                'categ_id': cat_id if cat_id else False,
                'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
            })
            new_template = self.create_row_product_template(template_data)
            templates[master_code] = new_template.id
        
        self.process_product_attributes_for_midocean(result, templates, attribute_values, product_attribute_dict)

        # --- VARIANT LOGIC ---
        template_id = self.env['product.template'].browse(int(templates.get(master_code)))
        variants = template_id.product_variant_ids

        update_variant = variants[0] if variants else self.env['product.product']
        attribute_color = result.get('mid_color_description')
        if attribute_color:
            attribute_color_data = attribute_values.get(attribute_color)
            for variant in variants:
                value_ids = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.id')
                if attribute_color_data and attribute_color_data['id'] in value_ids:
                    update_variant = variant

        if update_variant:
            if result.get('mid_printing_positions', []) and pim_config_id.printing_product:
                print_details = result.get('mid_printing_positions', [])
                self.process_print_product_for_midocean(result, update_variant, pim_config_id, print_details)
            if result.get('mid_price', []):
                self._process_pricelist_midocean_row_product_data(update_variant, pim_config_id, result)
            variant_data = template_data.copy()
            variant_data.update({
                'default_code': result.get('mid_varient_sku'),
                'json_data_varaint': str(result),
            })
            assets = result.get("mid_varient_digital_assets")
            if assets:
                front_image = next((asset for asset in assets if asset.get("mid_subtype") == "item_picture_front"), None)
                if front_image:
                    image_url = front_image.get("mid_url") or front_image.get("mid_url_highress")
                    if image_url:
                        variant_data.update({'image':front_image.get("mid_url")})
                        image_data = self._get_image_data(image_url)
                        variant_data.update({'image_1920': image_data})

            update_variant.write(variant_data)
        self.env['queue.job'].search([('sub_reference', '=', result.get('mid_varient_sku'))]).write({
            'state': 'done',
            'records': update_variant.id
        })
        self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())

    def process_product_attributes_for_midocean(self, result, templates, attribute_values, product_attribute_dict):
        master_code = result.get('mid_master_code')
        template_id = templates.get(master_code)

        for attr_data in ['mid_color_description']:
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
