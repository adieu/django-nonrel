"""
PostgreSQL database backend for Django.

Requires psycopg 2: http://initd.org/projects/psycopg2
"""

from django.db.backends import BaseDatabaseWrapper, BaseDatabaseOperations, util
try:
    import psycopg2 as Database
    import psycopg2.extensions
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured, "Error loading psycopg2 module: %s" % e

DatabaseError = Database.DatabaseError
IntegrityError = Database.IntegrityError

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

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

    def quote_name(self, name):
        if name.startswith('"') and name.endswith('"'):
            return name # Quoting once is enough.
        return '"%s"' % name

    def sql_flush(self, style, tables, sequences):
        qn = self.quote_name
        if tables:
            if postgres_version[0] >= 8 and postgres_version[1] >= 1:
                # Postgres 8.1+ can do 'TRUNCATE x, y, z...;'. In fact, it *has to*
                # in order to be able to truncate tables referenced by a foreign
                # key in any other table. The result is a single SQL TRUNCATE
                # statement.
                sql = ['%s %s;' % \
                    (style.SQL_KEYWORD('TRUNCATE'),
                     style.SQL_FIELD(', '.join([qn(table) for table in tables]))
                )]
            else:
                # Older versions of Postgres can't do TRUNCATE in a single call, so
                # they must use a simple delete.
                sql = ['%s %s %s;' % \
                        (style.SQL_KEYWORD('DELETE'),
                         style.SQL_KEYWORD('FROM'),
                         style.SQL_FIELD(qn(table))
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
                        style.SQL_FIELD(qn('%s_%s_seq' % (table_name, column_name))),
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
                         style.SQL_FIELD(qn('%s_id_seq' % table_name)),
                         style.SQL_KEYWORD('RESTART'),
                         style.SQL_KEYWORD('WITH'),
                         style.SQL_FIELD('1')
                         )
                    )
            return sql
        else:
            return []

    def sequence_reset_sql(self, style, model_list):
        from django.db import models
        qn = self.quote_name
        output = []
        for model in model_list:
            # Use `coalesce` to set the sequence for each model to the max pk value if there are records,
            # or 1 if there are none. Set the `is_called` property (the third argument to `setval`) to true
            # if there are records (as the max pk value is already in use), otherwise set it to false.
            for f in model._meta.fields:
                if isinstance(f, models.AutoField):
                    output.append("%s setval('%s', coalesce(max(%s), 1), max(%s) %s null) %s %s;" % \
                        (style.SQL_KEYWORD('SELECT'),
                        style.SQL_FIELD(qn('%s_%s_seq' % (model._meta.db_table, f.column))),
                        style.SQL_FIELD(qn(f.column)),
                        style.SQL_FIELD(qn(f.column)),
                        style.SQL_KEYWORD('IS NOT'),
                        style.SQL_KEYWORD('FROM'),
                        style.SQL_TABLE(qn(model._meta.db_table))))
                    break # Only one AutoField is allowed per model, so don't bother continuing.
            for f in model._meta.many_to_many:
                output.append("%s setval('%s', coalesce(max(%s), 1), max(%s) %s null) %s %s;" % \
                    (style.SQL_KEYWORD('SELECT'),
                    style.SQL_FIELD(qn('%s_id_seq' % f.m2m_db_table())),
                    style.SQL_FIELD(qn('id')),
                    style.SQL_FIELD(qn('id')),
                    style.SQL_KEYWORD('IS NOT'),
                    style.SQL_KEYWORD('FROM'),
                    style.SQL_TABLE(f.m2m_db_table())))
        return output

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
            self.connection.set_client_encoding('UTF8')
        cursor = self.connection.cursor()
        cursor.tzinfo_factory = None
        if set_tz:
            cursor.execute("SET TIME ZONE %s", [settings.TIME_ZONE])
        global postgres_version
        if not postgres_version:
            cursor.execute("SELECT version()")
            postgres_version = [int(val) for val in cursor.fetchone()[0].split()[1].split('.')]
        return cursor

allows_group_by_ordinal = True
allows_unique_and_pk = True
autoindexes_primary_keys = True
needs_datetime_string_cast = False
needs_upper_for_iops = False
supports_constraints = True
supports_tablespaces = False
uses_case_insensitive_names = False

dictfetchmany = util.dictfetchmany
dictfetchall = util.dictfetchall

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
