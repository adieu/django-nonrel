"""
PostgreSQL database backend for Django.

Requires psycopg 1: http://initd.org/projects/psycopg1
"""

from django.utils.encoding import smart_str, smart_unicode
from django.db.backends import BaseDatabaseWrapper, BaseDatabaseFeatures, util
from django.db.backends.postgresql.operations import DatabaseOperations
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

class DatabaseFeatures(BaseDatabaseFeatures):
    pass # This backend uses all the defaults.

class DatabaseWrapper(BaseDatabaseWrapper):
    features = DatabaseFeatures()
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
        if self.ops.postgres_version is None:
            cursor.execute("SELECT version()")
            self.ops.postgres_version = [int(val) for val in cursor.fetchone()[0].split()[1].split('.')]
        return cursor

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
