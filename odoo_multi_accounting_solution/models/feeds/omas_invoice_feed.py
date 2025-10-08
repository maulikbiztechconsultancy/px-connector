# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models, fields

class OMASInvoiceFeed(models.Model):
    _name='omas.invoice.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Invoice Feeds'

    feed_move_type = fields.Selection([
		('in_invoice','Vendor Bill'),
		('in_refund', 'Refund'),
		('out_invoice','Customer Invoice'),
		('out_refund', 'Credit Note'),
	], default="out_invoice", string="Type", required=True)

    def _get_invoice_lines(self,  invoice_lines):
        return list(map(self._get_invoice_line, invoice_lines))

    def _get_invoice_line(self, invoice_line):
        discount = invoice_line.get('discount', False)
        if invoice_line.get('line_source') == "delivery":
            product_id = self.instance_id.delivery_product_id
        elif invoice_line.get('line_source') == 'discount':
            product_id = self.instance_id.discount_product_id
        else:
            product_id = self._get_odoo_product(invoice_line)
        if not product_id:
            if invoice_line.get('name'):
                message = f'{invoice_line["name"]} product  not found.'
            elif invoice_line.get('default_code'):
                message = f'{invoice_line["default_code"]} product not found.'
            else:
                message = "product not found."
            raise Exception(message)
        vals = dict(
            product_id = product_id.id,
            quantity = invoice_line.get("product_uom_qty"),
            price_unit = invoice_line.get("price_unit"),
            name = invoice_line.get('name', False) or product_id.name,
            tax_ids = self.get_taxes_ids(invoice_line.get('line_taxes')) if invoice_line.get('line_taxes') else False,
            discount = discount,
        )
        account_remote_id = invoice_line.get('account_remote_id', False)
        if account_remote_id:
            account_id = self.instance_id.match_account_mapping(remote_id=account_remote_id)
            if account_id and account_id.name:
                vals.update({'account_id': account_id.name.id})
        return (0, 0, vals)

    def get_taxes_ids(self, taxes):
        taxes_ids = []
        for tax in taxes:
            mapping = self.instance_id.match_tax_mapping(remote_id = tax.get('remote_id'))
            if mapping:
                if not mapping.name:
                    raise UserWarning(f"{(tax.get('name'))} Tax is not mapped with any Odoo Tax")
                taxes_ids.append(mapping.name.id)
            else:
                amount = tax.get('rate')
                name =  tax.get('name')
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
                    })
                if tx:
                    taxes_ids.append(tx.id)
                if tx and tax.get('remote_id'):
                    # Match all active & inactive records of tax mappings
                    match  = self.instance_id.with_context(active_test = False).match_tax_mapping(remote_id = tax.get('remote_id'))
                    if match:
                        match.write({'name':tx, 'active':True})
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
        state = 'done'
        set_paid = data.pop('set_paid', False)
        match = self._context.get('invoice_mappings').get(
            instance_id.id, {}).get(remote_id)
        partner_id = data.get('partner_id')
        invoice_lines = data.pop('invoice_lines',[])
        invoice_line_ids = False
        currency_code = data.pop('currency_code',False)
        invoice_state = data.pop('state',False)
        invoice_type = data.pop('type', 'out_invoice')
        try:
            data['move_type'] = invoice_type
            if partner_id:
                partner_id = instance_id.match_customer_mapping(remote_id = partner_id).mapped('name').id or False
                if partner_id:
                    data['partner_id'] = partner_id
                else:
                    state = "error"
                    message += '<br/>Partner is not mapped.\n'
                    if instance_id.debug:
                        _logger.info('Invoice Error #1 : Partner is not Mapped.') 
            else:
                state = 'error'
                message += '<br/>Partner ID is Mandatory.\n'
                if instance_id.debug:
                    _logger.info('Invoice Error #1 : Partner ID is Mandatory.')
            if invoice_lines:
                invoice_line_ids = self._get_invoice_lines(invoice_lines)
            else:
                state='error'
                message += f'Invoice Line is Mandatory.\n'
                if instance_id.debug:
                    _logger.info('Invoice Error #2 : Order Line is Mandatory.')
            if currency_code:
                currency_id = instance_id.get_currency_id(currency_code)
                if not currency_id:
                    state = 'error'
                    id = self.env['res.currency'].with_context(active_test = False).search([('name','=',currency_code)],limit=1).id
                    action = self.env.ref('base.action_currency_form').id
                    # Created link to enable currency
                    message += f'<br/> Currency <a href="/web#id={id}&model=res.currency&action={action}&view_type=form" target = _blank>{currency_code}</a> not active in Odoo'
                    _logger.error(f'Invoice Error #3 : Currency {currency_code} not active in Odoo.')
                else:
                    data['currency_id'] = currency_id.id
            data['team_id'] = instance_id.team_id.id
            if state=='done':
                if match:
                    mapped_record = self.env['omas.invoice.mapping'].browse(match).name
                    if mapped_record.state=='draft':
                        odoo_id = match
                        data.update({'invoice_line_ids':[(5, 0)]})
                        mapped_record.write(data)
                        if invoice_line_ids:
                            mapped_record.write({'invoice_line_ids': invoice_line_ids})
                        if set_paid:
                            mapped_record.action_invoice_register_payment()
                    else:
                        message += 'Invoice Only in draft state can be updated.'
                else:
                    data.update({'invoice_line_ids': invoice_line_ids})
                    odoo_id = self.env['account.move'].create(data)
                    if set_paid:
                        odoo_id.action_invoice_register_payment()
                    mapping_id =  instance_id.create_invoice_mapping(remote_id, odoo_id, type=invoice_type)
                message  += f'<br/> Invoice {remote_id} successfully evaluated'
        except Exception as e:
            state = 'error'
            message += f'Error in Evaluating Invoice Feed: {e}\n'
            if instance_id.debug:
                _logger.info(message)
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )
