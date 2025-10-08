from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class ProductSupplierStock(models.Model):
    _name = "product.supplier.stock"
    _description = "Product Supplier Stock"

    # Based configration vendor stock
    name = fields.Char(string="Location", required=True)
    product_id = fields.Many2one(comodel_name="product.product", string="Variant", index=True, required=True)
    qty = fields.Float('QTY', readonly=True)