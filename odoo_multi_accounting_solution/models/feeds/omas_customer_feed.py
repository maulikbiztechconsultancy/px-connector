# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models

class OMASCustomerFeed(models.Model):
	_name='omas.customer.feed'
	_inherit = 'omas.feed'
	_description = 'OMAS Customer Feeds'


	def create_entity(self):
		feed=self
		message = ''
		odoo_id = False
		name = feed.name
		remote_id = feed.remote_id
		instance_id = feed.instance_id
		data = eval(feed.data)
		contacts = data.pop('contacts', False)
		state = 'done'
		type = data.get('type')
		if data.get('company_type'):
			company_type = data.pop('company_type')
			if company_type == 'company':
				data['company_type'] = company_type
		customer_type = data.pop('customer_type', 'customer')
		if customer_type in ['supplier', 'vendor']:
			customer_type = 'vendor'
			data.update({'supplier_rank': 1})
		else:
			data.update({'customer_rank': 1})
		match = self._context.get('customer_mappings').get(
			instance_id.id, {}).get(remote_id)
		if not name:
			message+="<br/>Name field is required."
			state = 'error'
		country_id = data.pop('country_id', False)
		if country_id:
			country_id = instance_id.get_country_id(country_id)
			if country_id:
				data['country_id'] = country_id.id
		state_id = data.pop('state_id', False)
		state_name = data.pop('state_name', False)
		state_code = data.pop('state_code', False)
		if (state_id or state_name) and country_id:
			state_id = instance_id.get_state_id(state_id,country_id,state_name)
			if state_id:
				data['state_id'] = state_id.id
		try:
			if state == 'done':
				if match:
					mapped_record = self.env['omas.customer.mapping'].browse(match)
					odoo_id = mapped_record.name
					odoo_id.write(data)
					if odoo_id.name and contacts:
						for contact in contacts:
							contact.update({'parent_id': odoo_id.id})
							self.with_context(customer_type=customer_type).create_res_partner(contact, remote_id)
				else:
					odoo_id = self.create_res_partner(data)
					mapping_id = instance_id.create_customer_mapping(remote_id, odoo_id, type=type, customer_type=customer_type)
					if odoo_id and contacts:
						for contact in contacts:
							contact.update({'parent_id': odoo_id.id})
							self.with_context(customer_type=customer_type).create_res_partner(contact, remote_id)
				message += f'<br/>Customer {name} successfully evaluated.'
		except Exception as e:
			message += f'Error in Evaluating Customer Feed: {e}\n'
			if instance_id.debug:
				_logger.info(message, exc_info=True)
			state = 'error'
		return dict(
			state=state,
			odoo_id=odoo_id,
			message=message
		)

	def create_res_partner(self, data, remote_id=False): # pass remote_id only in case of child customers creation
		country_id = False
		state_id = False
		try:
			country_code = data.pop('country_code',False)
			country_name = data.pop('country_name',False)
			state_code = data.pop('state_code',False)
			state_name = data.pop('state_name',False)
			customer_type=self._context.get('customer_type')
			type = data.get('type', 'other')
			if country_code:
				country_id = self.env['omas'].get_country_id(country_code)
				data.update({'country_id':country_id.id})
			if state_code:
				state_id = self.env['omas'].get_state_id(state_code, country_id)
				if state_id:
					data.update({'state_id':state_id.id})
			elif state_name and country_id:
				state_id = country_id.state_ids.filtered(lambda st:(st.name == state_name))
				if state_id:
					data.update({'state_id':state_id.id})
			if not customer_type: # parent customer
				odoo_id = self.env['res.partner'].create(data)
			else: # child customer
				if remote_id and customer_type:
					remote_id = str(type)+'_'+str(remote_id)
					match = self._context.get('customer_mappings').get(
         						self.instance_id.id, {}).get(remote_id)
					if match:
						mapped_record = self.env['omas.customer.mapping'].browse(match)
						odoo_id = mapped_record.name
						odoo_id.write(data)
					else:
						odoo_id = self.env['res.partner'].create(data)
						self.instance_id.create_customer_mapping(remote_id, odoo_id, type=type, customer_type=customer_type)
			return odoo_id
		except:
			return False
