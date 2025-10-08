Base = {
    'name': '',
    'object':'',
    'instance_id':'',
    'remote_id':'',
}

Account =  Base.update({
    'code':'',
    'account_type':'' #Odoo Account Type
})

Customer = Base.update({
    'company_name':'',
    'email':'',
    'type':'', #type can be contact, delivery, invoice.
	'phone':'',
	'mobile':'',
	'website':'',
	'street':'',
	'street2':'',
	'city':'',
	'zip':'',
	'state_name':'',
	'state_id':'',
	'country_id':'',
	'parent_id':'',
})

#for Simple Product 
ProductTemplate = Base.update({
    'type':'', #product type can be product, service or consumable.
	'list_price':'1',
	'default_code':'',
	'barcode':'',
	'description_sale':'',
	'description_purchase':'',
	'standard_price':'',
	'sale_delay':'',
	'qty_available':'',
	'weight':'',
	'weight_unit':'',
	'width':'',
	'height':'',
	'dimensions_unit':'',
	'image_url':'',
	'hs_code':'',
	'purchase_ok':False,
	'sale_ok':True,
	'variants':[] #format of the product variant is listed below.
})

#for Product with Variants
ProductVariant = ProductTemplate.update({
	'namevalue':[],
	'feed_templ_id':False
})

#Variant Name Value Dict
NameValue = {
    'name': '',
    'value': '',
    'attrib_name_id':'',
    'attrib_value_id':''
}

Order = Base.update({
	'partner_id':'', #Remote Instance Partner ID
	'invoice_partner_id', # Remote Instance Invoice Partner ID
	'shipping_partner_id', # Remote Instance Shipping Partner ID
	'order_state':'',
	'carrier_id':'',
	'invoice_date':'',
	'date_order':'',
	'confirmation_date':'',
	'order_lines':False,
	'currency_code':''
})

OrderLine = {
    'name':'', # For discount line the name should be "Discount".
	'product_uom_qty':'',
	'price_unit':'',
	'product_id':'', #Remote Product Id present in the order line.
	'default_code':'',
	'barcode':'',
	'taxes':'',
	'line_source' : '',
    'variant_id':'',
}

Invoice = Base.update({
	'type':'out_invoice' #default will be out_invoice.
	'partner_id':'', # Remote Instance Partner Id
	'state':'draft',
	'set_paid':False,
	'invoice_state':'',
	'invoice_date':'',
	'invoice_date_due':'',
	'confirmation_date':'',
	'invoice_lines':False,
	'xero_doc_number': '',
	'ref':''
})

InvoiceLine = OrderLine.Copy()

Payment = Base.update({
	'partner_type':'', #default is customer.
	'partner_id':'',  # Remote Partner ID.
	'payment_type':'' # default is inbound.
	'amount':'',
	'communication':'',
	'payment_date':'',
	'payment_method_id':'',
	'invoice_ids':[],  # Invoice ID or list of Invoice IDs
	'order_id': '',

})