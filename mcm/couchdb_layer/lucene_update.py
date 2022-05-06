import argparse
import logging
import json
import os
from tools.config_manager import Config
from mcm_database import Database


logger = logging.getLogger()


def update_database(database_name):
    logger.info('Updating database: %s', database_name)
    file_name = 'lucene_%s.js' % (database_name)
    if not os.path.isfile(file_name):
        logger.error('File %s does not exist', file_name)
        return

    with open(file_name, 'r') as input_file:
        script = input_file.read()

    logger.debug('Script: %s', script)
    while '\n ' in script or ',  ' in script:
        script = script.replace('\n ', '\n').replace(',  ', ', ')

    script = script.replace('\n', ' ').strip()
    logger.debug('Script in a single line: %s', script)
    database = Database(database_name)
    doc = database.get('_design/lucene')
    logger.info('Fetched a document %s (%s)', doc.get('_id'), doc.get('_rev'))
    logger.debug('Document: %s', json.dumps(doc, indent=2, sort_keys=True))
    doc['fulltext']['search']['index'] = script
    database.update(doc)


def main():
    """
    Main function
    """
    parser = argparse.ArgumentParser(description='Push lucene mapping to database')
    parser.add_argument('--db', help='Comma separated list of database names', type=str, required=True)
    parser.add_argument('--debug', help='Debug mode', action='store_true')
    parser.add_argument('--prod', help='Production mode', action='store_true')
    args = vars(parser.parse_args())
    debug = args.get('debug')
    # Setup loggers
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', level=log_level)
    logging.root.setLevel(log_level)

    # Read config
    prod = args.get('prod')
    dev = not prod
    Config.load('../config.cfg', 'production' if prod else 'development')
    Config.set('dev', dev)
    assert dev == Config.get('dev')
    database_names = [db.strip() for db in args.get('db').split(',') if db.strip()]
    database_names = sorted(list(set(database_names)))
    for database_name in database_names:
        update_database(database_name)


if __name__ == '__main__':
    main()
