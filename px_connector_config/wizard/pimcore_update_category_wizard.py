from odoo import models, fields, Command

class PimcoreUpdateCategoryWizard(models.TransientModel):
    _name = 'pimcore.update.category.wizard'
    _description = 'pimcore update category wizard'

    product_category=fields.Many2one('product.category')
    product_public_category=fields.Many2one('product.public.category')

    def action_update_category(self):
        self.ensure_one()
        if self.product_category and self.product_public_category:
            products = self.env['product.template'].search([('categ_id', '=', self.product_category.id)])
            products.write({'public_categ_ids': [Command.link(self.product_public_category.id)]})
