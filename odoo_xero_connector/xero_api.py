# -*- coding: utf-8 -*-
#################################################################################
#    Copyright (c) 2018-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    You should have received a copy of the License along with this program.
#    If not, see <https://store.webkul.com/license.html/>
#################################################################################
import logging
import requests
import json
import base64
import time

_logger = logging.getLogger(__name__)

__version__ = '1.0.0'

class XeroApi:
    def __init__(self, access_token, xero_tenant_id, debug=False, **extra
        ):
        self.debug=debug
        self.header = {
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
            "Xero-tenant-id": xero_tenant_id
        }
        self.api_url = "https://api.xero.com/api.xro/2.0"

    def format_get_error(self, error:str)->str:
        return f"{error.get('Detail', '')}"
    
    def format_put_error(self, error:str)->str:
        if error.get('Elements'):
            return f"({error.get('Type')}) {error.get('Elements')[0].get('ValidationErrors')[0].get('Message')}"
        elif error.get('Message'):
            return f"({error.get('Type')}) {error.get('Message')}"
        return error

    def get(self, resource:str, params={}, resource_id="", headers={})->dict:
        result = {'json':None, "f_error" :"something went wrong ..."}
        try:
            with requests.Session() as s:
                url = self.api_url + f'/{resource}'
                if resource_id:
                    url+=f'/{resource_id}'
                result['url'] = url
                if headers:
                    self.header.update(headers)
                _logger.info(self.header)
                response = s.get(url, headers=self.header, params=params)
                result['status_code'] = response.status_code or ''
                if response.ok :
                    response = response.json()
                    if result["status_code"] in  [200, 201]:
                        result['json'] = response
                    else:
                        result["f_error"] = self.format_get_error(response)
                        result["error"] = response
                elif response.status_code == 429:
                    result['error'] = result["f_error"] = "Error: Api record limit Exceeded."
                    if int(response.headers.get('X-DayLimit-Remaining')) == 0:
                        result['error'] = result["f_error"] = "Error: Api record limit Exceeded for day."
                        _logger.error(f"Xero Connector: Api record limit Exceeded for day")
                    elif response.headers.get('Retry-After'):
                        retry_after = int(response.headers.get('Retry-After'))
                        _logger.info(f"Warning: Wait for {retry_after} as per api limit")
                        if retry_after < 300:
                            time.sleep(retry_after+5)
                            response = s.get(url, headers=self.header, params=params)
                            result['status_code'] = response.status_code or ''
                            if response.ok :
                                response = response.json()
                                if result["status_code"] in  [200, 201]:
                                    result['json'] = response
                                else:
                                    result["f_error"] = self.format_get_error(response)
                                    result["error"] = response
                            else:
                                result['error'] = result["f_error"] = "Error: Response is not successfull."
                                _logger.info("Xero Connector API Response: %r", response.text)
                        else: 
                            result['error'] = result["f_error"] = f"Error: Api record limit Exceeded. Try after {retry_after} seconds."
                else:
                    result['error'] = result["f_error"] = "Error: Response is not successfull."
                    _logger.info("Xero Connector API Response: %r", response.text)
        except Exception as e:
            _logger.info("Xero Connector API Error: %r",e, exc_info=True)
            result['error'] = result["f_error"] = e.args[0]
        return result

    def post(self, resource:str, json={}, fetch_token=False, data='', headers = {})->dict:
        result = {'json':None}
        try:
            with requests.Session() as s:
                if fetch_token:
                    url = self.api_url
                else:
                    url = self.api_url
                url += f'/{resource}'
                result['url'] = url
                if headers:
                    self.header.update(headers)
                response = s.post(url, headers=self.header, json=json, data=data)
                result['status_code'] = response.status_code
                response = response.json()
                if result["status_code"] in [200, 201]:
                    if self.debug:
                        _logger.info("Response => %r", response)
                    result['json'] = response
                else:
                    if self.debug:
                        _logger.error("Error response => %r", response)
                    result['f_error'] = self.format_put_error(response)
                    result["error"] = response
        except Exception as e:
            result['error'] = result['f_error'] = e.args[0]
        return result

    def put(self, resource:str, resource_id="", json={}, data='')->dict:
        result = {'json':None}
        method = 'put'
        try:
            with requests.Session() as s:
                url = self.api_url + f'/{resource}'
                result['url'] = url
                if resource_id:
                    url+=f'/{resource_id}'
                response = getattr(s, method)(url, headers=self.header, json=json, data=data)
                result['status_code'] = response.status_code
                response = response.json()
                if result['status_code'] in [200, 201]:
                    if self.debug:
                        _logger.info("Response => %r", response)
                    result['json'] = response
                else:
                    if self.debug:
                        _logger.error("Error response => %r", response)
                    result["f_error"] = self.format_put_error(response)
                    result["error"] = response
        except Exception as e:
            result['error'] = result['f_error'] = e.args[0]
        return result

    def delete(self, resource:str, resource_id:str)->dict:
        result = {'json':None}
        try:
            with requests.Session() as s:
                url = self.api_url + f'/{resource}'
                result['url'] = url
                if resource_id:
                    url+=f'/{resource_id}'
                response = s.delete(url, headers=self.header)
                # result['text'] = response.text
                result['status_code'] = response.status_code

                if response.status_code in [200, 201]:
                    result['json'] = response.json().get('data')
                else:
                    err_msg = response.json().get('message', '')
        except:
            pass
        return result
