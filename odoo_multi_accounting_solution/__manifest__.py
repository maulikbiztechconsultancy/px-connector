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
  "name"                 :  "Odoo Multi-Accounting Solution",
  "summary"              :  """The module is Multiple Accounting platform connector with Odoo. You can connect and manage various Accounting platforms in odoo with the help of Odoo multi-Accounting Solution module. Odoo Accounting multiaccounting odoo multi accounting webkul multiaccounting solutions multi-accounting, It supports xero connectors zoho books connectors accounting""",
  "category"             :  "Website",
  "version"              :  "1.3.1",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "description"          :  """The module is Multiple Accounting platform connector with Odoo. You can connect and manage various Accounting platforms in odoo with the help of Odoo multi-Accounting Solution module.""",
  "live_test_url":"https://odoodemo.webkul.com/demo_feedback?module=odoo_multi_accounting_solution",
  "depends"              :  [
                             'stock_delivery', 'purchase',
                            ],
  "data"                 :  [
    'security/omas_security.xml',
    'security/ir.model.access.csv',
    'data/cron.xml',
    'data/server_actions.xml',
    'data/data.xml',
    'views/omas/omas_view.xml',
    'views/mappings/omas_account_mapping_view.xml',
    'views/mappings/omas_category_mapping_view.xml',
    'views/mappings/omas_customer_mapping_view.xml',
    'views/mappings/omas_template_mapping_view.xml',
    'views/mappings/omas_product_mapping_view.xml',
    'views/mappings/omas_order_mapping_view.xml',
    'views/mappings/omas_purchase_order_mapping_view.xml',
    'views/mappings/omas_invoice_mapping_view.xml',
    'views/mappings/omas_payment_mapping_view.xml',
    'views/mappings/omas_payment_method_mapping_view.xml',
    'views/mappings/omas_payment_term_mapping_view.xml',
    'views/mappings/omas_shipping_mapping_view.xml',
    'views/mappings/omas_tax_mapping_view.xml',
    'views/feeds/omas_account_feed_view.xml',
    'views/feeds/omas_customer_feed_view.xml',
    'views/feeds/omas_product_feed_view.xml',
    'views/feeds/omas_order_feed_view.xml',
    'views/feeds/omas_purchase_order_feed_view.xml',
    'views/feeds/omas_invoice_feed_view.xml',
    'views/feeds/omas_payment_feed_view.xml',
    # Update Tax
    'views/feeds/omas_tax_feed_view.xml',
    'views/omas/omas_dashboard.xml',
    'views/omas/omas_menus.xml',
    'wizards/omas_import_operation_view.xml',
    'wizards/omas_export_operation_view.xml',
    'wizards/omas_message_wizard_view.xml',
    # Added
    'wizards/manual_export/manual_export.xml',
    'data/export_actions.xml',
    
  ],
  'assets':{
    'web.assets_backend': [
      'web/static/lib/jquery/jquery.js',
      "odoo_multi_accounting_solution/static/src/js/omas_dashboard.js",
      "odoo_multi_accounting_solution/static/src/css/omas_dashboard.css",
      'odoo_multi_accounting_solution/static/src/xml/omas_dashboard.xml'
    ],
    'odoo_multi_accounting_solution.assetsLib':[
                                  '/web/static/lib/Chart/Chart.js',
                              ]
    # 'web.assets_qweb':[
    #   'odoo_multi_accounting_solution/static/src/xml/omas_dashboard.xml'
    # ],
  },
  'images':['static/description/banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  99,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
}
