# -*- coding: utf-8 -*-
import scrapy
import json
from web_sources_corpus import utils
from web_sources_corpus.spiders.BaseSpider import BaseSpider
from web_sources_corpus.items import WebSourcesCorpusItem


class NndbComSpider(BaseSpider):
    name = "nndb_com"
    allowed_domains = ['www.nndb.com']
    start_urls = (
        'http://www.nndb.com/',
    )

    list_page_selectors = 'xpath:.//a[@class="newslink"]/@href'
    detail_page_selectors = 'xpath:.//a[contains(@href, "http://www.nndb.com/people/")]/@href'

    item_class = WebSourcesCorpusItem
    item_fields = {
        'name': 'clean:xpath:.//table//td[1]//table//tr[3]//table//td//b1/text()'
    }

    def refine_item(self, response, item):
        base = './/table//td[1]//table//tr[3]//table//td'

        data = {}
        for paragraph in response.xpath(base + '//p'):
            fields = paragraph.xpath('./b/text()').extract()
            if not fields:
                continue

            contents = paragraph.xpath('.//text()').extract()
            for field, values in utils.split_at(contents, fields):
                if field is not None:
                    data[field.lower().strip().replace(':', '')] = ' '.join(values).strip()

        item['birth'] = data.get('born')
        item['death'] = data.get('died')
        item['other'] = json.dumps(data)

        return item
