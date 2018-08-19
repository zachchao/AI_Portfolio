from scrapy import signals
import scrapy
import json
import re
import hashlib
import urllib


class UserSpider(scrapy.Spider):
    name = "instagram_users_and_tags"
    base_url = 'https://www.instagram.com'
    #already_seen_users = {"instagram", "beyonce", "nike"}
    already_seen_users = {"instagram"}
    already_seen_tags = set()

    # So we dont get blocked by instagram
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN" : 1,
        "CONCURRENT_REQUESTS" : 1,
        "CLOSESPIDER_PAGECOUNT" : 25000,
    }

    # How many posts to request each time we scroll down
    num_to_request = 21
    # How deep to go when scrolling
    max_depth = 3
    # If it should grow beyond the initial users and tags
    should_propagate = False
    # These are always the same and getting them is a pain so... hardcoded
    user_query_hash = 'e7e2f4da4b02303f74f0841279e52d76'
    tag_query_hash = 'faa8d9917120f16cec7debbd3f16929d'
    rhx_gis = "6941971af67abc688afa564b573977e9"
    # For some reason I cant use string formatting on this.
    create_user_variables = lambda self, user_id, end_cursor : '{"id":"' + str(user_id) + '","first":' + str(self.num_to_request) + ',"after":"' + end_cursor + '"}'
    create_tag_variables = lambda self, tag, end_cursor : '{"tag_name":"' + tag + '","first":' + str(self.num_to_request) + ',"after":"' + end_cursor + '"}'
    create_scroll_url_suffix = lambda self, query_hash, variables : urllib.parse.urlencode({'query_hash' : query_hash, 'variables' : variables})
    create_x_gis = lambda self, variables : hashlib.md5(str(self.rhx_gis + ":" + variables).encode('utf-8')).hexdigest()
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'

    def start_requests(self):
        for user in self.already_seen_users:
            url = '{}/{}/'.format(self.base_url, user)
            headers = {"user-agent" : self.user_agent}
            request = scrapy.Request(url=url, headers=headers, callback=self.parse)
            request.meta["type"] = "user"
            request.meta["depth"] = 0
            yield request

    def parse(self, response):
        json_data = self.parse_to_json(response, response.meta["depth"], False)
        # Get all the relevant data out of the page
        if response.meta["type"] == "user":
            user_id, end_cursor, has_next_page, media = self.parse_user(json_data, response.meta["depth"])
            variables = self.create_user_variables(user_id, end_cursor)
            query_hash = self.user_query_hash
        else:
            tag, end_cursor, has_next_page, media = self.parse_hashtag(json_data, response.meta["depth"])
            variables = self.create_tag_variables(tag, end_cursor)
            query_hash = self.tag_query_hash

        if media:
            captions, hashtags, linked_users = self.extract_captions_tags_and_users(media)
            # TO DO :
            # Throw this to the pipeline as this is the vector to run word embeddings on
            self.write_to_file(captions)

            # Scroll down the page
            if has_next_page and response.meta["depth"] < self.max_depth:
                yield self.scroll(response, variables, query_hash)

            if self.should_propagate:
                for sub_list in hashtags:
                    for tag in sub_list:
                        if tag not in self.already_seen_tags:
                            self.already_seen_tags.add(tag)
                            url = '{}/explore/tags/{}/'.format(self.base_url, tag)
                            yield scrapy.Request(url=url, callback=self.parse)

                for user in linked_users:
                    if user not in self.already_seen_users:
                        self.already_seen_users.add(user)
                        url = '{}/{}/'.format(self.base_url, user) 
                        yield scrapy.Request(url=url, callback=self.parse)

    def scroll(self, response, variables, query_hash):
        headers = {
            "user-agent" : self.user_agent,
            "x-instagram-gis" : self.create_x_gis(variables)
        }
        scroll_url_suffix = self.create_scroll_url_suffix(query_hash, variables)
        request = scrapy.Request(
            url="{}/graphql/query/?{}".format(self.base_url, scroll_url_suffix),
            headers=headers,
            callback=self.parse
        )
        request.meta["type"] = response.meta["type"]
        request.meta["depth"] = response.meta["depth"] + 1
        return request

    def parse_user(self, json_data, depth):
        # When we scroll down the JSON is less nested.
        if depth > 0:
            user = json_data["data"]["user"]
            user_id = user["edge_owner_to_timeline_media"]["edges"][0]["node"]["owner"]["id"]
        # Otherwise we have to unpack everything   
        else:
            user = json_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]
            user_id = user["id"]
        # The rest is generic for scrolled requests or initial requests
        media = user["edge_owner_to_timeline_media"]["edges"]
        page_info = user["edge_owner_to_timeline_media"]["page_info"]
        has_next_page = page_info["has_next_page"]
        end_cursor = page_info["end_cursor"]
        return user_id, end_cursor, has_next_page, media
        

    def parse_hashtag(self, json_data, depth):
        hashtag = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]
        tag = hashtag["name"]
        page_info = hashtag["edge_hashtag_to_media"]["page_info"]
        end_cursor = page_info["end_cursor"]
        has_next_page = page_info["has_next_page"]
        media = hashtag["edge_hashtag_to_media"]["edges"]
        return tag, end_cursor, has_next_page, media

    def extract_captions_tags_and_users(self, media):
        # Unpacks each post the user has on the front page of their profile
        captions = list(map(self.unpack_post, media))
        # Extracts all the hashtags from a post, we only want ones with one more tags, because word embeddings
        hashtags = self.nonzero_set_map(self.extract_tags, captions)
        linked_users = self.nonzero_set_map(self.extract_users, captions)
        # Join linked_users into one because grouping doesnt matter for them
        linked_users = sum(linked_users, [])
        return captions, hashtags, linked_users

    # Applies a filter and map and returns all nonezero items from the list without repetitions
    def nonzero_set_map(self, fn, iterable):
        #nonzero_map = list(filter(lambda x : len(x) > 1, map(fn, iterable)))
        nonzero_map = list(map(fn, iterable))
        # Remove repeats
        return list(map(lambda x : list(set(x)), nonzero_map))

    def extract_users(self, caption):
        return re.findall(r"(?:^|\s)@([a-z\d\-\.\_]+)", caption)

    def unpack_post(self, post):
        edges = post["node"]["edge_media_to_caption"]["edges"]
        if edges:
            caption = edges[0]["node"]["text"]
            return caption
        return ""

    def extract_tags(self, caption):
        return re.findall(r"(?:^|\s)#([a-z\d\-]+)", caption)

    def parse_to_json(self, response, depth, write_to_file=False):
        # Once we scroll we just get raw JSON
        if depth > 0:
            json_data = response.text
        else:
            # First script object will always be the json data
            json_data = response.xpath("/html/body/script[1]/text()").extract_first()
            # Cut off the 'window._sharedData = '
            json_data = json_data[21:]
            # Cut off the ending semicolon
            json_data = json_data[:len(json_data) - 1]
        # Cut off the emoji shit
        json_data = json_data.replace("\\u", "u")
        json_data = json_data.replace("\\U", "U")
        # Writing to a file for debugging and finding paths
        if write_to_file:
            file_name = "json_data.txt"
            with open(file_name, "w") as f:
                print("Saved to {}".format(file_name))
                f.write(json_data)
        json_data = json.loads(json_data)
        assert json_data is not None
        return json_data

    def write_to_file(self, captions):
        #string_to_write = ""
        #for i in range(len(captions)):
            #if hashtags[i]:
            #    string_to_write += captions[i] + "\t" + ",".join(hashtags[i]) + "\n"
        #    string_to_write += captions[i] + "\n"
        #self.file.write(string_to_write)
        captions = list(map(lambda x : x.replace("\n", " "), captions))
        self.file.write("\n".join(captions))


    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(UserSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        return spider

    def spider_opened(self, spider):
        self.file = open("tags_for_embedding.txt", "a")

    def spider_closed(self, spider):        
        self.file.close()









    # Useless for word embeddings but I was bored.
    '''
    def unpack_user(self, user):
        is_private = user["is_private"]
        if not is_private:
            followed_by = user["edge_followed_by"]["count"]
            biography = user["biography"]
            follows = user["edge_follow"]["count"]
            full_name = user["full_name"]
            has_channel = user["has_channel"]
            highlight_real_count = user["highlight_real_count"]
            user_id = user["id"]
            is_verified = user["is_verified"]
            username = user["username"]
            connected_fb_page = user["connected_fb_page"]
            num_posts = user["edge_owner_to_timeline_media"]["count"]
    '''
            