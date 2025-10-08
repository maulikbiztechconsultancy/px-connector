# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models, fields

from logging import getLogger
_logger = getLogger(__name__)

class TaxFeed(models.Model):
    _name = 'omas.tax.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Tax Feeds'

    import_type = fields.Selection([('blank','Blank Mapping'),
                                     	('create','Create Record')], default = "blank")
    def create_entity(self):
        feed = self
        message = ''
        odoo_id = False
        instance_id = feed.instance_id
        data = eval(feed.data)
        remote_id = feed.remote_id
        rate = data.get('amount')
        name = feed.name
        state = 'done'
        import_type = feed.import_type
        mapped_id = self._context.get('tax_mappings').get(
            instance_id.id, {}).get(remote_id)
        amount = data.get('amount', 0)
        try:# Update Tax:
            if state == 'done':
                if mapped_id: #mapping exists
                    mapped_record = self.env['omas.tax.mapping'].browse(mapped_id)
                    odoo_id = mapped_id
                    if import_type == 'create':
                        mapped_record.name.write(data)
                else:
                    if import_type == "create":
                        odoo_id = self.env['account.tax'].create(data)
                    # When import_type is blank then the value of odoo_id = False
                    mapping_id = instance_id.create_tax_mapping(odoo_id, remote_id, amount=amount, display_name=name)
                message += f'<br/> Tax {name} Successfully Evaluated.'
        except Exception as e:
            state = 'error'
            message += f'Error in Evaluating Tax Feed: {e}\n'
            if instance_id.debug:
                _logger.info(message)
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )
