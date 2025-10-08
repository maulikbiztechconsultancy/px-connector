# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models, fields, api

class OMASFeed(models.Model):
    _name='omas.feed'
    _description = 'Base Feed for Odoo Multi-Accounting Solution'

    name = fields.Char()
    remote_id = fields.Char('Remote ID')
    instance_id = fields.Many2one(comodel_name='omas', string='Instance Id')
    instance = fields.Selection(related='instance_id.instance')
    data = fields.Text()
    message = fields.Html('Message',default='',copy=False)
    logs = fields.Text()
    state = fields.Selection([
        ('draft','Draft'),
        ('done','Done'),
        ('error','Error')
    ], default='draft')

    @api.model
    def create_feeds(self, datalist, kwargs={})->list:
        instance_id = self._context.get('instance_id')
        auto_evaluate_feed = instance_id.auto_evaluate_feed
        import_type = self._context.get('import_type')
        if auto_evaluate_feed:
            self = self.contextualize_mappings(instance_ids = instance_id.ids)
        ids = list(map(self.with_context(self._context,
                                         auto_evaluate_feed=auto_evaluate_feed,
                                         import_type = import_type,
                                         )._create_feed, datalist))
        len_ids = len(ids)
        ids = list(filter(lambda x: x, ids))
        kwargs['feed_count'] = len_ids - len(ids)
        return ids, kwargs

    def _create_feed(self, data)->int:
        remote_id, feed_id = data.pop('remote_id', False), False
        instance_id = data.pop('instance_id')
        data = {
            'name':data.get('name',''),
            'remote_id':remote_id,
            'instance_id': instance_id,
            'data': data
        }
        if self._name == 'omas.invoice.feed':
            feed_move_type = data.get('data').get('type', 'out_invoice')
            data.update({'feed_move_type': feed_move_type})
        if self._context.get('import_type'):
            data.update({'import_type':self._context.get('import_type')})
        feed = self.search([('instance_id','=',instance_id),('remote_id','=',remote_id)],limit = 1)
        try:
            if feed:
                feed.write(data)
                feed_id = feed.id
            else:
                feed = self.create(data)
                feed_id = feed.id
        except Exception as e:
            _logger.error(
                "Failed to create feed for Collection: "
                f"{data.get('remote_id')}"
                f" Due to: {e.args[0]}"
            )
        if self._context.get('auto_evaluate_feed') and feed:
            res = self.evaluate_feed(feed)
            if res.get('state') == 'error':
                feed_id = False
        return feed_id
    
    def _get_odoo_product(self,order_line):
        product_env = self.env['omas.product.mapping']
        instance_id = self.instance_id
        if instance_id.instance == 'xero':
            domain = [
                ('instance_id','=',self.instance_id.id),
                ('default_code','=',order_line.get('default_code'))
            ]
        else:
            domain = [
                ('instance_id','=',self.instance_id.id),
                ('remote_template_id','=',order_line.get('product_id'))
            ]
            if order_line.get('variant_id'):
                domain.append(('remote_id','=', order_line.get('variant_id')))
        product_id = product_env.search(domain, limit=1)
        return False if not product_id else product_id.mapped('name')

    def get_mapping_model(self):
        model_dict = {
            'omas.account.feed':'omas.account.mapping',
            'omas.customer.feed': 'omas.customer.mapping',
            'omas.product.feed':'omas.template.mapping',
            'omas.order.feed': 'omas.order.mapping',
            'omas.invoice.feed': 'omas.invoice.mapping',
            'omas.payment.feed': 'omas.payment.mapping',
            'omas.purchase.order.feed':'omas.purchase.order.mapping',
        }
        return model_dict.get(self._name, False)

    def set_odoo_order_state(self, order, order_state, **kwargs):
        instance_id = self.instance_id
        message = ''
        if order:
            om_order_state_ids =instance_id.order_state_ids
            order_state_ids = om_order_state_ids.filtered(
                lambda state: state.instance_state == order_state) or instance_id.order_state_ids.filtered(
                    'default_order_state')
            if order_state_ids:
                state_id = order_state_ids[0]
                order_state = state_id.odoo_order_state
                kwargs.update({
                    'create_invoice': state_id.odoo_create_invoice,
                    'invoice_state': state_id.odoo_set_invoice_state,
                    'ship_order' : state_id.odoo_ship_order
                })
                if order_state in ['cancelled']:
                    order.action_cancel()
                    message += '<br/> Order Status updated to cancel. '
                else:
                    message += self.confirm_order_and_create_invoice(order, order_state, **kwargs)
        return message
    
    def get_default_payment_method(self, journal_id):
        return self.env['account.journal'].browse(
            journal_id)._default_inbound_payment_methods()
    
    def create_payment_and_post(self, journal_id, invoice_id):
        status = False
        payment_id = False
        message = ""
        try:
            if invoice_id.state == 'posted':
                inv_id = invoice_id.id
            elif invoice_id.state == 'draft':
                invoice_id.action_post()
                inv_id = invoice_id.id
            else:
                _logger.info('Error: Can not create payment, invoice is cancelled in odoo')
                return False, f"Error: Can not create payment, invoice {invoice_id.name} is in cancelled state"
                # invoice_id.button_draft()
                # invoice_id.action_post()
                # inv_id = invoice_id.id
            # Setting Context for Payment Wizard
            register_wizard = self.env['account.payment.register'].with_context({
                    'active_model': 'account.move',
                    'active_ids': [inv_id]
                })
            register_wizard_obj = register_wizard.create({
                'journal_id': journal_id.id
            })
            payment_data = register_wizard_obj.action_create_payments()
            payment_id = self.env['account.payment'].browse(payment_data.get('res_id'))
        except Exception as e:
            message = f"Error in Creating payment {e}"
            if self.instance_id.debug:
                _logger.info('Error in creating Payments : %r', str(e))
            raise Exception(f'Error in creating Payment for invoice {invoice_id.name}: {e}')
        return payment_id, message
    
    def confirm_order_and_create_invoice(self, order, order_state, **kwargs):
        message = ""
        instance_id = self.instance_id
        confirmation_date = kwargs.get('confirmation_date')
        date_invoice = kwargs.get('date_invoice')
        payment_method = kwargs.get('payment_method')
        if order_state and order_state in ['sale', 'done']:
            if order.state == 'draft':
                order.action_confirm()
            if confirmation_date:
                order.write({'date_order': confirmation_date})
            message += "Order Status updated to confirm."
            journal_id = self.create_payment_method(payment_method)
            if journal_id and kwargs.get('create_invoice'):
                data = {
                    'order_id': order,
                    'journal_id': journal_id,
                    'instance_id': instance_id.id,
                    'order_state': order_state,
                    'invoice_state': kwargs.get('invoice_state'),
                    'date_invoice':date_invoice
                }
                message += self.set_order_paid(data)
        if order_state and order_state == 'shipped' or kwargs.get('ship_order'):
            message += self.set_order_shipped(order,confirmation_date = confirmation_date)
        return message
            
    def set_order_shipped(self, order, confirmation_date = False):
        message = ""
        if order.state == 'draft':
            order.action_confirm()
            if confirmation_date:
                order.date_order = confirmation_date
            message += 'Order Status updated to confirm.'
        for picking in order.picking_ids.filtered(lambda x: x.picking_type_code in ['outgoing', 'internal'] and x.state != 'done'):
            if picking.state == 'draft':
                picking.action_confirm()
            if picking.state != 'assigned':
                picking.action_assign()
            context = {
                'active_id' : picking.id,
                'picking_id' : picking.id
            }
            for move in picking.move_ids:
                if move.move_line_ids:
                    for move_line in move.move_line_ids:
                            move_line.quantity = move_line.quantity_product_uom
                else:
                    move.quantity = move.product_uom_qty
            picking.with_context(context, skip_backorder=True, skip_sms=True).button_validate()
            message += f"Order Status updated to shipped for Picking {picking.id}."
        return message

    def set_order_paid(self, data):
        counter = 0
        message = ""
        order = data.get('order_id')
        invoice_id = False
        invoice_ids = order.invoice_ids
        date_invoice = order.date_order
        journal_id = data.get('journal_id', False)
        draft_invoice_ids = self.env['account.move']
        if not invoice_ids:
            inv = order._create_invoices()
            if date_invoice:
                inv.invoice_date = date_invoice
            draft_invoice_ids += inv
            message += f'Invoice Created for Sale Order {order.name}'
        elif invoice_ids:
            for inv in invoice_ids:
                if inv.state == 'posted':
                    invoice_id = inv.id
                elif inv.state == 'draft':
                    if date_invoice:
                        inv.write({'invoice_date': date_invoice})
                    draft_invoice_ids += inv
                counter += 1
        if data.get('invoice_state') == 'paid':
            if counter <= 1:
                if draft_invoice_ids:
                    inv = draft_invoice_ids[0]
                    inv.action_post()
                    invoice_id = inv.id
                # Setting Context for Payment Wizard
                register_wizard_obj = self.env['account.payment.register'].with_context({
                    'active_model': 'account.move',
                    'active_ids': [invoice_id]
                }).create({
                    'journal_id': journal_id
                })
                register_wizard_obj.action_create_payments()
                status_message = 'Invoice Status changed to Paid.'
            else:
                status_message = "<br/>Multiple validated Invoices found for the Odoo order. Cannot make Payment<br/>"
        return message
    
    def create_payment_method(self, payment_method):
        message = ''
        journal_id = self.instance_id.payment_method_id.id
        if not journal_id:
            journal_id = self.env['account.journal'].search([('type','in',['bank','cash'])], limit=1)
            if not journal_id:
                raise Exception('Order can not be paid, Please set the Default Payment Method in the Configuration.')
        if payment_method:
            map_obj = self.env['omas.payment.method.mapping']
            exists = map_obj.search(
                [('remote_name', '=', payment_method)], limit=1)
            if not exists:
                journal = {
                    'name': payment_method,
                    'code': self._get_journal_code(payment_method),
                    'type': 'bank',
                }
                journal_obj = self.env['account.journal'].create(journal)
                if journal_obj:
                    journal_id = journal_obj.id
                    map_obj.create({
                        'name': journal_id,
                        'remote_name': payment_method,
                        'journal_code': journal_obj.code,
                        'odoo_journal_id': journal_id,
                        'channel_id': self.instance_id.id
                    })
            else:
                journal_id = exists.odoo_journal_id
        return journal_id
    
    def _get_journal_code(self, string, sep=' '):
        tl = [t.title()[0] for t in string.split(sep)]
        code = ''.join(tl)
        code = code[0:3]
        return code

    def evaluate_feeds(self)->object:
        message = ''
        self = self.contextualize_mappings(instance_ids = self.mapped('instance_id').ids)
        res = list(map(self.evaluate_feed, self))
        not_evaluated = list(filter(lambda x: x.get('state') == 'error', res))
        len_res, len_not_evaluated = len(res), len(not_evaluated)
        evaluated = len_res - len_not_evaluated
        if evaluated:
            message += f'<span class="text-success">{evaluated} feeds evaluated successfully.</span>'
        if not_evaluated:
            message += f'{len_not_evaluated} feeds could not be evaluated.'
        return self.env['omas'].display_message(message)
    
    def evaluate_feed(self, feed)->dict:
        # Update: Added with_compnay for multi-company feature
        res = feed.with_company(feed.instance_id.company_id.id).create_entity()
        if res['state'] not in ['done']:
            feed.state = res['state']
            feed.message = res['message']
        else:
            feed.unlink()
        return res
    
    def contextualize_feeds(self,object,instance_ids=False)->object:
        if not instance_ids and 'instance_id' in self._context:
            instance_ids = self._context.get('instance_id').ids
        if not instance_ids:
            raise Exception('No instance_ids available to contextualize feeds.')
        feeds = {}
        if object == 'accounts':
            for rec in self.env['omas.account.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object, f'{object}_feeds' :  feeds})
        elif object == 'customers':
            for rec in self.env['omas.customer.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object,f'{object}_feeds' :  feeds})
        elif object == 'products':
            for rec in self.env['omas.product.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object,f'{object}_feeds' :  feeds})
        elif object == 'orders':
            for rec in self.env['omas.order.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object,f'{object}_feeds' :  feeds})
        elif object == 'invoices':
            for rec in self.env['omas.invoice.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object,f'{object}_feeds' :  feeds})
        elif object == 'payments':
            for rec in self.env['omas.payment.feed'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                feeds.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'object' : object,f'{object}_feeds' :  feeds})
        else:
            raise Exception('Wrong type for feeds to be contextualized.')
    
    def contextualize_mappings(self,instance_ids=False)->object:
        if not instance_ids and 'instance_id' in self._context:
            instance_ids = self._context.get('instance_id').ids
        if not instance_ids:
            raise Exception('No instance_ids available to contextualize mappings.')
        if self._name == 'omas.account.feed':
            mappings = {}
            for rec in self.env['omas.account.mapping'].search_read(
                [('instance_id','in',instance_ids),('active','in',[True, False])],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'account_mappings':mappings})
        elif self._name == 'omas.customer.feed':
            mappings = {}
            for rec in self.env['omas.customer.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'customer_mappings':mappings})
        elif self._name == 'omas.product.feed':
            product_mappings,variant_mappings = {},{}
            for rec in self.env['omas.template.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                product_mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            for rec in self.env['omas.product.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','remote_template_id','instance_id'],
            ):
                variant_mappings.setdefault(
                    rec.get('instance_id')[0],{}
                ).setdefault(
                    rec.get('remote_template_id'),{}
                )[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'product_mappings':product_mappings,'variant_mappings':variant_mappings})
        elif self._name == 'omas.order.feed':
            mappings = {}
            for rec in self.env['omas.order.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'order_mappings':mappings})
        elif self._name == 'omas.invoice.feed':
            mappings = {}
            for rec in self.env['omas.invoice.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'invoice_mappings':mappings})
        elif self._name == 'omas.purchase.order.feed':
            mappings = {}
            for rec in self.env['omas.purchase.order.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'purchase_order_mappings':mappings})
        elif self._name == 'omas.payment.feed':
            mappings = {}
            for rec in self.env['omas.payment.mapping'].search_read(
                [('instance_id','in',instance_ids)],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'payment_mappings':mappings})
        # Update Tax contextualize mapping
        elif self._name == "omas.tax.feed":
            mappings = {}
            for rec in self.env['omas.tax.mapping'].search_read(
                [('instance_id','in',instance_ids),('active','in',[True, False])],
                ['id','remote_id','instance_id'],
            ):
                mappings.setdefault(rec.get('instance_id')[0],{})[rec.get('remote_id')] = rec.get('id')
            return self.with_context({'tax_mappings':mappings})
        else:
            raise Exception('Wrong type for mappings to be contextualized.')
