# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo import models

class OdooMultiAccountingSolution(models.Model):
    _inherit = 'omas'

    def create_account_mapping(self, remote_id, record, display_name=False, code=False, operation='import')->object:
        return self.env['omas.account.mapping'].sudo().create({
            'name':record.id if record else False,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_account_id':record.id if record else False,
            'operation':operation,
            'active':False if not record else True,
            'mapping_display_name': display_name or False,
            'remote_account_code': code,
        })

    def create_customer_mapping(self, remote_id, record, type='contact', customer_type='customer', operation='import')->object:
        return self.env['omas.customer.mapping'].sudo().create({
            'name': record.id,
            'remote_id' : remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_customer_id':record.id,
            'type':type,
            'customer_type': customer_type,
            'operation':operation
        })
    
    def create_template_mapping(self, remote_id, record, operation='import',item_code='')->object:
        default_code = record.default_code
        barcode = record.barcode
        return self.env['omas.template.mapping'].sudo().create({
            'name': record.id,
            'remote_id' : remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_template_id':record.id,
            'default_code': default_code if default_code else item_code,
            'barcode': barcode if barcode else '',
            'operation':operation
        })
    
    def create_order_mapping(self, remote_id, record, operation='import'):
        return self.env['omas.order.mapping'].sudo().create({
            'name':record.id,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_order_id':record.id,
            'operation':operation
        })

    def create_tax_mapping(self, record, remote_id, display_name=False, amount = 0, operation = 'import'):
        return self.env['omas.tax.mapping'].sudo().create({
            'name':record.id if record else False,
            'odoo_tax_id' : record.id if record else False,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'operation':operation,
            'active':False if not record else True,
            'mapping_display_name': display_name,
            'tax_amount': amount,
        })

    def create_invoice_mapping(self, remote_id, record, operation='import', type=False):
        return self.env['omas.invoice.mapping'].sudo().create({
            'name':record.id,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_invoice_id':record.id,
            'operation':operation,
            'mapping_move_type': type or 'out_invoice',
        })
    
    def create_payment_mapping(self, remote_id, record, operation='import'):
        return self.env['omas.payment.mapping'].sudo().create({
            'name':record.id,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_payment_id':record.id,
            'operation':operation
        })
    
    def create_product_mapping(self, remote_id, remote_template_id, record, operation='import', item_code='')->object:
        default_code = record.default_code
        barcode = record.barcode
        return self.env['omas.product.mapping'].sudo().create({
            'name': record.id,
            'remote_id' : remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_product_id': record.id,
            'odoo_template_id':record.product_tmpl_id.id,
            'remote_template_id': remote_template_id,
            'default_code': default_code if default_code else item_code,
            'barcode': barcode if barcode else '',
            'operation':operation
        })
    
    def create_purchase_order_mapping(self, remote_id, record, operation='import'):
        return self.env['omas.purchase.order.mapping'].sudo().create({
            'name':record.id,
            'remote_id':remote_id,
            'instance_id':self.id,
            'instance':self.instance,
            'odoo_purchase_order_id':record.id,
            'operation':operation
        })
