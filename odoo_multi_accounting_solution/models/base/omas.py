# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from logging import getLogger
_logger = getLogger(__name__)
from datetime import datetime
from odoo.http import request
from odoo import models, fields, api
from odoo.fields import Datetime, Date
from odoo.exceptions import UserError
from markupsafe import Markup
from ...ApiTransaction import Transaction

class OdooMultiAccountingSolution(models.Model):
    _name = 'omas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Odoo Multi Accounting Solution'

    name = fields.Char(required = True, tracking=True)
    debug = fields.Boolean(default=False)
    is_connected = fields.Boolean(default=False, string='Connected', tracking=True, copy=False)
    active = fields.Boolean(default=True)
    api_limit = fields.Selection([
        ('5','5'),
        ('10','10'),
        ('20','20'),
        ('50','50'),
        ('100','100')
    ], default='50')
    page_limit = fields.Selection([
        ('50','50'),
        ('100','100'),
        ('200','200'),
        ('500','500'),
        ('1000','1000')
    ], default='50')
    client_id = fields.Char("Client ID", tracking=True)
    client_secret = fields.Char("Client Secret", tracking=True)
    user_id = fields.Many2one(comodel_name = "res.users", string = "Salesperson", default= lambda self: self.env['res.users'].search([],limit=1))
    team_id = fields.Many2one(comodel_name = "crm.team", string = "Sales Team", default= lambda self: self.env['crm.team'].search([],limit=1))
    discount_product_id = fields.Many2one(comodel_name="product.product", string="Discount Product", default=lambda self: self.env.ref('odoo_multi_accounting_solution.discount_product').id)
    delivery_product_id = fields.Many2one(comodel_name="product.product", string="Delivery Product" , default = lambda self: self.env.ref('odoo_multi_accounting_solution.delivery_product').id)
    refresh_token = fields.Char('Refresh Token')
    access_token = fields.Char('Access Token')
    authorization_token = fields.Char('Authorization Token')
    # redirect_uri = fields.Char('Redirect URI',compute = '_omas_redirect_uri')
    redirect_uri = fields.Char('Redirect URI',help="Redirect Url eg: https://your-odoo-url/omas", default = lambda self:self._omas_redirect_uri(), tracking=True)
    currency_id = fields.Many2one(string = "Currency", comodel_name="res.currency", default=lambda self: self.env['res.currency'].search([], limit=1))
    auto_evaluate_feed = fields.Boolean(default=False, tracking=True)
    account_sequence_id = fields.Many2one(comodel_name="ir.sequence", string="Account Sequence")
    set_account_sequence = fields.Boolean(default = False)
    journal_sequence_id = fields.Many2one(comodel_name="ir.sequence", string="Payment Method Sequence")
    set_journal_sequence = fields.Boolean(default = False)
    product_sequence_id = fields.Many2one(comodel_name="ir.sequence", string="Product Sequence")
    set_product_sequence = fields.Boolean(default=False)
    
    import_invoice_date = fields.Datetime("Import Invoice Date")
    import_order_date = fields.Datetime("Import Order Date")
    import_purchase_order_date = fields.Datetime("Import Purchase Order Date")
    import_customer_date = fields.Datetime("Import Partner Date")
    import_payment_date = fields.Datetime("Import Payment Date")
    import_product_date = fields.Datetime("Import Product Date")
    import_credit_notes_date = fields.Datetime("Import Credit Notes Date")
    import_bill_date = fields.Datetime("Import Bills Date")
    import_refund_date = fields.Datetime("Import Refunds Date")

    use_order_cron = fields.Boolean(' Import Order Cron')
    use_purchase_order_cron = fields.Boolean(' Import Purchase Order Cron')
    use_product_cron = fields.Boolean(' Import Product Cron')
    use_invoice_cron = fields.Boolean(' Import Invoice Cron')
    use_payment_cron = fields.Boolean(' Import Payment Cron')
    use_customer_cron = fields.Boolean(' Import Customer Cron')
    use_credit_notes_cron = fields.Boolean('Import Credit Notes Cron')
    use_bill_cron = fields.Boolean('Import Bills Cron')
    use_refund_cron = fields.Boolean('Import Refunds Cron')

    payment_method_id = fields.Many2one(
        comodel_name='account.journal', 
        string = 'Default Payment Method',
        domain = [('type','in',['bank','cash'])], 
        default = lambda self: self.env['account.journal'].search([('type','in',['bank','cash'])],limit=1))
    image = fields.Image(max_width=300, max_height=300)
    default_tax_type = fields.Selection([
        ('include','Included In Price'),
        ('exclude','Excluded In Price')
        ], default = "exclude")

    company_id = fields.Many2one(
	comodel_name = "res.company",
        default = lambda self: self.env.user.company_id.id,
	    string='Company Id',
        required = True
	)

    location_id = fields.Many2one(
        "stock.location",
        related='warehouse_id.lot_stock_id',
        string='Stock Location',
        help='Stock Location used for imported product.',
    )
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Warehouse',
        help='Warehouse used for imported product.',
        default = lambda self: self.env['stock.warehouse'].search([],limit=1),
        required = True
    )


    @api.onchange('company_id')
    def change_warehouse_domain(self):
        if self.company_id:
            warehouse = self.env['stock.warehouse'].search([('company_id','=',self.company_id.id)],limit=1)
            self.warehouse_id = warehouse.id if warehouse else False
            self.currency_id = self.company_id.currency_id.id
            return {
                'domain':{'warehouse_id':[('company_id','=',self.company_id.id)]}
            }

    organization_id = fields.Many2one(comodel_name='omas.instance.organization', string='Organization ID', tracking=True, copy=False)

    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Default Pricelist',
        default=lambda self: self.env['product.pricelist'].search([], limit=1),
        help="""Select the same currency of pricelist used  over Accounting Software.""",
    )
    language_id = fields.Many2one(
        comodel_name='res.lang',
        default = lambda self: self.env['res.lang'].search([], limit=1),
        help="""The language used over the Accounting Software.""",
    )
    order_state_ids = fields.One2many(
        comodel_name='omas.instance.order.state',
        inverse_name='instance_id',
        string='Default Odoo Order States',
        help='Imported order will process in odoo on basis of these state mappings.',
        copy = True,
    )
    
    default_category_id = fields.Many2one(comodel_name="product.category", default=lambda self: self.env['product.category'].search([], limit=1), help="Default Category will be used in products")
    avoid_duplicity = fields.Boolean('Avoid Duplicity', help="Avoid creating duplicate products in odoo", tracking=True)
    
    sync_sale_order_name = fields.Boolean('Sale Order Name')
    sync_purchase_order_name = fields.Boolean('Purchase Order Name')
    
    @api.model
    def get_instances(self)->list:
        return []

    instance = fields.Selection(selection='get_instances', required=True)

    def _omas_redirect_uri(self):
        odoo_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return odoo_url+"/omas"

    def get_organization_ids(self):
        message = ''
        self.ensure_one()
        try:
            self.refresh_access_token()
            res = getattr(self, f'get_{self.instance}_organization_ids', False)
            if res:
                organizations, message = res()
                if organizations:
                    organization_env = self.env['omas.instance.organization']
                    organization_ids = organization_env.search([('instance_id','=',self.id)])
                    organization_ids.unlink()
                    data_list = []
                    for organization in organizations:
                        organization.update(instance_id = self.id)
                        data_list.append(organization)
                    if data_list:
                        message += "<br/> <span>Select the Organization</span>"
                        organization_env.create(data_list)
            else:
                message = f"Method not defined...get_{self.instance}_organization_ids"
        except Exception as e:
            message = f'Error in getting Organization IDs: {e}'
            if self.debug:
                _logger.error('Error in getting Organization IDs: %r', e, exc_info=True)
        return self.display_message(message)

    def display_message(self, text)-> None:
        return self.env['omas.message.wizard'].generate_message(text)

    def toggle_debug(self)->None:
        self.debug = not self.debug

    def toggle_active(self)->None:
        self.active = not self.active
    
    def disconnect_instance(self)->None:
        self.ensure_one()
        message = ''
        try:
            method = getattr(self, f'disconnect_{self.instance}')
            if method:
                res = method()
                if res:
                    message = "<span class='text-success'>Disconnect successfully</span>"
                    self.is_connected = False
                else:
                    message = 'Error: Failed to Disconnected Instance'
                    self.is_connected = False
                return self.display_message(message)
            _logger.error(f'Error: disconnect method not found')
        except Exception as e:
            raise UserError(f'Error in Disconnecting Instance : {e}')

    def connect_instance(self)->dict:
        self.ensure_one()
        try:
            res = getattr(self, f'connect_{self.instance}')()
            request.session['instance_id'] = self.id
        except Exception as e:
            raise UserError(e)
        return res

    def refresh_access_token(self)->None:
        self.ensure_one()
        try:
            res = getattr(self, f'refresh_{self.instance}_access_token')()
            if isinstance(res, dict):
                if not res.get('refresh_token'):
                    res.pop('refresh_token')
                if not res.get('access_token'):
                    res.pop('access_token')
                message = "<span class='text-success'>Connection Refreshed Successfully<span>"
                self.write(res)
            else:
                message = f"<span class='text-danger'>Something Went Wrong: Connection is not refreshed <br/> {res}</span>"
                # self.is_connected = False
            if self._context.get('from_button'):
                return self.display_message(message)

        except Exception as e:
            raise UserError(e)

    def import_entities(self, object , **kwargs)->None:
        return Transaction(instance_id=self).import_accounting(object, **kwargs)

    def export_entities(self, object, **kwargs)->None:
        return Transaction(instance_id=self).export_accounting(object, **kwargs)

    def create_entities_without_feed(self, object, datalist):
        mapping_model = self.get_mapping_model(object)
        instance_id = self
        records = [self.env[mapping_model].create_entity(instance_id, data) for data in datalist if data]
        return records

    def create_online_connection(self)->None:
        self.ensure_one()
        try:
            res = getattr(self, f'create_{self.instance}_online_connection')()
            if isinstance(res,dict):
                if not res.get('refresh_token'):
                    res.pop('refresh_token')
                if not res.get('access_token'):
                    res.pop('access_token')
                self.get_organization_ids()
                self.write(res)                
                self._cr.commit()
        except Exception as e:
            raise UserError(e)

    def export_entity(self, record):
        exported, remote_id, message = False, False, ''
        try:
            object = self._context.get('object')
            method = getattr(self, f'export_{self.instance}_{object}', False)
            if method:
                return_data = method(record)
                if object == 'templates':
                    exported, remote_id, item_code, *args = return_data
                else:
                    exported, remote_id, *args = return_data
                if args and type(args[0]) == dict:
                    kwargs = args[0]
                    message = kwargs.get('message', '')
                if exported:
                    if object == 'templates':
                        getattr(self, 'create_template_mapping')(remote_id, record, operation='export', item_code=item_code)
                        getattr(self, 'create_product_mapping')(remote_id, remote_id, record.product_variant_id, operation='export', item_code = item_code)
                    elif object in ['credit_notes', 'invoices']: # Invoices, Credit Notes and Refunds
                        getattr(self, 'create_invoice_mapping')(remote_id, record, operation='export', type=record.move_type)
                    elif object == 'accounts':
                        getattr(self, 'create_account_mapping')(remote_id, record, display_name=record.name, code=record.code, operation='export')
                    elif object == 'customers':
                        customer_type = 'vendor' if record.supplier_rank else 'customer'
                        getattr(self, 'create_customer_mapping')(remote_id, record, customer_type=customer_type, operation='export')
                    else:
                        getattr(self, f'create_{object[:-1]}_mapping')(remote_id, record, operation='export')
        except Exception as e:
            message += str(e)
            _logger.error(e)
            if self.debug:
                _logger.error(e, exc_info=True)
        if message:
            message = f'[{record.id}] ' + message
        return exported, remote_id, message
    
    def open_import_operation_view(self)->dict:
        view_id = self.env.ref('odoo_multi_accounting_solution.omas_import_operation_view_form').id
        context = self._context.copy()
        context.update({'default_instance_id' : self.id, 'active_id' : True})
        return {
            'name':'Import Wizard',
            'type' : 'ir.actions.act_window',
            'view_type' : 'form',
            'view_mode' : 'form',
            'res_model' : 'omas.import.operation',
            'views': [(view_id,'form')],
            'view_id': view_id,
            'context': context,
            'target':'new'
        }
    
    def open_export_operation_view(self)->dict:
        view_id = self.env.ref('odoo_multi_accounting_solution.omas_export_operation_view_form').id
        context = self._context.copy()
        context.update({'default_instance_id' : self.id, 'active_id' : True})
        return {
            'name':'Export Wizard',
            'type' : 'ir.actions.act_window',
            'view_type' : 'form',
            'view_mode' : 'form',
            'res_model' : 'omas.export.operation',
            'views': [(view_id,'form')],
            'view_id': view_id,
            'context': context,
            'target':'new'
        }

    # Open Cron View:
    def open_cron_views(self)->dict:
        cron_view_id = self._context.get('cron_view_id')
        view_id = self.env.ref(f'odoo_multi_accounting_solution.{cron_view_id}').id
        return {
			'name': 'Open Cron View',
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'ir.cron',
			'res_id': view_id,
			'target': 'current',
        }


    def match_odoo_template(self, data)->object:
        odoo_template = False
        template = self.env['product.template']
        barcode =  data.get('barcode')
        if barcode:
            odoo_template = template.search([('barcode', '=', barcode)], limit=1)
        else:
            default_code =  data.get('default_code')
            if default_code and self.avoid_duplicity:
                odoo_template = template.search([('default_code', '=', default_code)], limit=1)
        return odoo_template

    def match_odoo_taxes(self, rate, limit=1):
        domain = [('amount','=',rate)]
        return self.env['account.tax'].search(domain, limit=limit)

    def match_odoo_accounts(self, code, company_id = False,limit=1)->object:
        account = self.env['account.account']
        domain = [('code','=',code)]
        if company_id:
            domain.append(('company_id','=',company_id.id))
        return account.search(domain, limit=limit)

    def string_to_datetime(self, value:str)->Datetime:
        return Datetime.to_datetime(" ".join(value.split("T")))
    
    def datetime_to_string(self, value)->str:
        return Datetime.to_string(value)

    def string_to_date(self, value)->Date:
        if "T" in value:
            value = " ".join(value.split('T'))
        return Date.to_date(value)

    def epoch_to_date(self, value: str)->datetime:
        return datetime.fromtimestamp(int(value.split("(")[1][: 10])).date()
    
    @api.model
    def get_currency_id(self, code):
        return self.env['res.currency'].search([('name','=',code)], limit=1)
    
    @api.model
    def get_price_list(self, currency_id):
        price_list =  self.env['product.pricelist'].search([('currency_id','=',currency_id.id)], limit = 1)
        if price_list:
            return price_list
        # Created link to open pricelist tree view
        action = self.env.ref('product.product_pricelist_action2').id
        message = f'Please Create <a href="/web#model=product.pricelist&action={action}&view_type=tree" target = "_blank">pricelist</a> for currency {currency_id.name}'
        raise UserError(message)

    @api.model
    def get_country_id(self, country_code):
        return self.env['res.country'].search([('code', '=', country_code)], limit=1)

    def DomainVals(self, domain):
        return dict(map(lambda item :(item[0],item[2]),domain))

    @api.model
    def get_state_id(self, state_code, country_id, state_name=None):
        if not state_code and state_name:
            state_code = state_name[:2]
        state_name = state_name or ''
        domain = [
            ('code', '=', state_code),
            ('name', '=', state_name),
            ('country_id', '=', country_id.id)
        ]
        state_id = country_id.state_ids.filtered(
            lambda st:(
                st.code in [state_code,state_name[:3],state_name])
                or (st.name == state_name )
            )
        if not state_id:
            vals = self.DomainVals(domain)
            vals['name'] = state_name and state_name or state_code
            if (not vals['code']) and state_name:
                vals['code'] = state_name[:2]
            state_id = self.env['res.country.state'].create(vals)
        else:
            state_id =state_id[0]
        return state_id
    
    @api.model
    def omas_import_cron(self, object):
        for instance_id in self.env['omas'].search([('is_connected','=',True)]):
            real_object = object
            if getattr(instance_id, f'use_{object}_cron',False):
                kwargs = {}
                if object in ['bill', 'refund', 'invoice', 'credit_notes']:
                    move_type = 'in_invoice' if object=='bill' else 'in_refund' if object=='refund' else 'out_invoice' if object=='invoice' else 'out_refund'
                    if object == 'bill':
                        real_object = 'invoice'
                    elif object == 'refund':
                        real_object = 'credit_notes'
                    kwargs.update({'move_type': move_type})
                import_cron = getattr(instance_id, f'{instance_id.instance}_import_{real_object}_cron', False)
                if import_cron:
                    _logger.info(f'++++++++++++++++++ {instance_id.instance} Import {object} cron Started ++++++++++++++++++')
                    res = import_cron(**kwargs)
                elif instance_id.debug:
                    _logger.info(f'Import {real_object} cron method not defined in {instance_id.instance}')
        return True
    
    @api.model
    def omas_feed_evaluation_cron(self):
        for object_model in  ["omas.tax.feed", "omas.account.feed", "omas.product.feed", "omas.customer.feed", "omas.order.feed", "omas.invoice.feed", "omas.payment.feed"]:
            records = self.env[object_model].search([
                ("state","!=","done"),
                ("instance_id.is_connected","=",True)
            ])
            if records:
                records.evaluate_feeds()
        return True
