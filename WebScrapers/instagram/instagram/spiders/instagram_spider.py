import scrapy


class InstagramSpider(scrapy.Spider):
    name = "instagram"
    start_urls = [
        'http://www.instagram.com/instagram'
    ]

    def parse(self, response):
        print(response.xpath("//*[@id='react-root']/section"))
        print(response.xpath("body/span/section"))
        
        print(response.url)
