#!/usr/bin/env python
from django.core import management
from optparse import OptionParser
import os, sys

ACTION_MAPPING = {
    'adminindex': management.get_admin_index,
    'createsuperuser': management.createsuperuser,
    'createcachetable' : management.createcachetable,
#     'dbcheck': management.database_check,
    'init': management.init,
    'inspectdb': management.inspectdb,
    'install': management.install,
    'runserver': management.runserver,
    'sql': management.get_sql_create,
    'sqlall': management.get_sql_all,
    'sqlclear': management.get_sql_delete,
    'sqlindexes': management.get_sql_indexes,
    'sqlinitialdata': management.get_sql_initial_data,
    'sqlreset': management.get_sql_reset,
    'sqlsequencereset': management.get_sql_sequence_reset,
    'startapp': management.startapp,
    'startproject': management.startproject,
    'validate': management.validate,
}

NO_SQL_TRANSACTION = ('adminindex', 'createcachetable', 'dbcheck', 'install', 'sqlindexes')

def get_usage():
    """
    Returns a usage string. Doesn't do the options stuff, because optparse
    takes care of that.
    """
    usage = ["usage: %prog action [options]\nactions:"]
    available_actions = ACTION_MAPPING.keys()
    available_actions.sort()
    for a in available_actions:
        func = ACTION_MAPPING[a]
        usage.append("  %s %s -- %s" % (a, func.args, getattr(func, 'help_doc', func.__doc__)))
    return '\n'.join(usage)

class DjangoOptionParser(OptionParser):
    def print_usage_and_exit(self):
        self.print_help(sys.stderr)
        sys.exit(1)

def print_error(msg, cmd):
    sys.stderr.write('Error: %s\nRun "%s --help" for help.\n' % (msg, cmd))
    sys.exit(1)

def main():
    # Parse the command-line arguments. optparse handles the dirty work.
    parser = DjangoOptionParser(get_usage())
    parser.add_option('--settings',
        help='Python path to settings module, e.g. "myproject.settings.main". If this isn\'t provided, the DJANGO_SETTINGS_MODULE environment variable will be used.')
    parser.add_option('--pythonpath',
        help='Lets you manually add a directory the Python path, e.g. "/home/djangoprojects/myproject".')
    options, args = parser.parse_args()

    # Take care of options.
    if options.settings:
        os.environ['DJANGO_SETTINGS_MODULE'] = options.settings
    if options.pythonpath:
        sys.path.insert(0, options.pythonpath)

    # Run the appropriate action. Unfortunately, optparse can't handle
    # positional arguments, so this has to parse/validate them.
    try:
        action = args[0]
    except IndexError:
        print_error("An action is required.", sys.argv[0])
    if not ACTION_MAPPING.has_key(action):
        print_error("Your action, %r, was invalid." % action, sys.argv[0])
    if action in ('createsuperuser', 'init', 'validate'):
        ACTION_MAPPING[action]()
    elif action == 'inspectdb':
        try:
            param = args[1]
        except IndexError:
            parser.print_usage_and_exit()
        try:
            for line in ACTION_MAPPING[action](param):
                print line
        except NotImplementedError:
            sys.stderr.write("Error: %r isn't supported for the currently selected database backend.\n" % action)
            sys.exit(1)
    elif action == 'createcachetable':
        try:
            ACTION_MAPPING[action](args[1])
        except IndexError:
            parser.print_usage_and_exit()
    elif action in ('startapp', 'startproject'):
        try:
            name = args[1]
        except IndexError:
            parser.print_usage_and_exit()
        ACTION_MAPPING[action](name, os.getcwd())
    elif action == 'runserver':
        if len(args) < 2:
            addr = ''
            port = '8000'
        else:
            try:
                addr, port = args[1].split(':')
            except ValueError:
                addr, port = '', args[1]
        ACTION_MAPPING[action](addr, port)
    else:
        from django.core import meta
        if action == 'dbcheck':
            mod_list = meta.get_all_installed_modules()
        else:
            try:
                mod_list = [meta.get_app(app_label) for app_label in args[1:]]
            except ImportError, e:
                sys.stderr.write("Error: %s. Are you sure your INSTALLED_APPS setting is correct?\n" % e)
                sys.exit(1)
            if not mod_list:
                parser.print_usage_and_exit()
        if action not in NO_SQL_TRANSACTION:
            print "BEGIN;"
        for mod in mod_list:
            output = ACTION_MAPPING[action](mod)
            if output:
                print '\n'.join(output)
        if action not in NO_SQL_TRANSACTION:
            print "COMMIT;"

if __name__ == "__main__":
    main()
