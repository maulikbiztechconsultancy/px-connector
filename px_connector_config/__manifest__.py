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
    'depends': ['website_sale', 'pimcore_customization'],
    'external_dependencies': { 'python': ['graphql-core']
},
    'data': [
        "security/security.xml",
        'security/ir.model.access.csv',
        'wizard/pimcore_update_category_wizard_views.xml',
        'views/px_venderconfig_views.xml',
        'views/product_template_view.xml',
        'views/vendor_queue_job_views.xml',
        # 'views/product_public_category_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}