{
    'name': 'PX Connector',
    'version': '18.0',
    'summary': 'Integration with Pimcore for product/vendor synchronization',
    'description': """
        This module allows configuration of Pimcore vendor API access
        and provides connectivity tools for data exchange.
    """,
    'category': 'Tools',
    'version': '18.0',
    'author': 'Biztech',
    'website': 'https://www.biztechcs.com/',
    'depends': ['website_sale', 'sale_management'],
    'external_dependencies': { 'python': ['graphql-core']
},
    'data': [
        # "security/security.xml",
        'security/ir.model.access.csv',
        'views/px_supplier_authorization_views.xml',
        'views/px_queue_job.xml',
        'views/supplier_configuration_view.xml',
        'views/product_template_view.xml',
        'views/product_product_view.xml',
        'views/fields_mapping_views.xml',
        'wizard/product_public_wizard_views.xml',
        'views/menu_item_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}