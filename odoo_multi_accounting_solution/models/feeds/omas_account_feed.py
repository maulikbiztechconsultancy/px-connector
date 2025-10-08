# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from logging import getLogger
_logger = getLogger(__name__)
from odoo import models, fields

class AccountFeed(models.Model):
    _name = 'omas.account.feed'
    _inherit = 'omas.feed'
    _description = 'OMAS Account Feeds'

    import_type = fields.Selection([('blank','Blank Mapping'),
                                     	('create','Create Record')], default = "blank")

    def create_entity(self):
        feed = self
        message = ''
        odoo_id = False
        instance_id = feed.instance_id
        data = eval(feed.data)
        remote_id = feed.remote_id
        account_type = data.get('account_type',False)
        name = feed.name
        code = data.get('code')
        import_type = feed.import_type
        state = 'done'
        mapped_id = self._context.get('account_mappings').get(
            instance_id.id, {}).get(remote_id)
        if not data.get('code') and import_type == 'create':
            if instance_id.set_account_sequence:
                data['code'] = instance_id.account_sequence_id.next_by_id()
            else:
                message += """Account Number is Mandatory. Please enable the
                    Set Account Sequence field in Odoo Multi-Accounting Configuration View.\n"""
                state='error'
        if account_type:
            if account_type in ('asset_receivable', 'liablity_payable'):
                data['reconcile'] = True
        try:
            if state == 'done':
                match = instance_id.with_context(active_test = False).match_odoo_accounts(code, instance_id.company_id)
                if mapped_id:
                    odoo_id = mapped_id
                    mapped_record = self.env['omas.account.mapping'].browse(mapped_id)
                    # if import_type == 'create':
                    #     mapped_record.name.write(data)
                else:
                    if import_type == 'create':
                        if match:
                            odoo_id = match
                            _logger.warning(f'Account code {code} is already exists in odoo')
                        else:
                            odoo_id = self.env['account.account'].create(data)
                    # When import_type is blank then the value of odoo_id is False
                    mapping_id = instance_id.create_account_mapping(remote_id, odoo_id, display_name=name, code=code)
                message += f'<br/> Account {name} Successfully Evaluated.'
        except Exception as e:
            state = 'error'
            message += f'Error in Evaluating Account Feed: {e}\n'
            if instance_id.debug:
                _logger.error(message, exc_info=True)
        return dict(
            state=state,
            odoo_id=odoo_id,
            message=message
        )
