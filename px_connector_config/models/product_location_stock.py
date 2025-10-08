from odoo import models, fields, api


class ProductLocationStock(models.Model):
    _name = 'product.location.stock'
    _description = 'Product Field Line'
    _rec_name = "location"

    product_id = fields.Many2one('product.product', string='Product Variant')
    location = fields.Char('Location', required=True)
    quantity = fields.Float(string="Stock Quantity")