from scrapy import signals
import scrapy
import json
import re
import hashlib
import urllib


class UserSpider(scrapy.Spider):
    name = "instagram_users_and_tags"
    base_url = 'https://www.instagram.com'
    start_users = {"instagram", "beyonce", "nike"}
    start_tags = {"love"}
    already_seen_users = set()
    already_seen_tags = set()

    # So we don't get blocked by instagram
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN" : 1,
        "CONCURRENT_REQUESTS" : 1,
        "CLOSESPIDER_PAGECOUNT" : 10000,
    }

    # Hyper parameters
    # If it should grow beyond the initial users and tags
    should_propagate = True
    # How many posts to request each time we scroll down
    num_to_request = 21
    # How deep to go when scrolling
    max_depth = 3
    
    # These are always the same and getting them is a pain so... hardcoded
    user_query_hash = 'e7e2f4da4b02303f74f0841279e52d76'
    tag_query_hash = 'faa8d9917120f16cec7debbd3f16929d'
    rhx_gis = "6941971af67abc688afa564b573977e9"
    # These are the URL parameters that get sent
    create_user_variables = lambda self, user_id, end_cursor : '{"id":"' + str(user_id) + '","first":' + str(self.num_to_request) + ',"after":"' + end_cursor + '"}'
    create_tag_variables = lambda self, tag, end_cursor : '{"tag_name":"' + tag + '","first":' + str(self.num_to_request) + ',"after":"' + end_cursor + '"}'
    # This takes a query_hash and variables and encodes them into a url suffix
    create_scroll_url_suffix = lambda self, query_hash, variables : urllib.parse.urlencode({'query_hash' : query_hash, 'variables' : variables})
    # Creates an MD5 hash of rhx_gis and variables as its a required header for scrolling, ajax or js or something
    create_x_gis = lambda self, variables : hashlib.md5(str(self.rhx_gis + ":" + variables).encode('utf-8')).hexdigest()
    # User agent or instagram becomes madstagram
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'

    def start_requests(self):
        for user in self.start_users:
            url = '{}/{}/'.format(self.base_url, user)
            yield self.send_nice_request(url, "user")
        for tag in self.start_tags:
            url = '{}/explore/tags/{}/'.format(self.base_url, tag)
            yield self.send_nice_request(url, "tag")

    def parse(self, response):
        json_data = self.parse_to_json(response, response.meta["depth"], False)
        # Get all the relevant data out of the page
        if response.meta["type"] == "user":
            user_id, end_cursor, has_next_page, media = self.parse_user(json_data, response.url)
            # Will happen if they are private or 404 page, media will also be None
            if end_cursor:
                variables = self.create_user_variables(user_id, end_cursor)
                query_hash = self.user_query_hash
        else:
            tag, end_cursor, has_next_page, media = self.parse_hashtag(json_data, response.url)
            # Will happen if they are private or 404 page, media will also be None
            if end_cursor:
                variables = self.create_tag_variables(tag, end_cursor)
                query_hash = self.tag_query_hash

        # Some people post nothing or private or a 404 page
        if media:
            captions, hashtags, linked_users = self.extract_captions_tags_and_users(media)
            # TO DO :
            # Throw this to the pipeline as this is the vector to run word embeddings on
            self.write_to_file(captions)

            # Scroll down the page
            if has_next_page and response.meta["depth"] < self.max_depth:
                yield self.scroll(response, variables, query_hash)

            # Take all mentions of users or tags and follow them to scrape more
            if self.should_propagate:
                for sub_list in hashtags:
                    for tag in sub_list:
                        if tag not in self.already_seen_tags:
                            self.already_seen_tags.add(tag)
                            url = '{}/explore/tags/{}/'.format(self.base_url, tag)
                            yield self.send_nice_request(url, "tag")

                for user in linked_users:
                    if user not in self.already_seen_users:
                        self.already_seen_users.add(user)
                        url = '{}/{}/'.format(self.base_url, user) 
                        yield self.send_nice_request(url, "user")

    def send_nice_request(self, url, type_of_url):
        headers = {"user-agent" : self.user_agent}
        request = scrapy.Request(url=url, headers=headers, callback=self.parse)
        request.meta["type"] = type_of_url
        request.meta["depth"] = 0
        return request

    # Takes a response and scrolls down the page, assumes has_next_page == True
    def scroll(self, response, variables, query_hash):
        # Das all you need babee. Took me like 30 hours but its coo
        headers = {
            "user-agent" : self.user_agent,
            "x-instagram-gis" : self.create_x_gis(variables)
        }
        # Turn params into a url
        scroll_url_suffix = self.create_scroll_url_suffix(query_hash, variables)
        request = scrapy.Request(
            url="{}/graphql/query/?{}".format(self.base_url, scroll_url_suffix),
            headers=headers,
            callback=self.parse
        )
        request.meta["type"] = response.meta["type"]
        request.meta["depth"] = response.meta["depth"] + 1
        return request

    # Extracts the tag, end_cursor, has_next_page and media from the JSON of a user
    def parse_user(self, json_data, url):
        is_scrolled = re.search(r"graphql\/query\/\?", url)
        # JSON is formatted differently if we submit a query vs an initial call
        if is_scrolled:
            user = json_data["data"]["user"]
            user_id = user["edge_owner_to_timeline_media"]["edges"][0]["node"]["owner"]["id"]
        else:
            user = json_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]
            user_id = user["id"]
        # The rest is generic for scrolled requests or initial requests
        media = user["edge_owner_to_timeline_media"]["edges"]
        page_info = user["edge_owner_to_timeline_media"]["page_info"]
        has_next_page = page_info["has_next_page"]
        end_cursor = page_info["end_cursor"]
        return user_id, end_cursor, has_next_page, media
        
    # Extracts the tag, end_cursor, has_next_page and media from the JSON of a tag
    def parse_hashtag(self, json_data, url):
        is_scrolled = re.search(r"graphql\/query\/\?", url)
        # JSON is formatted differently if we submit a query vs an initial call
        if is_scrolled:
            hashtag = json_data["data"]["hashtag"]  
        else:
            hashtag = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]
        # The rest is generic for scrolled requests or initial requests
        tag = hashtag["name"]
        page_info = hashtag["edge_hashtag_to_media"]["page_info"]
        end_cursor = page_info["end_cursor"]
        has_next_page = page_info["has_next_page"]
        media = hashtag["edge_hashtag_to_media"]["edges"]
        return tag, end_cursor, has_next_page, media

    # Takes the 'media' section of JSON and returns the captions
    # as well as the tags and users mentioned within those captions
    def extract_captions_tags_and_users(self, media):
        # Unpacks each post the user has on the front page of their profile
        captions = list(map(self.unpack_post, media))
        # Extracts all the hashtags from a post, we only want ones with one more tags, because word embeddings
        hashtags = self.set_map(self.extract_tags, captions)
        linked_users = self.set_map(self.extract_users, captions)
        # Join linked_users into one because grouping doesn't matter for them
        linked_users = sum(linked_users, [])
        return captions, hashtags, linked_users

    # Applies a  map and returns all items from the list without repetitions
    def set_map(self, fn, iterable):
        nonzero_map = list(map(fn, iterable))
        # Remove repeats
        return list(map(lambda x : list(set(x)), nonzero_map))

    # Takes all mentions of users out of a caption and returns them in a list
    def extract_users(self, caption):
        return re.findall(r"(?:^|\s)@([a-z\d\-\.\_]+)", caption)

    # Takes all tags from a caption and returns them in a list
    def extract_tags(self, caption):
        return re.findall(r"(?:^|\s)#([a-z\d\-]+)", caption)

    # Takes a post and returns its caption
    def unpack_post(self, post):
        edges = post["node"]["edge_media_to_caption"]["edges"]
        if edges:
            caption = edges[0]["node"]["text"]
            return caption
        return ""

    # Takes a response and turns it into JSON
    def parse_to_json(self, response, depth, write_to_file=False):
        is_scrolled = re.search(r"graphql\/query\/\?", response.url)
        # Once we scroll we just get raw JSON
        if is_scrolled:
            json_data = response.text
        else:
            # First script object will always be the json data
            json_data = response.xpath("/html/body/script[1]/text()").extract_first()
            # Cut off the 'window._sharedData = '
            json_data = json_data[21:]
            # Cut off the ending semicolon
            json_data = json_data[:len(json_data) - 1]
        # Have trouble dealing with unicode so I take the escapes out and replace with a tilde
        # That way I can differentiate between words that start with u and are 5 letters and unicode
        json_data = json_data.replace("\\u", "/u")
        json_data = json_data.replace("\\U", "/U")
        # Writing to a file for debugging and finding paths
        if write_to_file:
            file_name = "json_data.txt"
            with open(file_name, "w") as f:
                print("Saved to {}".format(file_name))
                f.write(json_data)
        assert json_data is not None
        try:
            json_data = json.loads(json_data)
        except json.decoder.JSONDecodeError as e:
            print("Caught Error.")
            with open("error.txt", "w") as f:
                f.write(str(depth) + json_data)
            exit()
        return json_data

    # Save our captions to use on word embeddings
    def write_to_file(self, captions):
        #string_to_write = ""
        #for i in range(len(captions)):
            #if hashtags[i]:
            #    string_to_write += captions[i] + "\t" + ",".join(hashtags[i]) + "\n"
        #    string_to_write += captions[i] + "\n"
        #self.file.write(string_to_write)
        captions = list(map(lambda x : x.replace("\n", " "), captions))
        self.file.write("\n".join(captions))

    # Enables spider_opened and spider_closed methods
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(UserSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        return spider

    # Open our file to save captions to
    def spider_opened(self, spider):
        self.file = open("tags_for_embedding.txt", "a")

    # Close our file
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
            