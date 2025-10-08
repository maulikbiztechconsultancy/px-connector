# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
from logging import getLogger
from datetime import datetime
_logger = getLogger(__name__)


class XeroProductRequiredParam(Exception):
    pass


IN_ACCOUNT = {
    'BANK': 'asset_cash',
    'INVENTORY': 'liability_payable',
    'SALES': 'asset_receivable',
    'FIXED': 'asset_fixed',
    'CURRENT': 'asset_current',
    'CURRLIAB': 'liability_current',
    'LIABILITY': 'liability_current',
    'EQUITY': 'equity',
    'OTHERINCOME': 'income_other',
    'EXPENSE': 'expense',
    'DIRECTCOSTS': 'expense_direct_cost',
    'REVENUE': 'expense_direct_cost',
}
OUT_ACCOUNT = {
    'asset_cash': 'BANK',
    'asset_receivable': 'SALES',
    'income': 'REVENUE',
    'asset_fixed': 'FIXED',
    'asset_current': 'CURRENT',
    'liability_current': 'LIABILITY',
    'equity': 'EQUITY',
    'income_other': 'OTHERINCOME',
    'expense': 'EXPENSE',
    'expense_direct_cost': 'DIRECTCOSTS',
    'liability_payable': 'INVENTORY',
}


class XeroTransactions:

    def __init__(self, instance_id, env=False):
        self.instance_id = instance_id
        self.env = env

    #####################
    # Import Operations #
    #####################

    def get_object_data(self, xero, resource, import_cron_date, **kwargs):
        if kwargs.get("from_cron"):                                ##### FOR CRON ######
            object_resource = resource.split('?')[0] if '?' in resource else resource
            if object_resource in ["Quotes", "PurchaseOrders"]:
                resource += f"?DateFrom={import_cron_date.date()}&Order=Date ASC"
                object_datalist = xero.get(resource, params={"page": kwargs.get("page")})
            elif object_resource in ["Invoices","CreditNotes"]:
                resource += f' And {import_cron_date}&Order=Date ASC' # Import based on invoice date
                object_datalist = xero.get(resource, params={"page": kwargs.get("page")})
            elif object_resource in ['Payments']:
                resource += f'?where={import_cron_date}&Order=Date ASC' # Import based on create date
                object_datalist = xero.get(resource, params={"page": kwargs.get("page")})
            else:
                object_datalist = xero.get(resource, params={"page": kwargs.get("page")},
                                    headers={
                                        "If-Modified-Since": import_cron_date,
                                    })
        elif kwargs.get('object_id'):                                  ##### FOR IMPORT BY ID ######
            object_resource = resource.split('?')[0] if '?' in resource else resource
            if object_resource in ['Contacts', 'Invoices']:
                object_datalist = xero.get(resource, params={'IDs': kwargs.get('object_id')})
            else:
                object_datalist = []
                object_ids = kwargs.get('object_id').split(',')
                for order_id in list(set(object_ids)):
                    if order_id:
                        object_datalist.append(xero.get(resource, resource_id=order_id))
        elif kwargs.get('min_date') and kwargs.get('max_date'):      ##### FOR IMPORT BY MIN AND MAX ######
            min_date, max_date = kwargs.get('min_date'), kwargs.get('max_date')
            if resource in ['Quotes','PurchaseOrders']:
                resource += f'?DateFrom={min_date}&DateTo={max_date}'
                object_datalist = xero.get(resource)
            else:
                params = {
                    'where': f'UpdatedDateUTC >= DateTime({min_date.year},{min_date.month},{min_date.day}) && UpdatedDateUTC < DateTime({max_date.year},{max_date.month},{max_date.day})'
                }
                object_datalist = xero.get(resource, params=params)
        else:                                                  ##### FOR IMPORT BY ALL ######
            if resource in ['Items','Accounts']:
                object_datalist = xero.get(resource)
            else:
                object_datalist = xero.get(resource, params={"page": kwargs.get("page")})
        return object_datalist
    
    def get_accounts(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        import_account_date = instance_id.datetime_to_string(instance_id.import_account_date) if kwargs.get('from_cron') else False
        accounts = self.get_object_data(xero, "Accounts", import_account_date, **kwargs)
        if isinstance(accounts, list):
            for account in accounts:
                if not account.get("json"):
                    kwargs.update({'message': f"Error in Getting Accounts: {account.get('f_error')}"})
                else:
                    accounts = account.get("json", {}).get("Accounts", [])
                    processed_accounts = map(self._get_account, accounts)
                    data_list.extend(processed_accounts)
        else:
            if not accounts.get("json"):
                kwargs.update({'message': f"Error in Getting Orders: {account.get('f_error')}"})
            else:
                data_list = list(map(self._get_account, accounts.get("json").get("Accounts")))
            if data_list and data_list[-1].get('date_order') and kwargs.get('from_cron'):
                instance_id.import_order_date = data_list[-1].get('date_order')
        kwargs.update(stop=True)
        return kwargs, data_list

    def _get_account(self, account) -> dict:
        account_type = IN_ACCOUNT.get(account.get('Type'), 'asset_cash')
        return {
            'name': account.get('Name', ''),
            'instance_id': self.instance_id.id,
            'remote_id': account.get('AccountID', ''),
            'code': account.get('Code') or account.get('BankAccountNumber', ''),
            'account_type': account_type
        }

    def get_customers(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        import_partner_date = instance_id.datetime_to_string(instance_id.import_customer_date) if kwargs.get("from_cron") else False
        customers = self.get_object_data(xero, "Contacts", import_partner_date, **kwargs)
        if not customers.get("json"):
            kwargs.update({'message': f"Error in getting Customers: {customers.get('f_error')}"})
        else:
            data_list = list(map(self._get_customer, customers.get("json").get("Contacts")))
        return kwargs, data_list

    def _get_customer(self, contact) -> dict:
        name = contact.get('FirstName', '')+" "+contact.get('LastName', '')
        if contact.get("Name"):
            name = contact.get("Name", '')
        vals = {
            'name': name,
            'instance_id': self.instance_id.id,
            'remote_id': contact.get("ContactID"),
            'email': contact.get("EmailAddress", ""),
            'website': contact.get('Website', False),
            'type': 'contact',
            'customer_type': 'supplier' if contact.get('IsSupplier') else 'customer',
        }
        vals.update(self._get_default_phone(contact.get("Phones")))
        contacts = []
        for contact in contact.get("Addresses"):
            if contact.get('AddressLine1') or contact.get('AddressLine2') or \
                contact.get('AddressLine3') or contact.get('AddressLine4'):
                if contact.get('AddressType') == 'POBOX':
                    pobox_values = self._get_street_address(name, contact)
                    pobox_values.pop('type', False)
                    pobox_values.pop('name', False)
                    vals.update(pobox_values)
                else:
                    contacts.append(self._get_street_address(name, contact))
        vals.update(contacts=contacts)
        return vals

    def _get_default_phone(self, phones: list) -> dict:
        vals = {}
        for phone in phones:
            if phone.get("PhoneType") == "DEFAULT":
                vals["phone"] = phone.get("PhoneNumber", '')
            elif phone.get("PhoneType") == "MOBILE":
                vals["mobile"] = phone.get("PhoneNumber", '')
        return vals

    def _get_street_address(self, name, address: dict) -> dict:
        vals = {}
        type = "other"
        region = address.get('Region', '')
        country = address.get('Country')
        if address.get("AddressType") == "STREET":
            type = "delivery"
        street2 = ''
        street2 += address.get('AddressLine1','') + \
            " " if address.get('AddressLine1') else ""
        street2 += address.get("AddressLine2",'') + \
            " " if address.get("AddressLine2") else ""
        street2 += address.get("AddressLine3", '') + \
            " " if address.get("AddressLine3") else ""
        street2 += address.get("AddressLine4", '') + \
            " " if address.get("AddressLine4") else ""
        if region:
            street2 += region +" "
        if country:
            street2 += country
        vals.update({
            'name': name,
            'type': type,
            'street': address.get("AttentionTo", ""),
            'city': address.get("City", ""),
            'zip': address.get("PostalCode", ""),
            'street2': street2,
        })
        return vals

    def get_products(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        import_product_date = instance_id.datetime_to_string(instance_id.import_product_date) if kwargs.get("from_cron") else False
        products = self.get_object_data(xero, "Items", import_product_date, **kwargs)
        if isinstance(products, list):
            for product in products:
                if not product.get("json"):
                    kwargs.update({'message': f"Error in Getting Products: {product.get('f_error')}"})
                else:
                    products = product.get("json", {}).get("Items", [])
                    processed_products = map(self._get_product, products)
                    data_list.extend(processed_products)
        else:
            if not products.get("json"):
                kwargs.update({'message': f"Error in Getting Products: {product.get('f_error')}"})
            else:
                data_list = list(map(self._get_product, products.get("json").get("Items")))
        kwargs.update(stop=True) # Getting All Items in one request
        return kwargs, data_list

    def _get_product(self, product) -> dict:
        return {
            'name': product.get("Name"),
            'instance_id': self.instance_id.id,
            'remote_id': product.get("ItemID"),
            'type': "product" if product.get("IsTrackedAsInventory") else "service",
            'list_price': product.get("SalesDetails", {}).get("UnitPrice"),
            'default_code': product.get("Code"),
            'description_sale': product.get("Description"),
            'description_purchase': product.get("PurchaseDescription"),
            'standard_price': product.get('PurchaseDetails', {}).get('UnitPrice'),
            'qty_available': product.get('QuantityOnHand') if product.get("IsTrackedAsInventory") else 0,
            'purchase_ok': product.get("IsPurchased"),
            'sale_ok': product.get("IsSold")
        }

    def get_orders(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        resource = "Quotes"
        import_order_date = instance_id.import_order_date if kwargs.get("from_cron") else False
        orders = self.get_object_data(xero, resource, import_order_date, **kwargs)
        if isinstance(orders, list):
            for order in orders:
                if not order.get("json"):
                    kwargs.update({'message': f"Error in Getting Orders: {order.get('f_error')}"})
                else:
                    quotes = order.get("json", {}).get("Quotes", [])
                    processed_quotes = map(self._get_order, quotes)
                    data_list.extend(processed_quotes)
        else:
            if not orders.get("json"):
                kwargs.update({'message': f"Error in Getting Orders: {orders.get('f_error')}"})
            else:
                data_list = list(map(self._get_order, orders.get("json").get("Quotes")))
            if data_list and data_list[-1].get('date_order') and kwargs.get('from_cron'):
                instance_id.import_order_date = data_list[-1].get('date_order')
        if data_list and data_list[-1].get('date_order') and kwargs.get('from_cron'):
            instance_id.import_order_date = data_list[-1].get('date_order')
        return kwargs, data_list

    def _get_order(self, order) -> dict:
        vals = {
            'instance_id': self.instance_id.id,
            'remote_id': order.get("QuoteID"),
            'xero_doc_number': order.get("Reference"),
            'partner_id': order.get("Contact", {}).get("ContactID"),
            'currency_code': order.get('CurrencyCode'),
            'order_state': order.get('Status'),
            'origin': order.get('QuoteNumber',),
        }
        date_string = order.get("DateString")
        if date_string:
            date_string = date_string.replace("T", ' ')
            vals["date_order"] = date_string
        order_line = self._create_sale_order_lines(order.get("LineItems"))
        vals["order_lines"] = order_line
        return vals

    def _create_sale_order_lines(self, line_items: list) -> list:
        return list(map(self._get_order_line_item, line_items))

    def _get_order_line_item(self, item: dict) -> tuple:
        return dict(
            product_id=item.get("ItemCode"),
            default_code=item.get("ItemCode"),
            product_uom_qty=item.get("Quantity"),
            price_unit=item.get("UnitAmount"),
            name=item.get("Description"),
            line_taxes=self.get_line_taxes(
                item.get('TaxType')) if item.get('TaxType') else False,
            discount = item.get('DiscountRate'),
        )

    # === Open: Purchase order get API method
    def get_purchase_orders(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        resource = "PurchaseOrders"
        import_purchase_order_date = instance_id.import_purchase_order_date if kwargs.get("from_cron") else False
        purchase_orders = self.get_object_data(xero, resource, import_purchase_order_date, **kwargs)
        if isinstance(purchase_orders, list):
            for purchase_order in purchase_orders:
                if not purchase_order.get("json"):
                    kwargs.update({'message': f"Error in Getting Purchase Orders: {purchase_order.get('f_error')}"})
                else:
                    purchaseorders = purchase_order.get("json", {}).get("PurchaseOrders", [])
                    processed_quotes = map(self._get_purchase_order, purchaseorders)
                    data_list.extend(processed_quotes)
        else:
            if not purchase_orders.get("json"):
                kwargs.update({'message': f"Error in Getting Orders: {purchase_orders.get('f_error')}"})
            else:
                if purchase_orders.get("json").get("Quotes"):
                    data_list = list(map(self._get_purchase_order, purchase_orders.get("json").get("Quotes")))
                else:
                    data_list=''
        if data_list and data_list[-1].get('date_order') and kwargs.get('from_cron'):
            instance_id.import_purchase_order_date = data_list[-1].get('date_order')
        return kwargs, data_list

    def _get_purchase_order(self, order) -> dict:
        xero = self.instance_id.get_xeroapi_object()
        xero_id = order.get('PurchaseOrderID')
        if order.get('IsDiscounted'):
            order = xero.get("PurchaseOrders", resource_id=xero_id)
            if not order.get("json"):
                raise Exception(order.get('f_error'))
            order = order.get("json").get("PurchaseOrders")[0]
        remote_po_states = {
            'DRAFT': 'draft',
            'SUBMITTED': 'draft',
            'AUTHORISED': 'sale',
            'BILLED': 'done',
            'DELETED': 'cancelled',
        }
        vals = {
            'instance_id': self.instance_id.id,
            'remote_id': order.get("PurchaseOrderID"),
            'xero_doc_number': order.get("Reference"),
            'partner_id': order.get("Contact", {}).get("ContactID"),
            'currency_code': order.get('CurrencyCode'),
            'order_state': remote_po_states.get(order.get('Status','DRAFT')),
            'origin': order.get('PurchaseOrderNumber')
        }
        date_string = order.get("DateString")
        if date_string:
            date_string = date_string.replace("T", ' ')
            vals["date_order"] = date_string
        order_line = self._create_purchase_order_lines(order.get("LineItems"))
        vals["order_lines"] = order_line
        return vals

    def _create_purchase_order_lines(self, line_items: list) -> list:
        data_list = []
        for data in line_items:
            data_list.append(self._get_purchase_order_line_item(data))
            if data.get('DiscountRate'):
                data_list.append(self._get_purchase_discount_line_item(data))
        return data_list

    def _get_purchase_order_line_item(self, item: dict) -> tuple:
        return dict(
            product_id=item.get("ItemCode"),
            default_code=item.get("ItemCode"),
            product_qty=item.get("Quantity"),
            price_unit=item.get("UnitAmount"),
            name=item.get("Description"),
            line_taxes=self.get_line_taxes(
                item.get('TaxType')) if item.get('TaxType') else False,
        )

    def _get_purchase_discount_line_item(self, item):
        return dict(
                name= "Discount",
                product_qty = 1,
                price_unit= -(item.get('UnitAmount') * (item.get('DiscountRate', 0)/100))*item.get('Quantity'),
                line_source = 'discount',
                line_taxes=self.get_line_taxes(
                    item.get('TaxType')) if item.get('TaxType') else False,
                account_remote_id = item.get('AccountID'),
        )

    # === Close: Purchase order get API method

    def get_invoices(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        resource = "Invoices"
        if kwargs.get('move_type') and kwargs.get('move_type') == 'in_invoice':
            resource += '?where=Type=="ACCPAY"'
            cron_date_field = 'import_bill_date'
            import_cron_date = instance_id.import_bill_date
        else:
            cron_date_field = 'import_invoice_date'
            resource += '?where=Type=="ACCREC"'
            import_cron_date = instance_id.import_invoice_date
        date_time = self.get_xero_cron_datetime(import_cron_date) if kwargs.get("from_cron") else False
        invoices = self.get_object_data(xero, resource, date_time, **kwargs)
        if not invoices.get("json"):
            err_message = f"Error in Getting invoices : {invoices.get('f_error')}"
            kwargs.update({'message': err_message})
        else:
            data_list = list(map(self._get_invoice, invoices.get("json").get("Invoices")))
        if data_list and data_list[-1].get('invoice_date') and kwargs.get("from_cron"):
            instance_id.write({cron_date_field: data_list[-1].get('invoice_date')})
        return kwargs, data_list

    def _get_invoice(self, invoice) -> dict:
        xero = self.instance_id.get_xeroapi_object()
        xero_id = invoice.get('InvoiceID')
        if invoice.get('IsDiscounted'):
            invoice = xero.get("Invoices", resource_id=xero_id)
            if not invoice.get("json"):
                raise Exception(invoice.get('f_error'))
            invoice = invoice.get("json").get("Invoices")[0]
        vals = {
            'instance_id': self.instance_id.id,
            'remote_id': xero_id,
            'partner_id': invoice.get("Contact", {}).get("ContactID"),
            'invoice_date': invoice.get("DateString", "").replace('T', ' '),
            'invoice_date_due': invoice.get("DueDateString", '').replace('T', ' '),
            'xero_doc_number': invoice.get('Reference'),
            'currency_code': invoice.get('CurrencyCode'),
            'ref': invoice.get('InvoiceNumber'),
        }
        invoice_line_ids = self._get_invoice_line_items(
            invoice.get("LineItems", []))
        if invoice.get('Type') == "ACCPAY":
            vals.update({'type': 'in_invoice'})
        else: # ACCREC
            vals.update({'type': 'out_invoice'})
        vals["invoice_lines"] = invoice_line_ids
        return vals

    def _get_invoice_line_items(self, line_items: list) -> list:
        return list(map(self._get_invoice_line_item, line_items))

    def _get_invoice_line_item(self, item: dict) -> tuple:
        return dict(
            product_id=item.get("ItemCode"),
            default_code=item.get('ItemCode'),
            product_uom_qty=item.get("Quantity"),
            price_unit=item.get("UnitAmount"),
            name=item.get("Description"),
            account_remote_id = item.get('AccountID'),
            line_taxes=self.get_line_taxes(
                item.get('TaxType')) if item.get('TaxType') else False,
            discount = item.get('DiscountRate')
        )

    def get_payments(self, xero, **kwargs) -> list:
        instance_id = self.instance_id
        data_list = []
        resource = "Payments"
        date_time = self.get_xero_cron_datetime(instance_id.import_payment_date) if kwargs.get('from_cron') else False
        payments = self.get_object_data(xero, resource, date_time, **kwargs)
        if isinstance(payments, list):
            for payment in payments:
                if not payment.get("json"):
                    kwargs.update({'message': f"Error in Getting Purchase Orders: {payment.get('f_error')}"})
                else:
                    payments = payment.get("json", {}).get(resource, [])
                    processed_payments = map(self._get_payment, payments)
                    data_list.extend(processed_payments)
        else:
            if not payments.get("json"):
                kwargs.update({'message': f"Error in Getting Payments: {payments.get('f_error')}"})
            else:
                data_list = list(map(self._get_payment, payments.get("json").get(resource)))
        if data_list and kwargs.get("from_cron"):
            date_time = payments.get("json").get("Payments")[-1].get('Date') # /Date(1700611200000+0000)/
            if date_time:
                date_time = date_time.replace('/Date(', '').replace(')/','')
                if '+' in date_time:
                    date_time = date_time.split('+')[0]
                try:
                    date_time = datetime.fromtimestamp(int(date_time) / 1e3)
                    instance_id.import_payment_date = date_time
                except Exception as e:
                    _logger.error(e, exc_info=True)
        return kwargs, data_list

    def _get_payment(self, payment) -> dict:
        return {
            'remote_id': payment.get("PaymentID"),
            'instance_id': self.instance_id.id,
            'partner_type': "customer",
            'partner_id': payment.get("Invoice", {}).get("Contact", {}).get("ContactID"),
            'amount': payment.get("Amount"),
            'communication': payment.get("Reference", ""),
            'payment_date': str(self.instance_id.epoch_to_date(payment.get("Date"))),
            'payment_type': "outbound" if payment.get('PaymentType') == "ACCPAYPAYMENT" else "inbound",
            'invoice_ids': payment.get('Invoice', {}).get('InvoiceID')
        }

    # ===== Open: Credit Notes GET API method: 
    def get_credit_notes(self, xero, **kwargs):
        instance_id = self.instance_id
        data_list = []
        resource = 'CreditNotes'
        if kwargs.get('move_type', False) and kwargs.get('move_type') == 'in_refund':
            cron_date_field = 'import_refund_date'
            resource += '?where=Type=="ACCPAYCREDIT"'
            import_cron_date = instance_id.import_refund_date
        else:
            cron_date_field = 'import_credit_notes_date'
            resource += '?where=Type=="ACCRECCREDIT"'
            import_cron_date = instance_id.import_credit_notes_date
        date_time = self.get_xero_cron_datetime(import_cron_date) if kwargs.get("from_cron") else False
        if kwargs.get('filter_type') != 'all':
            resource = 'CreditNotes'
        credit_notes = self.get_object_data(xero, resource, date_time, **kwargs)
        if isinstance(credit_notes, list):
            for credit_note in credit_notes:
                if not credit_note.get("json"):
                    kwargs.update({'message': f"Error in Getting Purchase Orders: {credit_note.get('f_error')}"})
                else:
                    creditNotes = credit_note.get("json", {}).get('CreditNotes', [])
                    processed_creditNotes = map(self._get_credit_note, creditNotes)
                    data_list.extend(processed_creditNotes)
        else:
            if not credit_notes.get("json"):
                kwargs.update({'message': f"Error in Getting Payments: {credit_notes.get('f_error')}"})
            else:
                data_list = list(map(self._get_credit_note, credit_notes.get("json").get('CreditNotes')))
        if data_list and kwargs.get("from_cron"):
            return_cron_date = data_list[-1].get('invoice_date')
            if return_cron_date:
                instance_id.write({cron_date_field: data_list[-1].get('invoice_date')})
        return kwargs, data_list
    
    def _get_credit_note(self, invoice):
        xero_id = invoice.get('CreditNoteID')
        vals = {
            'instance_id': self.instance_id.id,
            'remote_id': xero_id,
            'partner_id': invoice.get("Contact", {}).get("ContactID"),
            'invoice_date': invoice.get("DateString", "").replace('T', ' '),
            'xero_doc_number': invoice.get('Reference'),
            'currency_code': invoice.get('CurrencyCode'),
            'ref': invoice.get('CreditNoteNumber'),
        }
        if invoice.get('Type') == "ACCPAYCREDIT":
            vals.update({'type': 'in_refund'})
        else:
            vals.update({'type': 'out_refund'})
        invoice_line_ids = self._get_invoice_line_items(
            invoice.get("LineItems", []))
        vals["invoice_lines"] = invoice_line_ids
        return vals
    # ===== Close: Credit Notes GET API method
    
    #==== Open: Journal/Payment Get API method
    def get_journals(self, xero, **kwargs):
        data_list = []
        journals = self.get_object_data(xero, 'ManualJournals', False, **kwargs)
        if isinstance(journals, list):
            for journal in journals:
                if not journal.get("json"):
                    kwargs.update({'message': f"Error in Getting Journals {journal.get('f_error')}"})
                else:
                    journals = journal.get("json", {}).get('ManualJournals', [])
                    processed_journals = map(self.get_journal, journals)
                    data_list.extend(processed_journals)
        else:
            if not journals.get("json"):
                kwargs.update({'message': f"Error in Getting Journals, {journals.get('f_error')}"})
            else:
                data_list = list(map(self.get_journal, journals.get('json').get('ManualJournals')))
        return kwargs, data_list     
        
    def get_journal(self, journal):
        return {
            'instance_id':self.instance_id.id,
            'remote_id':journal.get('ManualJournalID'),
            'name':journal.get('Narration'),
        }
    #==== Close: Journal/Payment Get API method

    def get_line_taxes(self, tax_type):
        xero = self.instance_id.get_xeroapi_object()
        match_tax = self.instance_id.match_tax_mapping(remote_id=tax_type)
        if match_tax and match_tax.name:
            return [{'remote_id': tax_type}]
        data = []
        taxes = self.get_tax_by_type(xero, tax_type)
        for tax in taxes:
            data.append({
                'rate': tax.get('amount'),
                'name': tax.get('name'),
                'type': "percent",
                'include': tax.get('price_include'),
                'remote_id': tax.get('remote_id'),
            })
        return data

    def get_taxes(self, xero, **kwargs):
        data_list  = []
        taxes = self.get_object_data(xero, 'TaxRates', False, **kwargs)
        if isinstance(taxes, list):
            for tax in taxes:
                if not tax.get('json'):
                    kwargs.update({'message': f"Error in Getting Taxes {tax.get('f_error')}"})
                else:
                    taxes = tax.get("json", {}).get('TaxRates', [])
                    processed_taxes = map(self.get_tax, taxes)
                    data_list.extend(processed_taxes)
        else:
            if not taxes.get('json'):
                kwargs.update({'message': f"Error in Getting Taxes {taxes.get('f_error')}"})
            else:
                data_list = list(map(self.get_tax, taxes.get('json').get('TaxRates')))
        kwargs.update({'stop':True})
        return kwargs, data_list

    # Call it from order/invoice using TaxType from response
    def get_tax_by_type(self, xero, type) -> list:
        # eg: vals = self.get_tax_by_type(xero, "TAX001")
        from urllib.parse import quote_plus
        string = "where=TaxType"+quote_plus(f'=="{type}"')
        taxes = xero.get('TaxRates?'+string)
        if taxes.get('json'):
            return list(map(self.get_tax, taxes.get('json').get('TaxRates')))
        else:
            return False

    def get_tax(self, tax) -> dict:
        return {
            'instance_id': self.instance_id.id,
            'remote_id': tax.get('TaxType'),
            'name': tax.get('Name'),
            'amount': tax.get('EffectiveRate'),
            'amount_type': 'percent',
            'active': True if tax.get('Status') == "ACTIVE" else False,
            'price_include': True if self.instance_id.default_tax_type == "include" else False
            # 'type_tax_use':'sale',
        }
    
####################
# Export Operation #
####################

    def post_account(self, xero, record, **kwargs):
        exported, xero_id = False, False
        acc_type = OUT_ACCOUNT.get(record.account_type, 'BANK')
        data = {
            "Name": record.name,
            "Type": acc_type,
            "Code": record.code
        }
        if acc_type == 'BANK':
            data.update({"BankAccountNumber": record.code})
        response = xero.put("Accounts", json=data)
        if response.get("json"):
            exported = True
            xero_id = response.get('json').get('Accounts')[0].get("AccountID")
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs

    def post_customer(self, xero, record, **kwargs):
        customer_data = record.read()[0]
        exported, xero_id = False, False
        response = xero.put("Contacts", json={
            "Contacts": [{
                "Name": customer_data.get('name'),
                "EmailAddress": customer_data.get('email','') or '',
                "TaxNumber": customer_data.get('vat', '') or '',
                "Addresses": [
                    {
                        "AddressType": "POBOX",
                        "AddressLine1": customer_data.get('street','') or '',
                        "AddressLine2": customer_data.get('street2','') or '',
                        "City": customer_data.get('city','') or '',
                        "PostalCode": customer_data.get('zip', '') or ''
                    }],
                "Phones": [{
                    "PhoneType": "DEFAULT",
                    "PhoneNumber": customer_data.get('phone', '') or ''
                }, {
                    "PhoneType": "MOBILE",
                    "PhoneNumber": customer_data.get('mobile', '') or ''
                }]
            }]
        })
        if response.get("json"):
            exported = True
            xero_id = response.get('json').get('Contacts')[0].get("ContactID")
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs

    def post_product(self, xero, record, **kwargs):
        product_data = record.read()[0]
        exported, xero_id, remote_itemCode = False, False, False
        if not product_data.get('default_code') and not self.instance_id.product_sequence_id:
            raise XeroProductRequiredParam(
                "Code is Required Parameter For Xero Product. Define Product Internal Reference Code or Set Product Sequence from Connected Instance Configuration.")
        itemCode = product_data.get('default_code') or self.instance_id.product_sequence_id.next_by_id()
        vals = {
            'Code': itemCode,
            'Name': product_data.get('name'),
        }
        if product_data.get('purchase_ok'):
            vals['IsPurchased'] = product_data.get('purchase_ok', '')
            vals['PurchaseDescription'] = product_data.get('description_purchase', '') or ''
            vals['PurchaseDetails'] = {
                "UnitPrice": product_data.get('standard_price')
            }
        if product_data.get('sale_ok'):
            vals['Description'] = product_data.get('description_sale', '') or ''
            vals['SalesDetails'] = {
                "UnitPrice": product_data.get('list_price')
            }
        response = xero.put("Items", json=vals)
        if response.get("json"):
            exported = True
            xero_id = response.get("json").get('Items')[0].get('ItemID')
            if not record.default_code:
                remote_itemCode = itemCode
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, remote_itemCode, kwargs

    def post_order(self, xero, record, **kwargs):
        instance_id = self.instance_id
        exported, xero_id = False, False
        xero_order_status = {
            'sent': 'Sent',
            'sale': 'ACCEPTED',
            'done': 'INVOICED',
            'cancel': 'DECLINED'
        }
        customer_id = instance_id.match_customer_mapping(
            odoo_id=record.partner_id.id)
        if customer_id:
            customer_id = customer_id.remote_id
        else:
            message = f'Customer {record.partner_id.name} is not mapped'
            _logger.error(message)
            kwargs.update({'message': message})
            return exported, xero_id , kwargs
        date_order = record.date_order or record.create_date
        vals = {
            'Contact': {
                "ContactID": customer_id or '',
            },
            'Reference': record.xero_doc_number or '',
            'Date': instance_id.datetime_to_string(date_order),
            "Terms": record.payment_term_id.name if record.payment_term_id else '',
            'LineAmountTypes': "Inclusive" if instance_id.default_tax_type == "include" else "Exclusive",
            'Status': xero_order_status.get(record.state, 'DRAFT'),
            'CurrencyCode' : record.currency_id.name,
            'LineItems': self._get_order_lines(record)
        }
        if instance_id.sync_sale_order_name:
            vals.update({'QuoteNumber': record.name})
        response = xero.put("Quotes", json=vals)
        if response.get("json"):
            exported = True
            xero_id = response.get("json").get('Quotes')[0].get('QuoteID')
            record.origin = response.get("json").get("Quotes")[0].get('QuoteNumber')
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs

    def _get_order_lines(self, record: object) -> list:
        return list(map(self._get_order_line, record.order_line))

    def _get_order_line(self, order_line: object) -> dict:
        tax_code = ''
        itemCode = self.instance_id.match_product_mapping(
            odoo_id=order_line.product_id)
        if itemCode:
            itemCode = itemCode.default_code
        else:
            raise Exception(
                f'Product {order_line.product_id.name} is not mapped')
        if hasattr(order_line.order_id, 'purchase_order_count'):
            taxes = order_line.tax_id # SO
        else:
            taxes = order_line.taxes_id # PO
        if taxes:
            tax_code = self.search_accounting_mappings('tax', taxes[0])
        data = dict(
            ItemCode=itemCode,
            Description=order_line.name,
            Quantity=order_line.product_uom_qty,
            UnitAmount=order_line.price_unit,
            TaxType = tax_code,
        )
        if order_line.order_id._name == 'sale.order':
            data.update({'DiscountRate': order_line.discount or 0,})
        return data

    # == Open: Purchase Order POST method
    def post_purchase_order(self, xero, record, **kwargs):
        instance_id = self.instance_id
        exported, xero_id = False, False
        xero_order_status = {
            'sent': 'SUBMITTED',
            'purchase': 'AUTHORISED',
            'done': 'BILLED',
            'cancel': 'DELETED'
        }
        customer_id = instance_id.match_customer_mapping(
            odoo_id=record.partner_id.id)
        if customer_id:
            customer_id = customer_id.remote_id
        else:
            message = f'Customer {record.partner_id.name} is not mapped'
            kwargs.update({'message': message})
            return exported, xero_id , kwargs
        date_order = record.date_order or record.create_date
        vals = {
            'Contact': {
                "ContactID": customer_id or '',
            },
            'Reference': record.xero_doc_number or '',
            'Date': instance_id.datetime_to_string(date_order),
            "Terms": record.payment_term_id.name if record.payment_term_id else "",
            'Status': xero_order_status.get(record.state, 'DRAFT'),
            'LineAmountTypes': "Inclusive" if instance_id.default_tax_type == "include" else "Exclusive",
            'CurrencyCode' : record.currency_id.name,
            'LineItems': self._get_order_lines(record)
        }
        if instance_id.sync_sale_order_name:
            vals.update({'PurchaseOrderNumber': record.name})
        response = xero.put("PurchaseOrders", json=vals)
        if response.get("json"):
            exported = True
            xero_id = response.get("json").get('PurchaseOrders')[0].get('PurchaseOrderID')
            record.origin = response.get("json").get('PurchaseOrders')[0].get('PurchaseOrderNumber')
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs
    # == Close: Purchase Order POST method

    def post_invoice(self, xero, record, **kwargs):
        """
        Type:
            ACCPAY:	A bill - commonly known as an Accounts Payable or supplier invoice
            ACCREC:	A sales invoice - commonly known as an Accounts Receivable or customer invoice
        """
        exported, xero_id = False, False
        instance_id = self.instance_id
        # InvoiceNumber = 'DRAFT '+ str(record.id) if not record.state == 'posted' else record.name
        Type = 'ACCREC'
        xero_invoice_status = {
            'posted': 'AUTHORISED',
        }
        if record.move_type == "in_invoice":
            Type = 'ACCPAY'
        customer_id = instance_id.match_customer_mapping(
            odoo_id=record.partner_id.id)
        if customer_id:
            customer_remote_id = customer_id.remote_id
            if 'delivery_' in customer_remote_id:
                customer_remote_id = customer_remote_id.replace('delivery_', '')
            elif 'invoice_' in customer_remote_id:
                customer_remote_id = customer_remote_id.replace('invoice_', '')        
        else:
            message = f'Customer {record.partner_id.name} [ID: {record.partner_id.id}] is not mapped'
            kwargs.update({'message': message})
            return exported, xero_id , kwargs
        inv_date = record.invoice_date or record.create_date
        invoice_date = instance_id.datetime_to_string(inv_date)
        due_date = instance_id.datetime_to_string(record.invoice_date_due) or ''
        json = {
            'Invoices': [{
                'Type': Type,
                'Contact': {
                    "ContactID": customer_remote_id or ''
                },
                # "InvoiceNumber": InvoiceNumber,
                'DateString': invoice_date,
                'DueDateString': due_date,
                # "ExpectedPaymentDate": "2009-10-20T00:00:00",
                'Reference': record.xero_doc_number or '', #if Type == 'ACCREC' else False,
                'CurrencyCode' : record.currency_id.name,
                'Status': xero_invoice_status.get(record.state, 'DRAFT'),
                'LineAmountTypes': "Inclusive" if instance_id.default_tax_type == "include" else "Exclusive",
                'LineItems': self._get_invoice_lines(record)
            }]}
        response = xero.put("Invoices", json=json)
        if response.get("json"):
            exported = True
            xero_id = response.get('json').get('Invoices')[0].get('InvoiceID')
            InvoiceNumber = response.get('json').get('Invoices')[0].get('InvoiceNumber')
            if InvoiceNumber and not record.ref:
                record.write({'ref': InvoiceNumber})
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs

    def _get_invoice_lines(self, record: object) -> list:
        return list(map(self._get_invoice_line, record.invoice_line_ids))

    def _get_invoice_line(self, line_id: object) -> dict:
        tax_code = ''
        itemCode = self.instance_id.match_product_mapping(
            odoo_id=line_id.product_id)
        if itemCode:
            itemCode = itemCode.default_code
        else:
            raise Exception(f'Line Product {line_id.product_id.name} is not mapped')
        account_code = self.search_accounting_mappings('account', line_id.account_id)
        if line_id.tax_ids:
            tax_code = self.search_accounting_mappings('tax', line_id.tax_ids[0])
        data = dict(
            ItemCode = itemCode or '',
            Description = line_id.name,
            Quantity = line_id.quantity,
            UnitAmount = line_id.price_unit,
            # AccountCode = account_code,
            AccountId = account_code,
            TaxType = tax_code,
        )
        if not line_id.move_id.move_type == 'in_invoice':
            data.update({'DiscountRate': line_id.discount})
        return data

    # == Open: Credit Notes POST method
    def post_credit_notes(self, xero, record, **kwargs):
        """
        Type:
            ACCPAYCREDIT	An Accounts Payable(supplier) Credit Note
            ACCRECCREDIT	An Account Receivable(customer) Credit Note
        """
        exported, xero_id = False, False
        instance_id = self.instance_id
        # InvoiceNumber = 'DRAFT '+ str(record.id) if not record.state == 'posted' else record.name
        Type = 'ACCRECCREDIT'
        xero_invoice_status = {
            'posted': 'AUTHORISED',
        }
        if record.move_type == "in_refund":
            Type = 'ACCPAYCREDIT'
        customer_id = instance_id.match_customer_mapping(
            odoo_id=record.partner_id.id)
        if customer_id:
            customer_id = customer_id.remote_id
        else:
            message = f'Vendor {record.partner_id.name} [ID: {record.partner_id.id}] is not mapped'
            kwargs.update({'message': message})
            return exported, xero_id , kwargs
        inv_date = record.invoice_date or record.create_date
        date = instance_id.datetime_to_string(inv_date)
        due_date = instance_id.datetime_to_string(record.invoice_date_due) or ''
        response = xero.put("CreditNotes", json={
            'CreditNotes': [{
                'Type': Type,
                'Contact': {
                    "ContactID": customer_id or ''
                },
                # "InvoiceNumber": InvoiceNumber,
                'DateString': date,
                'DueDateString': due_date,
                # "ExpectedPaymentDate": "2009-10-20T00:00:00",
                'Reference': record.xero_doc_number or '' if Type == 'ACCRECCREDIT' else '',
                'CurrencyCode' : record.currency_id.name,
                'LineAmountTypes': "Inclusive" if instance_id.default_tax_type == "include" else "Exclusive",
                'Status': xero_invoice_status.get(record.state, 'DRAFT'),
                'LineItems': self._get_invoice_lines(record),
            }]})
        if response.get("json"):
            exported = True
            xero_id = response.get('json').get('CreditNotes')[0].get('CreditNoteID')
            CreditNoteNumber = response.get('json').get('CreditNotes')[0].get('CreditNoteNumber')
            if CreditNoteNumber and not record.ref:
                record.write({'ref': CreditNoteNumber})
        else:
            kwargs.update({'message': response.get('f_error')})
        return exported, xero_id, kwargs
    # == Close: Credit Notes POST method

    def post_payment(self, xero, record, **kwargs):
        exported, xero_id, message = False, False, False
        instance_id = self.instance_id
        inv_id = record.reconciled_invoice_ids
        if not inv_id or len(inv_id) > 1: # Group Payment Feature not Available
            message = f"Payment {record.name} is not connected to any invoice"
        else:
            invoice_id = instance_id.match_invoice_mapping(odoo_id=inv_id.id)
            if not invoice_id:
                message = f"Reconciled Invoice [ID: {inv_id.id}] is not mapped"
            else:
                invoice_id = invoice_id.remote_id
                partner_id = inv_id.partner_id
                if inv_id.move_type in ['out_invoice', 'out_refund']:
                    account_id = partner_id.property_account_receivable_id
                else:
                    account_id = partner_id.property_account_payable_id
                acc_id = account_id.id
                account_mapping = instance_id.match_account_mapping(odoo_id=acc_id)
                if not account_mapping:
                    message = f"Account <b>'[{account_id.code}] {account_id.name}'</b> [ID: {acc_id}] is not mapped"
                account_remote_id = account_mapping.remote_id
                response = xero.put("Payments", json={
                    'Invoice': {"InvoiceID": invoice_id or ''},
                    'Account': {"AccountID": account_remote_id, 'Code': account_mapping.remote_account_code},
                    'Date': instance_id.datetime_to_string(record.date),
                    'Amount': record.amount,
                    'IsReconciled':	record.is_reconciled,
                })
                if response.get("json"):
                    exported = True
                    xero_id = response.get("json").get('Payments')[0].get('PaymentID')
                else:
                    kwargs.update({'message': response.get('f_error')})
        if message:
            kwargs.update({'message': message})
        return exported, xero_id, kwargs

    # Common method to search mappings for tax and account:
    def search_accounting_mappings(self, object, record):
        remote_id = ''
        if record:
            if object == "account":
                return_code = self.instance_id.match_account_mapping(
                    odoo_id=record.id)
            elif object == "tax":
                return_code = self.instance_id.match_tax_mapping(
                    odoo_id=record.id)
            remote_id = return_code.remote_id or ''
        if not remote_id:
            _logger.error(f'Line {object} {record.name} is not mapped')
        return remote_id

    def get_xero_cron_datetime(self, import_cron_date):
        return f"Date>DateTime({import_cron_date.year},{import_cron_date.month},{import_cron_date.day})"
