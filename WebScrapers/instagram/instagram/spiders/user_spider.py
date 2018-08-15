import scrapy
import json


class UserSpider(scrapy.Spider):
    name = "instagram_user"
    start_urls = [
        'https://www.instagram.com/instagram/'
    ]

    def parse(self, response):
        json_data = self.parse_to_json(response)
        user = json_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]
        self.unpack_user(user)

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
        #return json.loads(json_data)

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
