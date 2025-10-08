# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo import models, fields

from logging import getLogger
_logger = getLogger(__name__)

class OdooMultiAccountingSolution(models.Model):
    _inherit = 'omas'
    
    unavailable_features = fields.Html('Unavailable Features Note', compute="get_unavailable_features")

    # eg: xero_unavailable_features ,...etc
    def get_unavailable_features(self):
        """Show Unavailable features note in the operation page 
            of instance configuration.
            eg method in extension: zoho_unavailable_features, etc
        """
        instance = self.instance
        method = f'{instance}_unavailable_features'
        message = ''
        if hasattr(self, method):
            message_method  = getattr(self, method)
            if message_method:
                message = "NOTE:" + str(message_method())
        else:
            _logger.warning(f'{method} method is not defined in {instance} accounting module')
        self.unavailable_features = message

    all_available_features = fields.Char(compute="_get_available_features")

    def _all_available_features_list(self):
        return [
            'cron_available',
            'import_customer_cron',
            'import_product_cron',
            'import_sale_order_cron',
            'import_purchase_order_cron',
            'import_customer_invoice_cron',
            'import_vendor_bill_cron',
            'import_credit_note_cron',
            'import_refund_cron',
            'import_payment_cron',
        ]

    def _get_available_features(self):
        """show/hide fields from view based on the returned list from extension.
            Example methods in the extension: 
            xero_available_features, etc
        """
        features_list = self._all_available_features_list()
        method = f'{self.instance}_available_features'
        if hasattr(self, method):
            response = getattr(self, method)() # list return from extension
            if isinstance(response, (list, tuple, set)):
                features_list = response
        features_list = ','.join(set(features_list))
        self.all_available_features = features_list
    
    # Activate Developer Mode
    def multi_accounting_developer_mode(self):
        """Activate the Developer mode
        """
        url = self.redirect_to_instance(self.id)
        append_url = '/web?debug=0'
        if self._context.get('debug_activate'):
            append_url = '/web?debug=1'
        url = url.replace('/web', append_url)
        return {
                'type': 'ir.actions.act_url',
                'target': 'self',
                'url': url
            }
    def redirect_to_instance(self, instance_id=False):
        """Method to get the channel's form view URL
        """
        action_id = self.env.ref('odoo_multi_accounting_solution.omas_action').id
        url = "/web#action={}&model=omas".format(action_id)
        if instance_id:
            url = "/web#id={}&action={}&model=omas&view_type=form".format(instance_id, action_id)
        return url
    
    def get_feed_model(self, object)->str:
        mapping_dict = {
                'accounts':'omas.account.feed',
                'customers':'omas.customer.feed',
                'templates':'omas.product.feed',
                'orders':'omas.order.feed',
                'payments':'omas.payment.feed',
                'invoices':'omas.invoice.feed',
                'credit_notes':'omas.invoice.feed',
		        'taxes':'omas.tax.feed',
                'purchase_orders':'omas.purchase.order.feed',
            }
        return mapping_dict[object]

    def get_entity_model(self, object)->str:
        object_dict = {
                'accounts':'account.account',
                'customers':'res.partner',
                'templates':'product.template',
                'orders':'sale.order',
                'payments':'account.payment',
                'invoices':'account.move',
                'credit_notes':'account.move',
                'purchase_orders':'purchase.order',
            }
        return object_dict[object]

    def get_mapping_model(self, object)->str:
        mapping_dict = {
                'accounts':'omas.account.mapping',
                'customers':'omas.customer.mapping',
                'templates':'omas.template.mapping',
                'orders':'omas.order.mapping',
                'purchase_orders':'omas.purchase.order.mapping',
                'payments':'omas.payment.mapping',
                'invoices':'omas.invoice.mapping',
                'credit_notes':'omas.invoice.mapping',
                'payment_methods': 'omas.payment.method.mapping',
            }
        return mapping_dict[object]
    
    def get_message_object(self, object): # Object in import/export message for user
        message_object = {
                'taxes': 'Taxes',
                'accounts':'Accounts',
                'customers':'Customers',
                'templates':'Products',
                'orders':'Orders',
                'purchase_orders':'Purchase Orders',
                'payments':'Payments',
                'invoices':'Invoices',
                'credit_notes': 'Credit Notes',
                'out_invoice': 'Customer Invoices',
                'in_invoice': 'Vendor Bills',
                'out_refund':'Credit Notes',
                'in_refund':'Refunds',
                'payment_methods': 'Payment Methods',
        }
        return message_object.get(object)