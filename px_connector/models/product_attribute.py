from odoo import api, exceptions, fields, models, _
import requests
import json


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    code_refrence = fields.Char(string="Model Code")


class AttributeMapping(models.Model):
    _name = "attribute.mapping"
    _description = "Attribute Mapping"

    name = fields.Char(string="End-Point", required=True)
    attribute_id = fields.Many2one('product.attribute', string="Attribute")
    supplier_id = fields.Many2one('supplier.configuration', string="Supplier")
    option_query_text = fields.Text()

    def get_options_supplier(self):
        """
            This method use for Get attribute options form supplier.
        """
        attribuet_values = []
        for attribuet in self.attribute_id.value_ids:
            attribuet_values.append(attribuet.name.lower())
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": '*/*',
                "SupplierCode": supplier.supplier_id.vendor_short_code,
                "Authorization": supplier.supplier_id.authorization_id.token,
            }
            url = supplier.supplier_id.authorization_id.url + supplier.supplier_id.get_endpoint
            payload = {
                         "query": supplier.option_query_text
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    option_json = response.json()
                    new_options = []
                    for values in option_json.get('data').get('data').get('options'):
                        for value in option_json.get('data').get('data').get('options').get(values):
                            if value.get('value').lower() not in attribuet_values:
                                new_options.append({
                                    'name': value.get('value'),
                                    'code_refrence': value.get('key'),
                                    'attribute_id': supplier.attribute_id.id
                                    })
                    if new_options:
                        self.env['product.attribute.value'].create(new_options)
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")
