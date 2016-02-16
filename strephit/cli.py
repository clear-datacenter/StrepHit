from __future__ import absolute_import
import click
import yaml
import sys
from strephit import commons, web_sources_corpus
from strephit.commons import logging


CLI_COMMANDS = {
    'commons': commons.cli,
    'web_sources_corpus': web_sources_corpus.cli,
}


@click.group(commands=CLI_COMMANDS)
@click.pass_context
@click.option('--log-level', type=(unicode, click.Choice(logging.LEVELS)), multiple=True)
def cli(ctxm, log_level):
    logging.setup()
    for module, level in log_level:
        logging.setLogLevel(module, level)