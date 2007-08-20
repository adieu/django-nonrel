try:
    # Only exists in Python 2.4+
    from threading import local
except ImportError:
    # Import copy of _thread_local.py from Python 2.4
    from django.utils._threading_local import local

class BaseDatabaseWrapper(local):
    """
    Represents a database connection.
    """
    ops = None
    def __init__(self, **kwargs):
        self.connection = None
        self.queries = []
        self.options = kwargs

    def _commit(self):
        if self.connection is not None:
            return self.connection.commit()

    def _rollback(self):
        if self.connection is not None:
            return self.connection.rollback()

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def cursor(self):
        from django.conf import settings
        cursor = self._cursor(settings)
        if settings.DEBUG:
            return self.make_debug_cursor(cursor)
        return cursor

    def make_debug_cursor(self, cursor):
        from django.db.backends import util
        return util.CursorDebugWrapper(cursor, self)

class BaseDatabaseOperations(object):
    """
    This class encapsulates all backend-specific differences, such as the way
    a backend performs ordering or calculates the ID of a recently-inserted
    row.
    """
    def autoinc_sql(self, table):
        """
        Returns any SQL needed to support auto-incrementing primary keys, or
        None if no SQL is necessary.

        This SQL is executed when a table is created.
        """
        return None

    def date_extract_sql(self, lookup_type, field_name):
        """
        Given a lookup_type of 'year', 'month' or 'day', returns the SQL that
        extracts a value from the given date field field_name.
        """
        raise NotImplementedError()

    def date_trunc_sql(self, lookup_type, field_name):
        """
        Given a lookup_type of 'year', 'month' or 'day', returns the SQL that
        truncates the given date field field_name to a DATE object with only
        the given specificity.
        """
        raise NotImplementedError()

    def datetime_cast_sql(self):
        """
        Returns the SQL necessary to cast a datetime value so that it will be
        retrieved as a Python datetime object instead of a string.

        This SQL should include a '%s' in place of the field's name. This
        method should return None if no casting is necessary.
        """
        return None

    def deferrable_sql(self):
        """
        Returns the SQL necessary to make a constraint "initially deferred"
        during a CREATE TABLE statement.
        """
        return ''

    def drop_foreignkey_sql(self):
        """
        Returns the SQL command that drops a foreign key.
        """
        return "DROP CONSTRAINT"

    def fulltext_search_sql(self, field_name):
        """
        Returns the SQL WHERE clause to use in order to perform a full-text
        search of the given field_name. Note that the resulting string should
        contain a '%s' placeholder for the value being searched against.
        """
        raise NotImplementedError('Full-text search is not implemented for this database backend')

    def last_insert_id(self, cursor, table_name, pk_name):
        """
        Given a cursor object that has just performed an INSERT statement into
        a table that has an auto-incrementing ID, returns the newly created ID.

        This method also receives the table name and the name of the primary-key
        column.
        """
        return cursor.lastrowid

    def limit_offset_sql(self, limit, offset=None):
        """
        Returns a LIMIT/OFFSET SQL clause, given a limit and optional offset.
        """
        # 'LIMIT 40 OFFSET 20'
        sql = "LIMIT %s" % limit
        if offset and offset != 0:
            sql += " OFFSET %s" % offset
        return sql

    def max_name_length(self):
        """
        Returns the maximum length of table and column names, or None if there
        is no limit.
        """
        return None

    def pk_default_value(self):
        """
        Returns the value to use during an INSERT statement to specify that
        the field should use its default value.
        """
        return 'DEFAULT'

    def random_function_sql(self):
        """
        Returns a SQL expression that returns a random value.
        """
        return 'RANDOM()'

    def sql_flush(self, style, tables, sequences):
        """
        Returns a list of SQL statements required to remove all data from
        the given database tables (without actually removing the tables
        themselves).

        The `style` argument is a Style object as returned by either
        color_style() or no_style() in django.core.management.color.
        """
        raise NotImplementedError()

    def sequence_reset_sql(self, style, model_list):
        """
        Returns a list of the SQL statements required to reset sequences for
        the given models.

        The `style` argument is a Style object as returned by either
        color_style() or no_style() in django.core.management.color.
        """
        return [] # No sequence reset required by default.

    def start_transaction_sql(self):
        """
        Returns the SQL statement required to start a transaction.
        """
        return "BEGIN;"

    def tablespace_sql(self, tablespace, inline=False):
        """
        Returns the tablespace SQL, or None if the backend doesn't use
        tablespaces.
        """
        return None
