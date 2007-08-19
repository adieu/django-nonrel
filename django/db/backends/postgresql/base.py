"""
PostgreSQL database backend for Django.

Requires psycopg 1: http://initd.org/projects/psycopg1
"""

from django.utils.encoding import smart_str, smart_unicode
from django.db.backends import BaseDatabaseWrapper, BaseDatabaseOperations, util
try:
    import psycopg as Database
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured, "Error loading psycopg module: %s" % e

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

class UnicodeCursorWrapper(object):
    """
    A thin wrapper around psycopg cursors that allows them to accept Unicode
    strings as params.

    This is necessary because psycopg doesn't apply any DB quoting to
    parameters that are Unicode strings. If a param is Unicode, this will
    convert it to a bytestring using database client's encoding before passing
    it to psycopg.

    All results retrieved from the database are converted into Unicode strings
    before being returned to the caller.
    """
    def __init__(self, cursor, charset):
        self.cursor = cursor
        self.charset = charset

    def format_params(self, params):
        if isinstance(params, dict):
            result = {}
            charset = self.charset
            for key, value in params.items():
                result[smart_str(key, charset)] = smart_str(value, charset)
            return result
        else:
            return tuple([smart_str(p, self.charset, True) for p in params])

    def execute(self, sql, params=()):
        return self.cursor.execute(smart_str(sql, self.charset), self.format_params(params))

    def executemany(self, sql, param_list):
        new_param_list = [self.format_params(params) for params in param_list]
        return self.cursor.executemany(sql, new_param_list)

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            return getattr(self.cursor, attr)

postgres_version = None

class DatabaseOperations(BaseDatabaseOperations):
    def date_extract_sql(self, lookup_type, field_name):
        # http://www.postgresql.org/docs/8.0/static/functions-datetime.html#FUNCTIONS-DATETIME-EXTRACT
        return "EXTRACT('%s' FROM %s)" % (lookup_type, field_name)

    def date_trunc_sql(self, lookup_type, field_name):
        # http://www.postgresql.org/docs/8.0/static/functions-datetime.html#FUNCTIONS-DATETIME-TRUNC
        return "DATE_TRUNC('%s', %s)" % (lookup_type, field_name)

    def deferrable_sql(self):
        return " DEFERRABLE INITIALLY DEFERRED"

    def last_insert_id(self, cursor, table_name, pk_name):
        cursor.execute("SELECT CURRVAL('\"%s_%s_seq\"')" % (table_name, pk_name))
        return cursor.fetchone()[0]

class DatabaseWrapper(BaseDatabaseWrapper):
    ops = DatabaseOperations()

    def _cursor(self, settings):
        set_tz = False
        if self.connection is None:
            set_tz = True
            if settings.DATABASE_NAME == '':
                from django.core.exceptions import ImproperlyConfigured
                raise ImproperlyConfigured, "You need to specify DATABASE_NAME in your Django settings file."
            conn_string = "dbname=%s" % settings.DATABASE_NAME
            if settings.DATABASE_USER:
                conn_string = "user=%s %s" % (settings.DATABASE_USER, conn_string)
            if settings.DATABASE_PASSWORD:
                conn_string += " password='%s'" % settings.DATABASE_PASSWORD
            if settings.DATABASE_HOST:
                conn_string += " host=%s" % settings.DATABASE_HOST
            if settings.DATABASE_PORT:
                conn_string += " port=%s" % settings.DATABASE_PORT
            self.connection = Database.connect(conn_string, **self.options)
            self.connection.set_isolation_level(1) # make transactions transparent to all cursors
        cursor = self.connection.cursor()
        if set_tz:
            cursor.execute("SET TIME ZONE %s", [settings.TIME_ZONE])
        cursor.execute("SET client_encoding to 'UNICODE'")
        cursor = UnicodeCursorWrapper(cursor, 'utf-8')
        global postgres_version
        if not postgres_version:
            cursor.execute("SELECT version()")
            postgres_version = [int(val) for val in cursor.fetchone()[0].split()[1].split('.')]
        return cursor

allows_group_by_ordinal = True
allows_unique_and_pk = True
autoindexes_primary_keys = True
needs_datetime_string_cast = True
needs_upper_for_iops = False
supports_constraints = True
supports_tablespaces = False
uses_case_insensitive_names = False

def quote_name(name):
    if name.startswith('"') and name.endswith('"'):
        return name # Quoting once is enough.
    return '"%s"' % name

def dictfetchone(cursor):
    "Returns a row from the cursor as a dict"
    return cursor.dictfetchone()

def dictfetchmany(cursor, number):
    "Returns a certain number of rows from a cursor as a dict"
    return cursor.dictfetchmany(number)

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    return cursor.dictfetchall()

def get_random_function_sql():
    return "RANDOM()"

def get_pk_default_value():
    return "DEFAULT"

def get_max_name_length():
    return None

def get_start_transaction_sql():
    return "BEGIN;"

def get_sql_flush(style, tables, sequences):
    """Return a list of SQL statements required to remove all data from
    all tables in the database (without actually removing the tables
    themselves) and put the database in an empty 'initial' state

    """
    if tables:
        if postgres_version[0] >= 8 and postgres_version[1] >= 1:
            # Postgres 8.1+ can do 'TRUNCATE x, y, z...;'. In fact, it *has to*
            # in order to be able to truncate tables referenced by a foreign
            # key in any other table. The result is a single SQL TRUNCATE
            # statement.
            sql = ['%s %s;' % \
                (style.SQL_KEYWORD('TRUNCATE'),
                 style.SQL_FIELD(', '.join([quote_name(table) for table in tables]))
            )]
        else:
            # Older versions of Postgres can't do TRUNCATE in a single call, so
            # they must use a simple delete.
            sql = ['%s %s %s;' % \
                    (style.SQL_KEYWORD('DELETE'),
                     style.SQL_KEYWORD('FROM'),
                     style.SQL_FIELD(quote_name(table))
                     ) for table in tables]

        # 'ALTER SEQUENCE sequence_name RESTART WITH 1;'... style SQL statements
        # to reset sequence indices
        for sequence_info in sequences:
            table_name = sequence_info['table']
            column_name = sequence_info['column']
            if column_name and len(column_name)>0:
                # sequence name in this case will be <table>_<column>_seq
                sql.append("%s %s %s %s %s %s;" % \
                    (style.SQL_KEYWORD('ALTER'),
                    style.SQL_KEYWORD('SEQUENCE'),
                    style.SQL_FIELD(quote_name('%s_%s_seq' % (table_name, column_name))),
                    style.SQL_KEYWORD('RESTART'),
                    style.SQL_KEYWORD('WITH'),
                    style.SQL_FIELD('1')
                    )
                )
            else:
                # sequence name in this case will be <table>_id_seq
                sql.append("%s %s %s %s %s %s;" % \
                    (style.SQL_KEYWORD('ALTER'),
                     style.SQL_KEYWORD('SEQUENCE'),
                     style.SQL_FIELD(quote_name('%s_id_seq' % table_name)),
                     style.SQL_KEYWORD('RESTART'),
                     style.SQL_KEYWORD('WITH'),
                     style.SQL_FIELD('1')
                     )
                )
        return sql
    else:
        return []

def get_sql_sequence_reset(style, model_list):
    "Returns a list of the SQL statements to reset sequences for the given models."
    from django.db import models
    output = []
    for model in model_list:
        # Use `coalesce` to set the sequence for each model to the max pk value if there are records,
        # or 1 if there are none. Set the `is_called` property (the third argument to `setval`) to true
        # if there are records (as the max pk value is already in use), otherwise set it to false.
        for f in model._meta.fields:
            if isinstance(f, models.AutoField):
                output.append("%s setval('%s', coalesce(max(%s), 1), max(%s) %s null) %s %s;" % \
                    (style.SQL_KEYWORD('SELECT'),
                    style.SQL_FIELD(quote_name('%s_%s_seq' % (model._meta.db_table, f.column))),
                    style.SQL_FIELD(quote_name(f.column)),
                    style.SQL_FIELD(quote_name(f.column)),
                    style.SQL_KEYWORD('IS NOT'),
                    style.SQL_KEYWORD('FROM'),
                    style.SQL_TABLE(quote_name(model._meta.db_table))))
                break # Only one AutoField is allowed per model, so don't bother continuing.
        for f in model._meta.many_to_many:
            output.append("%s setval('%s', coalesce(max(%s), 1), max(%s) %s null) %s %s;" % \
                (style.SQL_KEYWORD('SELECT'),
                style.SQL_FIELD(quote_name('%s_id_seq' % f.m2m_db_table())),
                style.SQL_FIELD(quote_name('id')),
                style.SQL_FIELD(quote_name('id')),
                style.SQL_KEYWORD('IS NOT'),
                style.SQL_KEYWORD('FROM'),
                style.SQL_TABLE(f.m2m_db_table())))
    return output

def typecast_string(s):
    """
    Cast all returned strings to unicode strings.
    """
    if not s and not isinstance(s, str):
        return s
    return smart_unicode(s)

# Register these custom typecasts, because Django expects dates/times to be
# in Python's native (standard-library) datetime/time format, whereas psycopg
# use mx.DateTime by default.
try:
    Database.register_type(Database.new_type((1082,), "DATE", util.typecast_date))
except AttributeError:
    raise Exception, "You appear to be using psycopg version 2. Set your DATABASE_ENGINE to 'postgresql_psycopg2' instead of 'postgresql'."
Database.register_type(Database.new_type((1083,1266), "TIME", util.typecast_time))
Database.register_type(Database.new_type((1114,1184), "TIMESTAMP", util.typecast_timestamp))
Database.register_type(Database.new_type((16,), "BOOLEAN", util.typecast_boolean))
Database.register_type(Database.new_type((1700,), "NUMERIC", util.typecast_decimal))
Database.register_type(Database.new_type(Database.types[1043].values, 'STRING', typecast_string))

OPERATOR_MAPPING = {
    'exact': '= %s',
    'iexact': 'ILIKE %s',
    'contains': 'LIKE %s',
    'icontains': 'ILIKE %s',
    'regex': '~ %s',
    'iregex': '~* %s',
    'gt': '> %s',
    'gte': '>= %s',
    'lt': '< %s',
    'lte': '<= %s',
    'startswith': 'LIKE %s',
    'endswith': 'LIKE %s',
    'istartswith': 'ILIKE %s',
    'iendswith': 'ILIKE %s',
}
