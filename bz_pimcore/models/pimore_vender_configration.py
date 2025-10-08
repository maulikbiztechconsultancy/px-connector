from odoo import models, fields, api
import requests
import json
import xmlrpc.client
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)


class IrModelFieldsInherit(models.Model):
    _inherit = 'ir.model.fields'

    @api.depends('name', 'ttype')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} ({rec.ttype})"


class ProductFieldLine(models.Model):
    _name = 'product.field.line'
    _description = 'Product Field Line'

    config_id = fields.Many2one('pimore.vender.config', string='Vendor Config', ondelete='cascade')
    product_field_id = fields.Many2one(
        'ir.model.fields',
        string="Product Field",
        domain="[('model', '=', 'product.template'), ('store', '=', True)]"
    )
    custom_value = fields.Char(string="Custom Value")


class VariantFieldLine(models.Model):
    _name = 'variant.field.line'
    _description = 'Variant Field Line'

    config_id = fields.Many2one('pimore.vender.config', string='Vendor Config', ondelete='cascade')
    variant_field_id = fields.Many2one(
        'ir.model.fields',
        string="Variant Field",
        domain="[('model', '=', 'product.product'), ('store', '=', True)]"
    )
    custom_value = fields.Char(string="Custom Value")

class CategoryFieldLine(models.Model):
    _name = 'category.field.line'
    _description = 'Category Field Line'

    config_id = fields.Many2one('pimore.vender.config', string='Vendor Config', ondelete='cascade')
    product_category_field_id = fields.Many2one(
        'ir.model.fields',
        string="Category Field",
        domain="[('model', '=', 'product.public.category'), ('store', '=', True)]"
    )
    custom_value = fields.Char(string="Custom Value")

class AttributeLineFieldLine(models.Model):
    _name = 'attribute.line.field.line'
    _description = 'Attribute Line Field'

    config_id = fields.Many2one('pimore.vender.config', string='Vendor Config', ondelete='cascade')
    attribute_id = fields.Many2one(
        'product.attribute',
        string="Attribute")
    custom_link = fields.Char(string="Get Class Link")

    def set_attibute_values(self):
        headers = {
            "Cookie": "PHPSESSID=ced2ebb1cf13b117230701e1e30314c7",
            "Content-Type": "application/json",
            "X-API-Key": self.config_id.general_api_key,
        }
        url = self.custom_link
        payload = {}
 
        try:
            response = requests.get(url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                data = response.json()
                prepar_queue = {}
                if 'data' in data:
                    for data_queue in data.get('data'):
                        if 'options' in data_queue:
                            set_values = []
                            for options in data_queue.get('options'):
                                value_dict = {
                                        'name': str(options.get('key')),
                                        'code_refrence': str(options.get('value')),
                                        }
                                existing_attribute = self.env['product.attribute.value'].search([('attribute_id', '=', self.attribute_id.id), ('code_refrence', '=', str(options.get('value')))])
                                if existing_attribute and existing_attribute.id:
                                    existing_attribute.write(value_dict)
                                else:
                                    set_values.append((0,0, value_dict))
                            if set_values:
                                self.attribute_id.write({
                                    'value_ids': set_values
                                    })
            else:
                raise Exception(f"Failed to fetch data. Status: {response.status_code}")
        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")