from odoo import api, exceptions, fields, models, _
from datetime import datetime, timedelta
from graphql import parse, GraphQLError
import requests
import json
import xmlrpc.client



class SupplierConfiguration(models.Model):
    _name = "supplier.configuration"
    _description = "Supplier Configuration"

    # Main Configration
    name = fields.Char(string='Vendor Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    vendor_short_code = fields.Char(string="Short Code", copy=False)
    shipping_product = fields.Boolean('Add Shipping ?')
    printing_product = fields.Boolean('Add Printing ?')

    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    converted_currency_id = fields.Many2one('res.currency', string='Converted Currency', required=True, default=lambda self: self.env.company.currency_id)

    general_api_key = fields.Char(string='General API Key', copy=False)
    api_key = fields.Char(string='API Key', copy=False)
    endpoint_url = fields.Char(string='Pimcore URL', copy=False)
    get_limit = fields.Integer('Get Limit')
    total_limit = fields.Integer('Total limit')
    import_data = fields.Integer('Import Datas')
    next_schedule_date = fields.Date('Next Schedule Date')
    authorization_id = fields.Many2one("px.supplier.authorization", string="Authorization")

    # Product Configration
    update_product = fields.Selection([
        ('full', 'Full'),
        ('price', 'Pricelist'),
        ('stock', 'Vendor Stock'),
        ('price_stock', 'Both Pricelist & Stock'),
    ], string="Update Product", default='full', required=True)
    create_pricelist = fields.Selection([
        ('sales', 'Sales Pricelist'),
        ('vendor', 'Vendor Pricelist'),
        ('both', 'Both Pricelist'),
    ], string="Create Pricelist",default='both', required=True)
    partner_id = fields.Many2one('res.partner', string="Supplier")
    last_synced_date = fields.Datetime('Last synced date', readonly=True)
    central_system_date = fields.Datetime('Last central system date', readonly=True)
    # Margin
    pricelist_margin = fields.Float(
        string="Price-list Margin (%)",
        help="Raw material and finishing charges pricelist margin percentage",
        default=30.00
    )
    extra_margin = fields.Float(
        string="Extra Margin (%)",
        help="Setup, printing, and shipping charges additional margin percentage",
        default=30.00
    )
    attribute_mapping_ids = fields.One2many('attribute.mapping', 'supplier_id', string="Attribute Mapping")
    # Order Configration
    shpping_product_id = fields.Many2one('product.product', string="Shipping Product", required=True)
    printing_product_id = fields.Many2one('product.product', string="Print Product", required=True)
    setup_product_id = fields.Many2one('product.product', string="Setup Product", required=True)

    get_endpoint = fields.Char("Get End-Point")
    category_query_text = fields.Text()
    price_stock_query_text = fields.Text()
    product_query_text = fields.Text()
    page_size = fields.Integer("Page Size", default=100)
    page = fields.Integer("Page", default=1)
    language_id = fields.Many2one(
        'res.lang',
        string="Language",
        domain="[('active', 'in', [True, False])]",
        help="Select language for fetching data.",
        default=lambda self: self.env.ref('base.lang_en').id  # or use a search for user's language
    )
    category_relation_ids = fields.One2many(
        'product.category.relation',
        'supplier_id',
        string="Variant Field Values"
    )

    @api.onchange('attribute_query_text')
    def _onchange_product_query(self):
        if self.category_query_text:
            try:
                parse(self.category_query_text)
            except GraphQLError as e:
                UserError("Invalid GraphQL Query:", e)
        if self.price_stock_query_text:
            try:
                parse(self.price_stock_query_text)
            except GraphQLError as e:
                UserError("Invalid GraphQL Query:", e)
        if self.product_query_text:
            try:
                parse(self.product_query_text)
            except GraphQLError as e:
                UserError("Invalid GraphQL Query:", e)

    def get_suppiler_category(self):
        """
            This method use for getting token for px supplier.
        """
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": '*/*',
                "SupplierCode": supplier.vendor_short_code,
                "Authorization": supplier.authorization_id.token,
            }
            url = supplier.authorization_id.url + supplier.get_endpoint
            payload = {
                         "query": "query { categories(language: \"en\", page: 1, pageSize: 100) { categories { level name description image } totalCount } }"
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    auth_json = response.json()
                    model = self.env['ir.model'].search([('model', '=', 'product.category')], limit=1).id
                    for category_json in auth_json.get('data').get('data').get('categories').get('categories'):
                        self.insert_with_cr('Category', self.env.user.id, model, category_json)
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

    def insert_with_cr(self, name, user_id, models, result):
        cr = self._cr  # Get cursor
        priority = 0
        result_json = json.dumps(result)
        result_json_text = json.dumps(result, indent=3)
        # Example insert query
        reference, sub_reference = '' , ''

        if name == 'Category':
            reference = result.get('name') or result.get('name') or False
            sub_reference = result.get('name') or result.get('name') or False
        if name == 'Product':
            reference = result.get('templateCode') or result.get('templateCode') or False
            sub_reference = result.get('itemCode') or result.get('itemCode') or False
        name = self.name + ' - '+ name
        cr.execute("""
            INSERT INTO queue_job (name, user_id, supplier_id, company_id, model_id, state, result, reference, sub_reference, priority, result_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, user_id, self.id, self.env.company.id, models, 'draft', result_json, reference, sub_reference, priority, str(result_json_text)))
        # Commit if needed (use cautiously in Odoo)
        self.env.cr.commit()

    def fetch_suppiler_product(self):
        """
            This method use for getting token for px supplier.
        """
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": '*/*',
                "SupplierCode": supplier.vendor_short_code,
                "Authorization": supplier.authorization_id.token,
            }
            url = supplier.authorization_id.url + supplier.get_endpoint
            page = self.page
            payload = {
                          "query": "query { products(language: \"en\", page:"+ str(page) +", pageSize: 500) { products { sku templateCode itemCode supplier product { templateTitle variantName longDescription description brand material variationDependencies gender eanOrGtin isPrintable commentsNotes specificAttributes { name value } relatedItems moqPrint moqWithoutPrint currency } categories { level name description image } variantAttributes { color { name code pms hex group description pmsCode pmsColorReference } size sizeGrid } media { images { isPrimary url urlHigh type } digitalAssets { url type } } pricing { pricelist { min max gross net } additionalCharges { name chargePerOrder chargePerItem quantityFrom } modifiedDate expiresAt effectiveFrom } measurements { grossWeight { value unit } netWeight { value unit } width { value unit } height { value unit } length { value unit } volume { value unit } diameter { value unit } circumference { value unit } grammage { value unit } } complianceSustainability { isEco countryOfOrigin greenPoints greenPointsFile certifications { name url } co2Total co2EmissionBenchmark recycledContent } stockManagement { currentStock stockLocation location { name code qty } unit nextStockDate nextStockQuantity } packaging { innerCarton { qty dimensions { length width height unit } weight { net unit } volume { value unit } packagingType } outerCarton { qty dimensions { length width height unit } weight { gross unit } volume { value unit } packagingType } } shipping { carrier tierCharges { type qty price } } seo { metaKeywords } printing { printData { location locationCode locationMaxWidth locationMaxHeight locationDiameter locationUnit shape priceDependency maxColors method methodCode setupCharges { type value } pricing { colorPricing { numPosition numColours tiers { colorQuantityFrom colorQuantityTo grossPrice netPrice vdpNetPrice vdpGrossPrice } setupCharges { type value } } sizePricing { numPosition size { value unit } area { from to unit } tiers { sizeQuantityFrom sizeQuantityTo grossPrice netPrice vdpNetPrice vdpGrossPrice } setupCharges { type value } } } coordinates { topLeftX topLeftY topRightX topRightY bottomLeftX bottomLeftY bottomRightX bottomRightY width height unit diameter } leadTime { standard  maxQty } images { blankImage markedImage } printNotes } artworkTemplates { type url } } metadata { creationDateTime modifiedDate isDiscontinued } } totalCount } }"
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    product_json = response.json()
                    model = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1).id
                    for variant_json in product_json.get('data').get('data').get('products').get('products'):
                        self.insert_with_cr('Product', self.env.user.id, model, variant_json)
                page += 1
                self.page = page
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

