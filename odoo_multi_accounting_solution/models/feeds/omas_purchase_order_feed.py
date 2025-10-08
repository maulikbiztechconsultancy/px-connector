# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger

from odoo import models

_logger = getLogger(__name__)

class OMASpurchaseorderFeed(models.Model):
    _name='omas.purchase.order.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Purchase Order Feeds'

    def _get_purchase_order_lines(self, purchase_order_lines):
        return list(map(self._get_purchase_order_line, purchase_order_lines))

    def _get_purchase_order_line(self, purchase_order_line):
        if purchase_order_line.get('line_source') == "discount":
            product_id = self.instance_id.discount_product_id
        elif purchase_order_line.get('line_source') == "delivery":
            product_id = self.instance_id.delivery_product_id
        else:
            product_id = self._get_odoo_product(purchase_order_line)
        if not product_id:
            if purchase_order_line.get('name'):
                message = '{} product not found.'.format(purchase_order_line['name'])
            elif purchase_order_line.get('default_code'):
                message = '{} product not found.'.format(purchase_order_line['default_code'])
            else:
                message = "product not found."
            raise Exception(message)
        else:
            return (0, 0, dict(
                product_id=product_id.id,
                product_qty=purchase_order_line.get("product_qty"),
                price_unit=purchase_order_line.get("price_unit"),
                name=purchase_order_line.get('name',False) or product_id.name,
                taxes_id = self.get_taxes_ids(purchase_order_line.get('line_taxes')) if purchase_order_line.get('line_taxes') else False
            ))

    def get_taxes_ids(self, taxes):
        taxes_ids = []
        if taxes:
            for tax in taxes:
                mapping = self.instance_id.match_tax_mapping(remote_id = tax.get('remote_id'))
                if mapping:
                    if not mapping.name:
                        raise UserWarning('Purchase Order tax mapping is exist but not mapped with any odoo tax')
                    taxes_ids.append(mapping.name.id)
                else:
                    amount = tax.get('rate')
                    name = tax.get('name')
                    amount_type = "percent"
                    if tax.get('type'):
                        amount_type = tax.get('type')
                    domain = [('name', '=', name),
                            ('amount_type', '=', amount_type),
                            ('amount', '=', amount),
                            ('price_include', '=', tax.get('include'))
                            ]
                    tx = self.env['account.tax'].search(domain, limit=1)
                    if not tx:
                        tx = self.env['account.tax'].create({
                            'name': name,
                            'amount_type': amount_type,
                            'price_include': tax.get('include'),
                            'amount': amount,
                            'type_tax_use': 'purchase',
                        })
                    if tx:
                        taxes_ids.append(tx.id)
                    if tx and tax.get('remote_id'):
                        match = self.instance_id.with_context(active_test = False).match_tax_mapping(remote_id = tax.get('remote_id'))
                        if match:
                            match.write({'name':tx.id, 'active':True})
                        else:
                            self.instance_id.create_tax_mapping(tx, tax.get('remote_id'), amount = amount, display_name=name)
        return [(6, 0, taxes_ids)]


    def create_entity(self):
        feed = self
        message = ''
        odoo_id = False
        instance_id = self.instance_id
        data = eval(feed.data)
        remote_id = feed.remote_id
        name = feed.name
        state = 'done'
        match = self._context.get('purchase_order_mappings').get(
            instance_id.id, {}).get(remote_id)
        partner_id = data.get('partner_id',False)
        order_lines = data.pop('order_lines',[])
        currency_code = data.pop('currency_code', False)
        order_state = data.pop('order_state', False)
        if instance_id.sync_purchase_order_name and data.get('origin'):                     ##PURCHASE ORDER NAME SYNC FROM ACCOUNTING SOFTWARE TO ODOO##
            data['name'] = data.get('origin')
        if instance_id.instance == 'xero':
            check_by_sku = True
        try:
            if partner_id:
                partner_id = instance_id.match_customer_mapping(remote_id = partner_id).mapped('name').id
                if partner_id:
                    data['partner_id'] = partner_id
                else:
                    state = "error"
                    message += '<br/>Partner is not mapped.\n'
                    if instance_id.debug:
                        _logger.info('Purchase Order Error #1 : Partner is not Mapped.')
                # data['invoice_partner_id'] = instance_id.match_customer_mapping(remote_id = partner_id,type='invoice').mapped('name').id or False
                # data['shipping_partner_id'] = instance_id.match_customer_mapping(remote_id = partner_id, type='shipping').mapped('name').id or False
            else:
                state = 'error'
                message += '<br/>Partner ID is Mandatory.\n'
                if instance_id.debug:
                    _logger.info('Purchase Order Error #1 : Partner ID is Mandatory.')
            if order_lines:
                order_lines = self._get_purchase_order_lines(order_lines)
                data['order_line'] = order_lines
            else:
                state='error'
                message += f'Order Line is Mandatory.\n'
                if instance_id.debug:
                    _logger.info('Purchase Order Error #2 : Order Line is Mandatory.')
            if currency_code:
                currency_id = instance_id.get_currency_id(currency_code)
                if not currency_id:
                    state = 'error'
                    id = self.env['res.currency'].with_context(active_test = False).search([('name','=',currency_code)],limit=1).id
                    action = self.env.ref('base.action_currency_form').id
                    # Created link to enable currency
                    message += f'<br/> Currency <a href="/web#id={id}&model=res.currency&action={action}&view_type=form" target = "_blank">{currency_code}</a> not active in Odoo'
                    _logger.error(f'Purchase Order Error #3 : Currency {currency_code} not active in Odoo.')
                else:
                    data['currency_id'] = currency_id.id
            if state == 'done':
                if match:
                    mapped_record = self.env['omas.purchase.order.mapping'].browse(match).name
                    if mapped_record.state=='draft':
                        mapped_record.write({'order_line':[(5,0)]})
                        mapped_record.write(data)
                    else:
                        _logger.warning('Purchase Order can be updated only in draft state.')
                    odoo_id = mapped_record
                    self.update_po_states(mapped_record, order_state)
                else:
                    odoo_id = self.env['purchase.order'].create(data)
                    self.update_po_states(odoo_id, order_state)
                    mapping_id =  instance_id.create_purchase_order_mapping(remote_id, odoo_id)
                message  += f'<br/> Purchase Order {remote_id} successfully evaluated'
        except Exception as e:
            state = 'error'
            message += f'Error in Evaluating Purchase Order Feed: {e}\n'
            if instance_id.debug:
                _logger.info(message)
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )

    def update_po_states(self, record, remote_state):
        if record.state == 'draft':
            if remote_state in ['sale', 'done']:
                record.button_confirm()
        if remote_state in ['cancelled', 'cancel'] and not record.state == 'cancel':
             record.button_cancel()
