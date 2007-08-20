from django.db.backends import BaseDatabaseOperations

# This DatabaseOperations class lives in here instead of base.py because it's
# used by both the 'postgresql' and 'postgresql_psycopg2' backends.

class DatabaseOperations(BaseDatabaseOperations):
    def __init__(self, postgres_version=None):
        self.postgres_version = postgres_version

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
        if tables:
            if self.postgres_version[0] >= 8 and self.postgres_version[1] >= 1:
                # Postgres 8.1+ can do 'TRUNCATE x, y, z...;'. In fact, it *has to*
                # in order to be able to truncate tables referenced by a foreign
                # key in any other table. The result is a single SQL TRUNCATE
                # statement.
                sql = ['%s %s;' % \
                    (style.SQL_KEYWORD('TRUNCATE'),
                     style.SQL_FIELD(', '.join([self.quote_name(table) for table in tables]))
                )]
            else:
                # Older versions of Postgres can't do TRUNCATE in a single call, so
                # they must use a simple delete.
                sql = ['%s %s %s;' % \
                        (style.SQL_KEYWORD('DELETE'),
                         style.SQL_KEYWORD('FROM'),
                         style.SQL_FIELD(self.quote_name(table))
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
                        style.SQL_FIELD(self.quote_name('%s_%s_seq' % (table_name, column_name))),
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
                         style.SQL_FIELD(self.quote_name('%s_id_seq' % table_name)),
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
        output = []
        qn = self.quote_name
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