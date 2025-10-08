{
    'name': 'PF-Concept Connector',
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
    'depends': ['website_sale', 'px_connector'],
    'external_dependencies': { 'python': ['graphql-core']
},
    'data': [
        'datas/product_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}