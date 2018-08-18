from scrapy import signals
import scrapy
import json
import re
import hashlib
import requests


class InfiniteScroller(scrapy.Spider):
    name = "infinite_scroller"
    
    def start_requests(self):
        tags = ["arte"]
        for tag in tags:
            url = 'https://www.instagram.com/explore/tags/{}/'.format(tag)
            request = scrapy.Request(url=url, callback=self.parse)
            request.meta["tag"] = tag
            yield request

    def parse(self, response):
        json_data = self.parse_to_json(response, True)
        # Need to find rhx_gis
        #rhx_gis = json_data["rhx_gis"]
        rhx_gis = "6941971af67abc688afa564b573977e9"
        # Need to find end cursor
        end_cursor = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]["edge_hashtag_to_media"]["page_info"]["end_cursor"]
        # Need to find query_hash
        query_hash_link = response.xpath("/html/body/script[8]/@src").extract_first()
        request =  scrapy.Request(url = "https://www.instagram.com" + query_hash_link, callback=self.scroll)
        request.meta["rhx_gis"] = rhx_gis
        request.meta["end_cursor"] = end_cursor
        request.meta["tag"] = response.meta["tag"]
        yield request

    def scroll(self, response):
        tag = response.meta["tag"]
        query_hash = re.search(r"d=\"([0-9a-z]+)\"},,,function", response.text).group(1)
        rhx_gis = response.meta["rhx_gis"]
        end_cursor = response.meta["end_cursor"]
        
        x_gis = hashlib.md5(
            str(rhx_gis + '{"tag_name":' +
                tag + ',"include_reel":false,"include_logged_out":true}').encode('utf-8')
            ).hexdigest()

        x_gis = hashlib.md5(
            str(rhx_gis + ':{"tag_name":"' + 
            tag + '","first":12,"after":"' + 
            end_cursor + '"}').encode('utf-8')
            ).hexdigest()

        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
            'x-instagram-gis': x_gis,
        }

        params = (
            ('query_hash', 'faa8d9917120f16cec7debbd3f16929d'),
            ('variables', '{"tag_name":"' + tag + '","first":7,"after":' + end_cursor),
        )

        response = requests.get('https://www.instagram.com/graphql/query/', headers=headers, params=params)
        print(response.text)
        '''
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
            'x-instagram-gis': '5f097a12049a192b347b2362e9cfe7c7',
        }

        params = (
            ('query_hash', str(query_hash)),
            ('variables', '{"tag_name":"love","include_reel":false,"include_logged_out":true}'),
        )
        response = requests.get('https://www.instagram.com/graphql/query/', headers=headers, params=params)
        print(response.text)
        '''

    def next_scroll(self, response):
        print(response.text)


    def parse_to_json(self, response, write_to_file=False):
        # First script object will always be the json datas
        json_data = response.xpath("/html/body/script[1]/text()").extract_first()
        # Cut off the emoji shit
        json_data = re.sub("\\\\u....", "", json_data)
        # Cut off the 'window._sharedData = '
        json_data = json_data[21:]
        # Cut off the ending semicolon
        json_data = json_data[:len(json_data) - 1]

        if write_to_file:
            with open("json_data.txt", "w") as f:
                f.write(json_data)
        json_data = json.loads(json_data)
        assert json_data is not None
        return json_data