from odoo import api, exceptions, fields, models, _, Command
import logging
import json
import requests
import base64

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def set_product_pf_concept(self, job, supplier_id, record=False):
        """
            Creating product Varinat Based on set values.
        """
        image_url = False
        if 'images' in job.result.get('media'):
            images_dicts= job.result.get('media').get('images')
            for images_dict in images_dicts:
                if images_dict.get('type') == "imageMain":
                    image_url = images_dict.get('url')
        image_data = False
        if image_url:
            response = requests.get(image_url)
            if response.ok:
                image_data = base64.b64encode(response.content).decode('utf-8')
        price_list = []
        vendor_price_list = []
        cost = 0.0
        main_price = 0.0
        for price_details in job.result.get('pricing').get('pricelist'):
            price = price_details.get('gross') + (price_details.get('gross') * supplier_id.pricelist_margin)/100
            final_price = self._get_currency_convert_amount(supplier_id.currency_id,float(price),supplier_id.converted_currency_id)

            price_list.append({
                'min_quantity': price_details.get('min'),
                'fixed_price': final_price,
                'price': final_price,
                'currency_id': supplier_id.converted_currency_id.id,
                'applied_on': '0_product_variant'
                })
            if main_price == 0.0:
                main_price = final_price
            if cost == 0.0:
                cost = price_details.get('gross')
            vendor_price_list.append({
                                'partner_id': supplier_id.partner_id.id,
                                'min_qty': price_details.get('min'),
                                'price': price_details.get('gross'),
                                'currency_id': supplier_id.currency_id.id,
                            })
        template_dict = {
        'name': job.result.get('product').get('templateTitle'),
        'description': job.result.get('product').get('description'),
        'description_ecommerce': job.result.get('product').get('description'),
        'description_sale': job.result.get('product').get('description'),
        'description_purchase': job.result.get('product').get('description'),
        'website_description': job.result.get('product').get('description'),
        'type': 'consu',
        'product_service_type': 'finished',
        'template_code': job.result.get('templateCode'),
        'supplier_id': supplier_id.id,
        'website_description': job.result.get('product').get('description'),
        'route_ids': [Command.link(self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False).id)]
        }
        varinat_dict = {
        'name': job.result.get('product').get('templateTitle'),
        'item_code': job.result.get('itemCode'),
        'default_code': json.dumps(job.result.get('sku')),
        'standard_price': cost,
        'list_price': main_price,
        'description': job.result.get('product').get('description'),
        'description_ecommerce': job.result.get('product').get('description'),
        'description_sale': job.result.get('product').get('description'),
        'description_purchase': job.result.get('product').get('description'),
        'website_description': job.result.get('product').get('description'),
        'raw_json': json.dumps(job.result, indent=3),
        'printing_json': json.dumps(job.result.get('printing'), indent=3),
        'shipping_json': '',
        'image_1920': image_data,
        'supplier_id': supplier_id.id,
        }
        category = False
        for categorie in job.result.get('categories'):
            if not category:
                category = self.env['product.category'].search([('name', '=', categorie.get('name'))], limit=1)
        if category:
            template_dict.update({'categ_id': category.id})
        if 'stockManagement' in job.result:
            varinat_dict.update({'stock_location_ids': [(0,0, {
                'name': job.result.get('stockManagement').get('stockLocation'),
                'qty': job.result.get('stockManagement').get('currentStock')
                })]})
        size_attribute = False
        color_attribute = False
        if job.result.get('variantAttributes').get('size'):
            size_attribute = self.env['product.attribute.value'].search([('name', 'ilike', job.result.get('variantAttributes').get('size')),('attribute_id', '=', 13)], limit=1)

        if job.result.get('variantAttributes').get('color'):
            color_attribute = self.env['product.attribute.value'].search([('name', 'ilike', job.result.get('variantAttributes').get('color').get('name')),('attribute_id', '=', 7)], limit=1)

        if job.result.get('complianceSustainability').get('co2Totale'):
            varinat_dict.update({'carbon_co2': job.result.get('complianceSustainability').get('co2Totale')})

        template = self.env['product.template'].search([('template_code', '=', job.result.get('templateCode'))], limit=1)
        if not template and not template.id:
            template = self.env['product.template'].create(template_dict)
        # template.attribute_line_ids
        if color_attribute:
            color_attr_line = template.attribute_line_ids.filtered(
                lambda line: line.attribute_id.id == 7
            )
            if color_attr_line and color_attr_line.id:
                color_attr_line.value_ids = [(4, color_attribute.id)]
            else:
                template.attribute_line_ids = [(0, 0, {
                    'attribute_id': 7,
                    'value_ids': [(4, color_attribute.id)]
                    })]
        if size_attribute:
            size_attr_line = template.attribute_line_ids.filtered(
                lambda line: line.attribute_id.id == 13
            )
            if size_attr_line and size_attr_line.id:
                size_attr_line.value_ids = [(4, size_attribute.id)]
            else:
                template.attribute_line_ids = [(0, 0, {
                    'attribute_id': 13,
                    'value_ids': [(4, size_attribute.id)]
                    })]
        expected_value_ids = []
        if color_attribute:
            expected_value_ids.append(color_attribute.id)
        if size_attribute:
            expected_value_ids.append(size_attribute.id)

        variants = template.product_variant_ids
        matching_variant = variants  # Default to all variants
        for variant in template.product_variant_ids:
            variant_value_ids = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id.id')
            if sorted(variant_value_ids) == sorted(expected_value_ids):
                matching_variant = variant
                break
        # Optional: Get first variant
        variant = matching_variant[0] if matching_variant else None
        if matching_variant:
            variant_update = matching_variant[0]  # Assuming one match
            variant_update.update_sale_price_list(price_list)
            variant_update.update_vendor_price_list(vendor_price_list)
            variant_update.write(varinat_dict)
            job.write({
            'mapping_record': variant_update.id,
            'state': 'done'
            })
        else:
            job.write({
            'error_reason': "Product Not Found",
            'state': 'fail'
            })
