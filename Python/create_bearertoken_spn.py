import requests
import json
import requests
#
tenant ='<<your tenant_id>>'
client_id = '<<your client_id>>'
client_secret = '<<your client_secret>>'

url = 'https://login.microsoftonline.com/%s/oauth2/token' % tenant
data = {
  'grant_type': 'client_credentials',
  'client_id': client_id,
  'client_secret': client_secret
}

headers = {'Content-Type': 'application/x-www-form-urlencoded'}
resp = requests.post(url, data=data, headers=headers)

token = resp.json()['access_token']
print(str(token))
