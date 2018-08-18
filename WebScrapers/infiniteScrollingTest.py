import requests
import re
import hashlib
import urllib


'''
Tested in requests first to get everything right, then moved to scrapy
'''

username = "instagram"
user_id = "25025320"
r = requests.get("https://www.instagram.com/{}/".format(username))
end_cursor = re.search(r",\"end_cursor\":\"([A-Za-z0-9_-]+)\"", r.text).group(1)
rhx_gis = "6941971af67abc688afa564b573977e9"
variables = '{"id":"' + user_id + '","first":25,"after":"' + end_cursor + '"}'

x_gis = hashlib.md5(str(rhx_gis + ":" + variables).encode('utf-8')).hexdigest()

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
    'x-instagram-gis': x_gis,
}

suffix = urllib.parse.urlencode({
    'query_hash' : 'e7e2f4da4b02303f74f0841279e52d76',
    'variables' : variables
    })

response = requests.get('https://www.instagram.com/graphql/query/?' + suffix, headers=headers)
print(response)






tag = "poetry"
r = requests.get("https://www.instagram.com/explore/tags/{}".format(tag))
end_cursor = re.search(r",\"end_cursor\":\"([A-Za-z0-9_-]+)\"", r.text).group(1)
rhx_gis = "6941971af67abc688afa564b573977e9"

variables = '{"tag_name":"' + tag + '","first":25,"after":"' + end_cursor + '"}'

x_gis = hashlib.md5(str(rhx_gis + ":" + variables).encode('utf-8')).hexdigest()

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
    'x-instagram-gis': x_gis,
}

suffix = urllib.parse.urlencode({
    'query_hash' : 'faa8d9917120f16cec7debbd3f16929d',
    'variables' : variables
    })

response = requests.get('https://www.instagram.com/graphql/query/?' + suffix, headers=headers)
print(response)
print(response.text)
