from odoo import models, fields, Command


class ProductPublicWizaed(models.TransientModel):
    _name = 'product.public.wizard'
    _description = 'Product Public Wizard'

    product_category_id = fields.Many2one('product.category', string="Category")
    public_category_id = fields.Many2one('product.public.category', string="eCommerce Category")

    def action_update_category(self):
        """
            This method using for the set eCommerce based on Product Category
        """
        self.ensure_one()
        if self.product_category_id and self.public_category_id:
            products = self.env['product.template'].search([('categ_id', '=', self.product_category_id.id)])
            products.write({'public_categ_ids': [Command.link(self.public_category_id.id)]})
