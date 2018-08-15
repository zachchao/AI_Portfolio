from scrapy import signals
import scrapy
import json
import re


class UserSpider(scrapy.Spider):
    name = "instagram_users_and_tags"
    already_seen_users = {"instagram", "beyonce", "nike"}
    already_seen_tags = set()
    start_urls = ['https://www.instagram.com/{}/'.format(user) 
        for user in already_seen_users]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN" : 1,
        "CONCURRENT_REQUESTS" : 1,
        "CLOSESPIDER_PAGECOUNT" : 10000,
    }

    def parse(self, response):
        json_data = self.parse_to_json(response)
        # Will be false if it is not a tag page
        is_tag = re.search(r"com\/explore\/tags\/", response.url)
        if is_tag:
            media = self.parse_hashtag(json_data)
        else:
            media = self.parse_user(json_data)
        if media:
            captions, hashtags, linked_users = self.extract_captions_tags_and_users(media)
            self.write_to_file(captions, hashtags)

            # Propogate
            for sub_list in hashtags:
                # TO DO :
                # Throw this to the pipeline as this is the vector to run word embeddings on
                for tag in sub_list:
                    if tag not in self.already_seen_tags:
                        self.already_seen_tags.add(tag)
                        url = 'https://www.instagram.com/explore/tags/{}/'.format(tag)
                        yield scrapy.Request(url=url, callback=self.parse)

            for user in linked_users:
                if user not in self.already_seen_users:
                    self.already_seen_users.add(user)
                    url = 'https://www.instagram.com/{}/'.format(user) 
                    yield scrapy.Request(url=url, callback=self.parse)

    def parse_user(self, json_data):
        user = json_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]
        media = user["edge_owner_to_timeline_media"]["edges"]
        return media

    def parse_hashtag(self, json_data):
        hashtag = json_data["entry_data"]["TagPage"][0]["graphql"]["hashtag"]
        end_cursor, media = self.unpack_hashtag(hashtag)
        return media

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
        return re.findall(r"@(.+?)(?:$| |\n|[@,\/#!$%\^&\*;:{}=\`~()])", caption)

    def unpack_post(self, post):
        edges = post["node"]["edge_media_to_caption"]["edges"]
        if edges:
            caption = edges[0]["node"]["text"]
            return caption
        return ""

    def extract_tags(self, caption):
        return re.findall(r"#(.+?)(?:$| |\n|[@.,\/#!$%\^&\*;:{}=\`~()])", caption)

    def unpack_hashtag(self, hashtag):
        tag = hashtag["name"]
        end_cursor = hashtag["edge_hashtag_to_media"]["page_info"]["end_cursor"]
        media = hashtag["edge_hashtag_to_media"]["edges"]
        return end_cursor, media

    def parse_to_json(self, response, write_to_file=False):
        # First script object will always be the json datas
        json_data = response.xpath("/html/body/script[1]/text()").extract_first()
        # Cut off the emoji shit
        json_data = json_data.replace("\\u", "u")
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

    def write_to_file(self, captions, hashtags):
        string_to_write = ""
        for i in range(len(captions)):
            if hashtags[i]:
                string_to_write += captions[i] + "\t" + ",".join(hashtags[i]) + "\n"
        self.file.write(string_to_write)



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
            