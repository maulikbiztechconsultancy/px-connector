# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

{
    "name": "Job Queue",
    "version": "18.0.1.3.0",
    "author": "Camptocamp,ACSONE SA/NV,Odoo Community Association (OCA)",
    "license": "LGPL-3",
    "category": "Generic Modules",
    "depends": ["mail", "base_sparse_field", "web"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/queue_job_views.xml",
        "views/queue_job_menus.xml",
    ],

    "installable": True,
}
