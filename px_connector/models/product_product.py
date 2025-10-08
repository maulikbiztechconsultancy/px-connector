from odoo import api, exceptions, fields, models, _
import logging
import json

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Based configration of Job Queue
    image_url = fields.Char(string="Image URL") # Add new featuer for live url on design
    item_code = fields.Char(string="Item Code") # Add new featuer for live url on design
    
    repeat_charge = fields.Float(string="Repeat Charge")
    setup_charge = fields.Float(string="Setup Charge")

    supplier_id = fields.Many2one('supplier.configuration', string="Supplier", readonly=True, related="product_tmpl_id.supplier_id")
    stock_location_ids = fields.One2many("product.location.stock", 'product_id', string="Stock Locations")
    # Json data
    raw_json = fields.Json("Raw Json", readonly=True, copy=False)
    printing_json = fields.Json(string="Printing Json", readonly=True, copy=False)
    shipping_json = fields.Json(string="Shipping Json", readonly=True, copy=False)

    def json_process(self, job, supplier_id):
        """
            Process import category based on queue.
        """
        method_name = "set_product_%s" % supplier_id.vendor_short_code.lower()
        method = getattr(self, method_name, None)
        if method:
            return method(job, supplier_id)

    def _get_currency_convert_amount(self, currency, amount, to_currency):
        """
            Process amount based on currency.
        """
        return currency._convert(
            amount,
            to_currency,
            self.env.company,
            fields.Date.context_today(self),
        )

    def update_sale_price_list(self, vals_list):
        for vals in vals_list:
            vals.update({'product_id': self.id})
        self.env['product.pricelist.item'].create(vals_list)

    def update_vendor_price_list(self, vals_list):
        for vals in vals_list:
            vals.update({'product_id': self.id})
        self.env['product.supplierinfo'].create(vals_list)