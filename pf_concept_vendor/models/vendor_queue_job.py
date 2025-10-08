# -*- coding: utf-8 -*
from odoo import models, fields, api, Command
import xmlrpc.client
from datetime import datetime
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    _inherit = "queue.job"

    def pf_concept_category_import_data(self):
        self.env['product.category'].create_queue_record_create(job_queue=self)

    def pf_concept_product_import_data(self):
        _logger.info("-\n\n------START------%s", datetime.now())
        pim_config_id = self.pim_config_id
        attribute_values, categories = self.env['product.template'].get_product_data(pim_config_id)
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
            self.process_single_product_result(result, templates, attribute_values, categories, pim_config_id, product_attribute_dict)
        _logger.info("------END-------%s", datetime.now())

    def process_product_attributes(self, result, templates, attribute_values, product_attribute_dict):
        model_code = result.get('modelCode')
        template_id = templates.get(model_code)

        for attr_name in ['color', 'size']:
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

    def process_single_product_result(self, result, templates, attribute_values, categories, pim_config_id, product_attribute_dict):
        _logger.info("-\n\n------SINGLE RAW PRODUCT START------%s", datetime.now())
        template_data = self.env['product.template'].get_product_template_data(result, pim_config_id)
        model_code = result.get('modelCode')

        if model_code not in templates:
            cat_code = result.get('categoryData')[0].get('catCode')
            cat_id = categories.get(cat_code, {}).get('id')
            template_data.update({
                'product_add_mode': 'matrix',
                'is_storable': True,
                'categ_id': cat_id if cat_id else 1,
                'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
            })
            new_template = self.create_row_product_template(template_data)
            templates[model_code] = new_template.id

        self.process_product_attributes(result, templates, attribute_values, product_attribute_dict)

        template_id = self.env['product.template'].browse(int(templates.get(model_code)))
        variants = template_id.product_variant_ids
        if result.get('printData', []) and pim_config_id.printing_product:
            print_details = result.get('printData', [])
            self.process_print_product(result, variants ,pim_config_id, print_details)

        update_variant = variants[0] if variants else self.env['product.product']
        attribute_color = result.get('color')
        if attribute_color:
            attr_key = '_'.join(attribute_color) if isinstance(attribute_color, list) else attribute_color
            attribute_color_data = attribute_values.get(attr_key)
            for variant in variants:
                value_ids = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.id')
                if attribute_color_data and attribute_color_data['id'] in value_ids:
                    update_variant = variant

        if update_variant:
            if result.get('pricing', []):
                self._process_pricelist_row_product_data(update_variant, pim_config_id, result.get('pricing', []))
            variant_data = template_data.copy()
            variant_data.update({
                'default_code': result.get('itemCode'),
                'json_data_varaint': str(result),
            })
            if result.get("imageMain"):
                image_data = self._get_image_data(result.get("imageMain"))
                variant_data.update({'image_1920': image_data})

            stock_location = result.get('stockLocation')
            stock_quantity = result.get('stockDirect')
            if stock_location and stock_quantity:
                self._update_stock_location(update_variant.id, stock_location, float(stock_quantity))

            update_variant.write(variant_data)

            self.env['queue.job'].search([('sub_reference', '=', result.get('itemCode'))], limit=1).write({
                'state': 'done',
                'records': update_variant.id
            })
            self.env.cr.commit()
        _logger.info("-\n\n------SINGLE RAW PRODUCT END------%s", datetime.now())
