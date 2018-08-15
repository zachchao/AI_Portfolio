import scrapy
from instagram.helpers import parse_to_json


'''
To scrape hashtag pages for captions
'''
class TagSpider(scrapy.Spider):
    name = "instagram_hashtag"
    start_urls = [
        'https://www.instagram.com/explore/tags/whphidden/'
    ]

    def parse(self, response):
        print(response.headers)
        json_data = parse_to_json(response)
        hashtag = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]
        end_cursor, media = self.unpack_hashtag(hashtag)
        captions = [self.unpack_post(post) for post in media]

    def unpack_hashtag(self, hashtag):
        tag = hashtag["name"]
        end_cursor = hashtag["edge_hashtag_to_media"]["page_info"]["end_cursor"]
        media = hashtag["edge_hashtag_to_media"]["edges"]
        return end_cursor, media
        
    def unpack_post(self, post):
        caption = post["node"]["edge_media_to_caption"]["edges"][0]["node"]["text"]
        return caption



