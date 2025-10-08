# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models, api

class OMASproductFeed(models.Model):
    _name='omas.product.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Product Feeds'


    def create_entity(self):
        feed = self
        message = ''
        odoo_id = False
        name = feed.name
        remote_id = feed.remote_id
        instance_id = self.instance_id
        data = eval(feed.data)
        qty_available = data.pop('qty_available', False)
        location_id = instance_id.location_id
        state = 'done'
        match = self._context.get('product_mappings').get(
            instance_id.id, {}).get(remote_id)
        context = self._context.copy()
        context.update({
            'pricelist':instance_id.pricelist_id.id,
            'lang':instance_id.language_id.code,
        })
        variants = data.pop('variants',[])
        if not data.get('name'):
            message += "<br/>Product name is Mandatory.\n"
            state = 'error'
        if not remote_id:
            message += "<br/>Remote ID is Mandatory.\n"
            state = 'error'
        categ_id = instance_id.default_category_id.id
        if categ_id:
            data['categ_id'] = categ_id
        # dimensions_unit = data.pop('dimensions_unit')
        # if dimensions_unit:
        # 	data['dimensions_uom_id'] = instance_id.get_uom_id(name=dimensions_unit).id
        # variants = data.pop('variants')
        # if variant_lines:
        # 	check_attr = self.check_attribute_value(feed_variants)
        # 	state = check_attr.get('state')
        # 	message+=check_attr.get('message')
        # image_url = data.pop('image_url','')
        # location_id = channel_id.location_id
        # if not b64_image and image_url and (image_url not in ['false','False',False]):
        # 	image_res = channel_id.read_website_image_url(image_url)
        # 	if image_res:
        # 		data['image_1920'] = image_res
        template_exists_odoo = instance_id.match_odoo_template(data)
        try:
            if state == 'done':
                if match:
                    match = self.env['omas.template.mapping'].browse(match)
                    if not template_exists_odoo:
                        template_id = match.name
                    else:
                        template_id = template_exists_odoo
                    if variants:
                        pass
                    else:
                        match_product = self._context.get('variant_mappings',{}).get(instance_id.id,{}).get(remote_id)
                        if not match_product:
                            instance_id.create_product_mapping(remote_id, remote_id, template_id.product_variant_id)
                    match.name.with_context(context).write(data)
                    odoo_id = match
                else:
                    template_id = False
                    if template_exists_odoo:
                        template_id = template_exists_odoo
                    else:
                        template_id = self.env['product.template'].with_context(context).create(data)
                    odoo_id = template_id
                    template_mapping_id = instance_id.create_template_mapping(remote_id, template_id)
                    variant_mapping_id = instance_id.create_product_mapping(remote_id, remote_id, template_id.product_variant_id)
                if not template_exists_odoo:
                    self.wk_change_product_qty(template_id.product_variant_id, qty_available, location_id)
        except Exception as e:
            state = 'error'
            message += f'Error in Evaluating Product Feed: {e}\n'
            if instance_id.debug:
                _logger.info(message)
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )

    @api.model
    def wk_change_product_qty(self,product_id,qty_available, location_id):
        quant = self.env['stock.quant']    
        if qty_available and product_id.type=='product':
            quant.with_context(
                inventory_mode=True,
                inventory_report_mode=True
            ).create(
                {
                    'product_id': product_id.id,
                    'location_id': location_id.id,
                    'inventory_quantity': qty_available,
                }
            )
            quant.action_apply_inventory()
