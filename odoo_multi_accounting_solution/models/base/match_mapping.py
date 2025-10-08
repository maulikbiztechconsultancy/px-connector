# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from odoo import models

class OdooMultiAccountingSolution(models.Model):
    _inherit = 'omas'

    def match_product_mapping(self, odoo_id = False, remote_id = False, limit=1):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=',odoo_id))
            else:
                domain.append(('name','=',odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=',remote_id))
        return self.env['omas.product.mapping'].search(domain, limit=limit)

    def match_customer_mapping(self, odoo_id = False, remote_id = False, type='contact', limit=1):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.customer.mapping'].search(domain, limit=limit)

    def match_invoice_mapping(self, odoo_id = False, remote_id = False, limit=1):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.invoice.mapping'].search(domain, limit=limit)

    def match_account_mapping(self, odoo_id = False, remote_id = False, limit=1):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.account.mapping'].search(domain, limit=limit)

    def match_order_mapping(self, odoo_id = False, remote_id = False):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.order.mapping'].search(domain, limit=1)

    def match_tax_mapping(self, odoo_id = False, remote_id = False):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))     
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.tax.mapping'].search(domain, limit = 1)

    def match_payment_mapping(self, odoo_id = False, remote_id = False):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.payment.mapping'].search(domain, limit=1)

    def match_payment_method_mapping(self, remote_id=False, name=False):
        domain = [('instance_id','=',self.id)]
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        if name:
            domain.append(('remote_name','=',name))
        return self.env['omas.payment.method.mapping'].search(domain, limit=1)
    
    def match_purchase_order_mapping(self, odoo_id = False, remote_id = False):
        domain = [('instance_id','=',self.id)]
        if odoo_id:
            if isinstance(odoo_id, (int, str)):
                domain.append(('name','=', odoo_id))
            else:
                domain.append(('name','=', odoo_id.id))
        if remote_id:
            domain.append(('remote_id','=', remote_id))
        return self.env['omas.purchase.order.mapping'].search(domain, limit=1)
