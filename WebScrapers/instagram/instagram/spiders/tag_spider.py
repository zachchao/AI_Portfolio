import scrapy
import json


class TagSpider(scrapy.Spider):
    name = "instagram_hashtag"
    start_urls = [
        'https://www.instagram.com/explore/tags/whphidden/'
    ]

    def parse(self, response):
        json_data = self.parse_to_json(response)
        hashtag = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]
        end_cursor, media = self.unpack_hashtag(hashtag)
        captions = [self.unpack_post(post) for post in media]

    def parse_to_json(self, response):
        # First script object will always be the json datas
        json_data = response.xpath("/html/body/script[1]/text()").extract_first()
        # Cut off the emoji shit
        json_data = json_data.replace("\\u", "u")
        # Cut off the 'window._sharedData = '
        json_data = json_data[21:]
        # Cut off the ending semicolon
        json_data = json_data[:len(json_data) - 1]

        #with open("json_data.txt", "w") as f:
        #    f.write(json_data)
        json_data = json.loads(json_data)
        assert json_data is not None
        return json_data

    def unpack_hashtag(self, hashtag):
        tag = hashtag["name"]
        end_cursor = hashtag["edge_hashtag_to_media"]["page_info"]["end_cursor"]
        media = hashtag["edge_hashtag_to_media"]["edges"]
        return end_cursor, media
        
    def unpack_post(self, post):
        caption = post["node"]["edge_media_to_caption"]["edges"][0]["node"]["text"]
        return caption



