#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Usage:
    convert_sa_to_django [options] <sa-design>

Options:
    -h, --help        Show this page
    --debug            Show debug logging
    --verbose        Show verbose logging
"""
from docopt import docopt
import logging
import sys
import yaml

logger = logging.getLogger('convert_sa_to_django')

field_map = {
    "BOOLEAN": "BooleanField",
    "DATE": "DateField",
    "DATETIME": "DateTimeField",
    "DECIMAL": "DecimalField",
    "FLOAT": "FloatField",
    "INTEGER": "IntegerField",
    "NUMERIC": "NumericField",
    "SMALLINT": "SmallIntegerField",
    "TEXT": "TextField",
    "TIME": "TimeField",
    "VARCHAR": "CharField",
    "TIMESTAMP": "DateTimeField",
    "UUID": "UUIDField",
    "JSON": "JSONField",
    "JSONB": "JSONField",
}

def camelcase(s):
    return ''.join(x.capitalize() or '_' for x in s.split('_'))

def convert_field_type(field):
    if field['type'] in field_map:
        field['type'] = field_map[field['type']]
    elif "VARCHAR" in field['type']:
        field['len'] = int(field['type'].split('(')[1].split(')')[0])
        field['type'] = field_map['VARCHAR']
    if field.get('pk'):
        field['type'] = 'AutoField'



def clean_field(field):
    if 'ref' in field:
        if field['ref'] is None:
            del field['ref']
    if 'ref_field' in field:
        if field['ref_field'] is None:
            del field['ref_field']
    if 'ref' in field:
        field['ref'] = camelcase(field['ref'])
    if 'pk' in field:
        if not field['pk']:
            del field['pk']




def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = docopt(__doc__, args)
    if parsed_args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


    with open(parsed_args['<sa-design>']) as f:
        sa_design = yaml.safe_load(f)

        for model in sa_design['models']:
            for field in model['fields']:
                convert_field_type(field)
                clean_field(field)

            model['name'] = camelcase(model['name'])



        print(yaml.dump(sa_design))


    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
