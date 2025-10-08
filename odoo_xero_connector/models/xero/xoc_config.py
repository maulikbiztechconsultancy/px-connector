# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from logging import getLogger
import requests
import base64
from ...xero_api import XeroApi
from urllib.parse import urlencode
from odoo import models, api
from odoo.exceptions import UserError
from markupsafe import Markup
from ...XeroTransactions import XeroTransactions

_logger = getLogger(__name__)

class XeroConfiguration(models.Model):
    _inherit = 'omas'

    def get_xero_organization_ids(self):
        organizations = []
        self.refresh_access_token()
        tenants = requests.get('https://api.xero.com/connections', headers={
            'Authorization':f'Bearer {self.access_token}',
            'Content-Type':'application/json'
        })
        tenants_json = tenants.json()
        if tenants.ok:
            for tenant in tenants_json:
                organizations.append({
                    'name' : tenant.get('tenantName'),
                    'remote_id' : tenant.get('tenantId'),
                    'connection_id': tenant.get('id')

                })
            message = f'<span class="text-success">Organizations Fetched Successfully for Xero<span>'
        else:
            message = f'Error in getting Organizations : {tenants_json.get("Detail")}'
        return organizations, message

    @api.model
    def get_instances(self)->list:
        res = super(XeroConfiguration, self).get_instances()
        res.append(('xero', 'Xero'))
        return res

    def connect_xero(self)->dict:
        scope = 'offline_access accounting.transactions accounting.settings accounting.contacts'
        url = "?".join(
            ["https://login.xero.com/identity/connect/authorize", urlencode({
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": "xeroodooconnector"
        })])
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target":"self"
        }
    
    def disconnect_xero(self)->dict:
        self.refresh_access_token()
        connectionId = self.organization_id.connection_id
        res = requests.delete(f'https://api.xero.com/connections/{connectionId}', headers={
            'Authorization':f'Bearer {self.access_token}',
            'Content-Type':'application/json'
        })
        if res.status_code in [200, 204]:
            return True

    def create_xero_online_connection(self)->None:
        if not self.is_connected and not self._context.get('authorization'):
            self.message_post(body=Markup("""
                              <span class="text-danger">Error</span>: Can not create connection 
                              with Xero using '<span class="text-primary">'Create Online 
                              Connection</span>' button when you are disconnected!<br/> Please 
                              try to create connection using '<span class="text-success">
                              Connect</span>' button
                              """))
            return False
        pair = self.client_id + ':' + self.client_secret
        auth_header = pair.encode("utf-8")
        headers = {
            "authorization": "Basic " + base64.b64encode(auth_header).decode('utf-8'),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(
            "https://identity.xero.com/connect/token", data=urlencode({
                'grant_type':'authorization_code',
                'code':self.authorization_token,
                'redirect_uri':self.redirect_uri
        }), headers=headers)
        if response.status_code in [200, 201]:
            res = response.json()
            return {
                "is_connected": True,
                "access_token": res.get("access_token"),
                "refresh_token": res.get("refresh_token"),
            }
    
    def refresh_xero_access_token(self)->None:
        pair = self.client_id + ':' + self.client_secret
        auth_header = pair.encode("utf-8")
        headers = {
            "Authorization": "Basic " + base64.b64encode(auth_header).decode('utf-8'),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(
            "https://identity.xero.com/connect/token", data={
                'refresh_token' : self.refresh_token,
                'grant_type':'refresh_token'
        }, headers=headers)
        if response.status_code in [200, 201]:
            res = response.json()
            return {
                "is_connected": True,
                "access_token": res.get("access_token"),
                "refresh_token": res.get("refresh_token"),
            }
        

    @api.constrains('organization_id')
    def xero_organization_currencies(self):
        if self.instance == 'xero':
            message = ''
            mismatch = "<strong>There is a mismatch in currencies</strong>"
            if self.organization_id:
                self.refresh_access_token()
                currencies = self.get_xeroapi_object().get('Currencies')
                if currencies.get('json') and currencies.get('json').get('Currencies'):
                    xero_active_currencies = currencies.get('json').get('Currencies')
                    odoo_active_currencies = self.env['res.currency'].search([]).mapped('name')
                    for xero_currency in xero_active_currencies:
                        if not xero_currency.get('Code') in odoo_active_currencies:
                            message += f"""<p class='text-warning'>Warning: Xero Organization currency <strong>{xero_currency.get('Code')}</strong> is not active in odoo</p>"""       
            if message:
                message = mismatch + message
                self.message_post(body=Markup(message))
        
    def xero_unavailable_features(self):
        message = """
            <ul>
                <li>The Features Category Mappings, Payment Term Mappings and Shipping Mappings does not exists in Xero.</li>
            </ul>
            """         
        return message
    
    def get_xeroapi_object(self)->object:
        if not self.organization_id:
            raise UserError('Please Select Organization Id First.')
        return XeroApi(self.access_token, self.organization_id.remote_id, debug=self.debug)

    def import_xero_accounts(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_accounts(xero, **kwargs)

    def import_xero_customers(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_customers(xero, **kwargs)

    def import_xero_templates(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_products(xero, **kwargs)

    def import_xero_orders(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_orders(xero, **kwargs)

    def import_xero_purchase_orders(self,**kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_purchase_orders(xero, **kwargs)

    def import_xero_invoices(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_invoices(xero, **kwargs)

    def import_xero_payments(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_payments(xero, **kwargs)

    def import_xero_taxes(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_taxes(xero, **kwargs)    

    def import_xero_credit_notes(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_credit_notes(xero, **kwargs)

    def import_xero_payment_methods(self, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).get_journals(xero, **kwargs)

    def export_xero_credit_notes(self, record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_credit_notes(xero, record, **kwargs)
    
    def export_xero_accounts(self, record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_account(xero, record, **kwargs)

    def export_xero_customers(self,record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_customer(xero, record, **kwargs)

    def export_xero_templates(self, record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_product(xero, record, **kwargs)

    def export_xero_orders(self,record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_order(xero, record, **kwargs)
    
    def export_xero_purchase_orders(self,record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_purchase_order(xero, record, **kwargs)

    def export_xero_invoices(self,record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self).post_invoice(xero, record, **kwargs)

    def export_xero_payments(self,record, **kwargs):
        self.refresh_access_token()
        xero = self.get_xeroapi_object()
        return XeroTransactions(self, env=self.env).post_payment(xero, record, **kwargs)

    def xero_import_customer_cron(self, **kw):
        return self.import_entities('customers', from_cron = True, **kw)

    def xero_import_product_cron(self, **kw):
        return self.import_entities('templates', from_cron = True, **kw)

    def xero_import_order_cron(self, **kw):
        return self.import_entities('orders', from_cron = True, **kw)

    def xero_import_invoice_cron(self, **kw):
        return self.import_entities('invoices', from_cron = True, **kw)
    
    def xero_import_credit_notes_cron(self, **kw):
        return self.import_entities('credit_notes', from_cron = True, **kw)

    def xero_import_payment_cron(self, **kw):
        return self.import_entities('payments', from_cron = True, **kw)
    
    def xero_import_purchase_order_cron(self, **kw):
        return self.import_entities('purchase_orders', from_cron = True, **kw)
    
