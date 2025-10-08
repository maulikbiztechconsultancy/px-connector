{
    'name': 'PX Customized JSON',
    'summary': 'Customization layer for Pimcore JSON product/vendor integration',
    'description': """ Pimcore JSON Customization """,
    'version': '18.0',
    'category': 'Product',
    'author': 'Biztech',
    'website': 'https://www.biztechcs.com/',
    'depends': ['pimcore_customization', 'px_connector'],
    'data': [
        "security/ir.model.access.csv",
        "views/product_product_views.xml",
        "wizard/sale_order_line_wizard_views.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
