from odoo import api, exceptions, fields, models, _
from datetime import datetime, timedelta
import requests
import json
from datetime import datetime



class PxSupplierAuthorization(models.Model):
    _name = "px.supplier.authorization"
    _description = "PX Supplier Authorization"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Main Configration
    name = fields.Char(string="PX Authorization", required=True, tracking=True)
    user_id = fields.Many2one(comodel_name="res.users", string="User")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", index=True)
    currency_id = fields.Many2one(comodel_name="res.currency", string="Currency", index=True)

    # Authorization
    url = fields.Char("URL", required=True)
    login = fields.Char("Login", required=True)
    password = fields.Char("Password", required=True)
    token_endpoint = fields.Char("Token EndPoint", required=True)
    refresh_endpoint = fields.Char("Refresh Token EndPoint", required=True)
    token = fields.Char("Token")
    refresh_token = fields.Char("Refresh Token")
    expires_at = fields.Datetime("EXpires At", readonly=True, copy=False)
    odoo_login = fields.Char("Odoo Login")
    odoo_password = fields.Char("Odoo Password")

    # Vendor Configration
    supplier_provide_ids = fields.One2many('supplier.provided', 'authorization_id', string="Supplier Configurations")


    def get_px_supplier_token(self):
        """
            This method use for getting token for px supplier.
        """
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": 'text/plain',
            }
            url = supplier.url + supplier.token_endpoint
            payload = {
                          "email": supplier.login,
                          "password": supplier.password
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    auth_json = response.json()
                    timestamp_str = auth_json.get('expiresAt')
                    if "." in timestamp_str:
                        date_part, frac = timestamp_str.split(".")
                        frac = frac.rstrip("Z")[:6]  # keep only first 6 digits
                        timestamp_str = f"{date_part}.{frac}Z"

                    dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")

                    # Ensure naive datetime (remove timezone if any)
                    dt = dt.replace(tzinfo=None)
                    supplier.write({
                        'token': auth_json.get('token'),
                        'refresh_token': auth_json.get('refreshToken'),
                        'expires_at': dt,   # Odoo Datetime field
                    })
                    return {
                        "effect": {
                            "fadeout": "slow",
                            "message": _("Successfully Generate Token! 🎉"),
                            "type": "rainbow_man",
                        }
                    }
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

    def get_px_refresh_token(self):
        """
            This method using for the generate refresh token.
        """
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": 'text/plain',
            }
            url = supplier.url + supplier.refresh_endpoint
            payload = {
                          "refreshToken": supplier.refresh_token,
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    auth_json = response.json()
                    timestamp_str = auth_json.get('expiresAt')
                    if "." in timestamp_str:
                        date_part, frac = timestamp_str.split(".")
                        frac = frac.rstrip("Z")[:6]  # keep only first 6 digits
                        timestamp_str = f"{date_part}.{frac}Z"

                    dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")

                    # Ensure naive datetime (remove timezone if any)
                    dt = dt.replace(tzinfo=None)
                    supplier.write({
                        'token': auth_json.get('token'),
                        'refresh_token': auth_json.get('refreshToken'),
                        'expires_at': dt,   # Odoo Datetime field
                    })
                    return {
                        "effect": {
                            "fadeout": "slow",
                            "message": _("Successfully Generate Refresh Token! 🎉"),
                            "type": "rainbow_man",
                        }
                    }
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")

    def get_suppiler_list(self):
        """
            This method using for the get suppiler list providing details.
        """
        for supplier in self:
            headers = {
                "Content-Type": "application/json",
                "accept": '*/*',
                "Authorization": supplier.token,
            }
            url = supplier.url + '/api/suppliersdata/configuration'
            payload = {
                          "userEmail": supplier.login,
                        }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                if response.status_code == 200:
                    supplier_data = response.json()
                    supplier_list = []
                    for supplier_lst in supplier_data.get('assignedSuppliers'):
                        supplier_list.append({
                            'name': supplier_lst.get('supplierName'),
                            'supplier_code': supplier_lst.get('supplierCode'),
                            'authorization_id': supplier.id
                            })
                    if supplier_list:
                        supplier.supplier_provide_ids.unlink()
                        supplier.supplier_provide_ids.create(supplier_list)
                else:
                    raise UserError(response.json())
            except Exception as e:
                raise Exception(f"An error occurred: {str(e)}")



class SupplierProvided(models.Model):
    _name = "supplier.provided"
    _description = "supplier.provided"


    name = fields.Char(string="Supplier Name", required=True)
    supplier_code = fields.Char(string="Supplier Code")
    authorization_id = fields.Many2one("px.supplier.authorization", string="Authorization")