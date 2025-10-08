from odoo import models, fields, api


class ProductTemplate(models.Model):
	_inherit = "product.attribute.value"

	code_refrence = fields.Char(string="Model Code")




class QueueJob(models.Model):
	_inherit = "queue.job"

	pim_config_id = fields.Many2one("pimore.vender.config", string="PIM ID")
