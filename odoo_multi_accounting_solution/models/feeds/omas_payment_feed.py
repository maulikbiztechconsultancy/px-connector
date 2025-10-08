# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models

class OMASpaymentFeed(models.Model):
    _name='omas.payment.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Payment Feeds'

    def create_entity(self):
        feed = self
        message = ''
        odoo_id = False
        instance_id = self.instance_id
        data = eval(feed.data)
        remote_id = feed.remote_id
        name = feed.name
        state = 'done'
        payment_id = False
        match = self._context.get('payment_mappings').get(
            instance_id.id, {}).get(remote_id)
        partner_id = data.pop('partner_id','')
        if not data.get('partner_type'):
            data.update(partner_type='customer')
        if not data.get('payment_type'):
            data.update(payment_type = 'inbound')
        if data.get('payment_date'):
            date = data.get('payment_date')
            data.update({'date':date})
        if partner_id:
            data['partner_id'] = instance_id.match_customer_mapping(remote_id = partner_id).mapped('name').id or False
        else:
            message += '<br/>Partner ID is Mandatory.\n'
            state = 'error'
            if instance_id.debug:
                _logger.info('Payment Error #1 : Partner ID is Mandatory.')
        payment_method_id = instance_id.payment_method_id
        order_id = data.get('order_id','')
        invoice_ids = data.get('invoice_ids', '')
        if state == 'done':
            if order_id:
                order_id = instance_id.match_order_mapping(remote_id = order_id).name
                if order_id and order_id.invoice_ids:
                    invoice_id = order_id.invoice_ids[0]
                    payment_id, message = self.create_payment_and_post(payment_method_id, invoice_id)
            elif invoice_ids:
                if isinstance(invoice_ids, list):
                    for invoice_id in invoice_ids:
                        invoice_id = instance_id.match_invoice_mapping(remote_id = invoice_id).mapped('name') or False
                        if invoice_id:
                            if invoice_id.payment_state == "paid":
                                state = 'error'
                                message = f'Invoice {invoice_id.name} already paid'
                            else:
                                payment_id, message = self.create_payment_and_post(payment_method_id, invoice_id)
                        else:
                            state = 'error'
                            message = f"Error: Invoice is not mapped"
                            break
                else:
                    invoice_ids = instance_id.match_invoice_mapping(remote_id = invoice_ids).mapped('name') or False
                    if invoice_ids:
                        if invoice_ids.payment_state == "paid":
                            message = f'Invoice {invoice_ids.name} already paid'
                            state = 'error'
                        else:
                            payment_id, message = self.create_payment_and_post(payment_method_id, invoice_ids)
                    else:
                        state = 'error'
                        message = f"Error: Invoice is not mapped" 
            else:
                message += f'<br/> Payment Error #2 : Order ID or Invoice ID is mandatory. \n'
                state = 'error'
                if instance_id.debug:
                    _logger.info("Payment Error #2 : Order ID or Invoice ID is mandatory.")
        if payment_id:
            if not match:
                mapping_id = instance_id.create_payment_mapping(remote_id,payment_id)
        else:
            message = message if message else "Error: something went wrong"
            state = 'error'
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )
