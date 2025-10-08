from odoo import models, fields, api
from graphql import parse, GraphQLError 
import requests
import json
import xmlrpc.client
from odoo.http import request
from datetime import datetime
from odoo.exceptions import UserError
import base64
import logging
_logger = logging.getLogger(__name__)

class PimoreVendorConfig(models.Model):
    _name = 'pimore.vender.config'
    _description = 'Pimcore Vendor Configuration'

    name = fields.Char(string='Vendor Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Access PIM
    general_api_key = fields.Char(string='General API Key', copy=False)
    api_key = fields.Char(string='API Key', copy=False)
    endpoint_url = fields.Char(string='Pimcore URL', copy=False)

    # Attribute Configuration
    attribute_line_fields = fields.One2many(
        'attribute.line.field.line',
        'config_id',
        string="Attribute Line Fields"
    )

    # Category Configuration
    query_text = fields.Text(string="Category Query", copy=False)
    category_relation_ids = fields.One2many(
        'product.category.relation',
        'config_id',
        string="Variant Field Values"
    )
    category_field_lines = fields.One2many(
        'category.field.line',
        'config_id',
        string="Category Field Lines"
    )

    # Product Configuration
    product_query_text = fields.Text(string="Product Query", copy=False)
    product_field_lines = fields.One2many(
        'product.field.line',
        'config_id',
        string="Product Field Values"
    )
    get_limit = fields.Integer('Get Limit')
    total_values = fields.Integer('Total Data')
    total_remaining_values = fields.Integer('Remaining Datas')
    next_schedule_date = fields.Date('Next Schedule Date')
    partner_id = fields.Many2one('res.partner', string="Supplier")
    create_pricelist = fields.Selection([
        ('sales', 'Sales Pricelist'),
        ('vendor', 'Vendor Pricelist'),
        ('both', 'Both Pricelist'),
    ], string="Create Pricelist",default='sales')
    sale_margin = fields.Float('Sales Margin')

    @api.onchange('query_text')
    def _onchange_query(self):
        if self.query_text:
            try:
                parse(self.query_text)
                UserError("GraphQL Query is valid!")
            except GraphQLError as e:
                UserError("Invalid GraphQL Query:", e)

    @api.onchange('product_query_text')
    def _onchange_product_query(self):
        if self.product_query_text:
            try:
                parse(self.product_query_text)
            except GraphQLError as e:
                UserError("Invalid GraphQL Query:", e)
    
    def action_fetch_pimcore_data(self):
        for record in self:
            headers = {
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/json",
                "X-API-Key": record.api_key,
            }
            url = record.endpoint_url
            payload = {
                "query": record.query_text.strip()
            }
            model = self.env['ir.model'].search([('model', '=', 'product.public.category')], limit=1).id
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    data = response.json()
                    prepar_queue = {}
                    for datas in data:
                        for category_list in data.get(datas):
                            for edges in data.get(datas).get(category_list):
                                if edges == 'totalCount':
                                    pass
                                else:
                                    for data_queue in data.get(datas).get(category_list).get(edges):
                                        self.insert_with_cr('Create Category', self.env.user.id, model, data_queue.get('node'))
                    # if 'data' in data and 'getPFCategoryListing' in data.get('data') and 'edges' in data.get('data').get('getPFCategoryListing'):
                    #     for data_queue in data.get('data').get('getPFCategoryListing').get('edges'):
                    #         self.insert_with_cr('Create Category', self.env.user.id, model, data_queue.get('node'))
                else:
                    raise Exception(f"Failed to fetch data. Status: {response.status_code}")
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

    @api.model
    def insert_with_cr(self, name, user_id, models, result):
        cr = self._cr  # Get cursor
        priority = 0
        result_json = json.dumps(result)
        # Example insert query
        reference, sub_reference = '' , ''
        if name == 'Create Category':
            reference = result.get('catCode') or result.get('code') or False
            if 'parent_category' in result:
                priority = len(result.get('parent_category').split(",")) if result.get('parent_category') else 0
        elif name == "Create Product":
            reference = result.get('modelCode') or result.get('lt_ProductCode')
            sub_reference = result.get('itemCode') or result.get('lt_ItemCode')
        cr.execute("""
            INSERT INTO queue_job (name, user_id, pim_config_id, company_id, model_id, state, result, reference, sub_reference, priority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, user_id, self.id, self.env.company.id, models, 'process', result_json, reference, sub_reference, priority))
        # Commit if needed (use cautiously in Odoo)
        self.env.cr.commit()

    def action_fetch_pimcore_product_data(self):
        for record in self:
            headers = {
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/json",
                "X-API-Key": record.api_key,
            }
            url = record.endpoint_url
            new_query = record.product_query_text.split('(')
            new_query_i = new_query[1].split(')')
            new_query_ii = new_query[1].split(')')
            total_remaining_values = self.total_remaining_values 
            final_query = new_query[0] + '(' + 'first:'+str(self.get_limit)+', after:' + str(total_remaining_values)+ ')' + new_query_i[1]


            payload = {
                "query": final_query.strip()
            }

            model = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1).id
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    data = response.json()
                    prepar_queue = {}
                    for datas in data:
                        for product_list in data.get(datas):
                            for edges in data.get(datas).get(product_list):
                                if edges == 'totalCount':
                                    pass
                                else:
                                    for data_queue in data.get(datas).get(product_list).get(edges):
                                        self.insert_with_cr('Create Product', self.env.user.id, model, data_queue.get('node'))
                    # if 'data' in data and 'getPFProductsListing' in data.get('data') and 'edges' in data.get('data').get('getPFProductsListing'):
                    #     for data_queue in data.get('data').get('getPFProductsListing').get('edges'):
                    #         self.insert_with_cr('Create Product', self.env.user.id, model, data_queue.get('node'))
                    self.total_remaining_values += self.get_limit
                else:
                    raise Exception(f"Failed to fetch data. Status: {response.status_code}")
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")
