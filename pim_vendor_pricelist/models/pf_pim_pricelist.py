# -*- coding: utf-8 -*
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
    _inherit = 'pimore.vender.config'

    def action_fetch_pimcore_product_data(self):
        """
           This method use for the add price lisr for PF Concept
        """
        for pim in self:
            # Build method name dynamically
            if pim.update_product:
                method_name = "%s_get_pricelist" % pim.vendor_short_code.lower()
                method = getattr(pim, method_name, None)
                return method()
            else:
                super(PimoreVendorConfig, pim).action_fetch_pimcore_product_data()

    def pf_get_pricelist(self):
        for record in self:
            headers = {
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/json",
                "X-API-Key": record.api_key,
            }
            url = record.endpoint_url
            new_query = record.update_query.split('(')
            new_query_i = new_query[1].split(')')
            new_query_ii = new_query[1].split(')')
            total_remaining_values = self.total_remaining_values 
            final_query = new_query[0] + '(' + 'first:'+str(self.get_limit)+', after:' + str(total_remaining_values)+ ')' + new_query_i[1]


            payload = {
                "query": final_query.strip()
            }

            model = self.env['ir.model'].search([('model', '=', 'product.pricelist')], limit=1).id
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
                                        self.insert_with_cr('Update Pricelist', self.env.user.id, model, data_queue.get('node'))
                    self.total_remaining_values += self.get_limit
                    if self.total_remaining_values >= self.total_values:
                        self.last_synced_date = datetime.now()
                else:
                    raise Exception(f"Failed to fetch data. Status: {response.status_code}")
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

    
            