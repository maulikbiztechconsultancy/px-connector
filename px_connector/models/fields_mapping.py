from odoo import api, exceptions, fields, models, _
import requests
import json


PRODUCT_BUSINESS_MODELS = [
    'product.product',
    'product.template',
]

class FieldsMapping(models.Model):
    _name = "fields.mapping"
    _description = "Fields Mapping"

    name = fields.Char("Name")
    model_id = fields.Many2one('ir.model', string="Model")
    odoo_field_id = fields.Many2one('ir.model.fields', string="Field", domain=[('model', 'in', PRODUCT_BUSINESS_MODELS)])
    technical_name = fields.Char(string="Field")
    active = fields.Boolean('Active', default=True)
    
    # Install unique constraint to avoid duplicate mappings
    _sql_constraints = [
        ('uniq_model_field', 'unique(model_id, odoo_field_id)', 'Each Odoo field can only be mapped once per model!'),
    ]

    # install unique constraint to avoid duplicate technical names
    _sql_constraints += [
        ('uniq_model_technical_name', 'unique(model_id, technical_name)', 'Each technical name can only be mapped once per model!'),
    ]


class ProductLocationStock(models.Model):
    _name = "product.location.stock"
    _description = "Product Location Stock"

    name = fields.Char("Location")
    product_id = fields.Many2one("product.product", string="Product")
    qty = fields.Float("Quantity")


class ProductCategoryRelation(models.Model):
    _name = 'product.category.relation'
    _description = 'Product Category Relation'

    supplier_id = fields.Many2one('supplier.configuration', string='Supplier', ondelete='cascade')
    odoo_caegory_id = fields.Many2one(
        'product.category', string="Current Category",
    )
    supplier_category_id = fields.Many2one('queue.job', string="Supplier Value", domain="[('model_id', '=', 'product.category'), ('state', '!=', 'done'), ('supplier_id', '=', supplier_id)]")