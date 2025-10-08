{
    'name': 'XD Vendor',
    'version': '18.0',
    'summary': 'Integration with Pimcore for product/vendor synchronization',
    'description': """""",
    'category': 'Tools',
    'version': '18.0',
    'author': 'Biztech',
    'website': 'https://www.biztechcs.com/',
    'depends': ['website_sale', 'px_connector_config'],
    'external_dependencies': { 'python': ['graphql-core']},
    'data': [
        'data/data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}