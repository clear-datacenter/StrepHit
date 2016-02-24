# -*- encoding: utf-8 -*-
from __future__ import absolute_import
import click
import json
import logging
from collections import defaultdict
from strephit.commons import io, wikidata, parallel


logger = logging.getLogger(__name__)


def get_wikidata_id(name, cache, language):
    results = wikidata.call_api('wbsearchentities',  search=name, language=language)
    for r in results.get('search', []):
        if r.get('label').lower() == name.lower():
            return r['id']
    else:
        return None


def fix_name(name):
    name = name.lower()

    name, honorifics = strip_honorifics(name)

    try:
        last_name, first_name = name.split(',', 1)
        name = first_name.strip() + ' ' + last_name.strip()
    except ValueError:
        pass

    return name.strip(), honorifics


def strip_honorifics(name):
    honorifics = []
    changed = True
    while changed:
        changed = False
        for prefix in ['prof', 'dr', 'phd', 'sir', 'mr', 'mrs', 'miss', 'mister',
                       'bishop', 'arcibishop', 'st', 'hon', 'rav']:
            if name.startswith(prefix):
                honorifics.append(prefix)
                changed = True
                name = name[len(prefix):]
                if name[0] == '.':
                    name = name[1:].strip()
    return name, honorifics


def serialize_item((i, item, cache, language)):
    _id = item.get('id', i)
    name = item.get('name')
    other = item.get('other', {})

    if not name:
        logger.debug('item %s has no name, skipping' % _id)
        return

    data = {}
    try:
        data = json.loads(other)
    except ValueError:
        pass
    except TypeError:
        if isinstance(other, dict):
            data = other

    name, honorifics = fix_name(name)
    wid = get_wikidata_id(name, cache, language)
    if not wid:
        logger.debug('cannod find wikidata id for item %s (%s), skipping' % (
            _id, name)
        )
        return

    data.update(item)
    data['name'] = name

    for key, value in data.iteritems():
        statement = wikidata.finalize_statement(wid, key, value, language,
                                                item.get('url'))
        if statement:
            yield statement
        else:
            logger.debug('skipped property %s of %s (%s)' % (key, _id, name))

    for each in honorifics:
        statement = wikidata.finalize_statement(wid, 'honorific', each, language,
                                                item.get('url'))
        if statement:
            yield statement


@click.command()
@click.argument('corpus-dir', type=click.Path())
@click.argument('out-file', type=click.File('w'))
@click.option('--cache/--no-cache', default=True, help='Cache HTTP requests')
@click.option('--language', default='en', help='The names are searched in this language')
@click.option('--processes', '-p', default=0)
def process_semistructured(corpus_dir, out_file, cache, language, processes):
    """ Processes the corpus and extracts semistructured data serialized into quick statements
    """

    params = ((i, item, cache, language)
             for i, item in enumerate(io.load_scraped_items(corpus_dir)))
    for statement in parallel.map(serialize_item, params, processes, flatten=True):
        out_file.write(statement.encode('utf8'))
        out_file.write('\n')