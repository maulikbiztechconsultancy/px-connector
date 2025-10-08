# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
    "name":  "Odoo Xero Connector",
    "summary":  """
                    Odoo Xero Connector is the best solution for your accounting and 
                    business management needs. The module allows you to efficiently 
                    import and export all the necessary data to manage the account
                    odoo connector xero accounting webkul xero multi accounting 
                    odoo accounting solutions odoo webkul apps multiaccounting
                """,
    "description": "Odoo Xero Connector for Multi Accounting Solution",
    "category":  "Website",
    "version":  "1.3.0",
    'depends': [
        'odoo_multi_accounting_solution'
    ],
    "sequence":  1,
    "author":  "Webkul Software Pvt. Ltd.",
    "license":  "Other proprietary",
    "data":  [
        "views/core/xoc_account_move_view.xml",
        "views/core/xoc_sale_order_view.xml",
        "views/core/xoc_purchase_order_view.xml",
        "data/data.xml",
        "wizard/import_operation.xml",
    ],
    "live_test_url":  "http://odoodemo.webkul.com/?module=odoo_xero_connector",
    'images': ['static/description/banner.png'],
    "application":  True,
    "installable":  True,
    "auto_install":  False,
    "price":  150,
    "currency":  "USD",
    "pre_init_hook":  "pre_init_check",
}
