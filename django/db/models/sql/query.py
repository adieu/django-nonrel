"""
Create SQL statements for QuerySets.

The code in here encapsulates all of the SQL construction so that QuerySets
themselves do not have to (and could be backed by things other than SQL
databases). The abstraction barrier only works one way: this module has to know
all about the internals of models in order to get the information it needs.
"""

from copy import deepcopy

from django.utils.tree import Node
from django.utils.datastructures import SortedDict
from django.dispatch import dispatcher
from django.db import connection
from django.db.models import signals
from django.db.models.sql.where import WhereNode, EverythingNode, AND, OR
from django.db.models.sql.datastructures import Count
from django.db.models.fields import FieldDoesNotExist
from django.core.exceptions import FieldError
from datastructures import EmptyResultSet, Empty, MultiJoin
from constants import *

try:
    set
except NameError:
    from sets import Set as set     # Python 2.3 fallback

__all__ = ['Query']

class Query(object):
    """
    A single SQL query.
    """
    # SQL join types. These are part of the class because their string forms
    # vary from database to database and can be customised by a subclass.
    INNER = 'INNER JOIN'
    LOUTER = 'LEFT OUTER JOIN'

    alias_prefix = 'T'
    query_terms = QUERY_TERMS

    def __init__(self, model, connection, where=WhereNode):
        self.model = model
        self.connection = connection
        self.alias_refcount = {}
        self.alias_map = {}     # Maps alias to join information
        self.table_map = {}     # Maps table names to list of aliases.
        self.join_map = {}
        self.rev_join_map = {}  # Reverse of join_map.
        self.quote_cache = {}
        self.default_cols = True
        self.default_ordering = True
        self.standard_ordering = True
        self.ordering_aliases = []
        self.start_meta = None
        self.select_fields = []
        self.related_select_fields = []

        # SQL-related attributes
        self.select = []
        self.tables = []    # Aliases in the order they are created.
        self.where = where()
        self.where_class = where
        self.group_by = []
        self.having = []
        self.order_by = []
        self.low_mark, self.high_mark = 0, None  # Used for offset/limit
        self.distinct = False
        self.select_related = False
        self.related_select_cols = []

        # Arbitrary maximum limit for select_related. Prevents infinite
        # recursion. Can be changed by the depth parameter to select_related().
        self.max_depth = 5

        # These are for extensions. The contents are more or less appended
        # verbatim to the appropriate clause.
        self.extra_select = {}  # Maps col_alias -> col_sql.
        self.extra_select_params = ()
        self.extra_tables = ()
        self.extra_where = ()
        self.extra_params = ()
        self.extra_order_by = ()

    def __str__(self):
        """
        Returns the query as a string of SQL with the parameter values
        substituted in.

        Parameter values won't necessarily be quoted correctly, since that is
        done by the database interface at execution time.
        """
        sql, params = self.as_sql()
        return sql % params

    def __deepcopy__(self, memo):
        result= self.clone()
        memo[id(self)] = result
        return result

    def get_meta(self):
        """
        Returns the Options instance (the model._meta) from which to start
        processing. Normally, this is self.model._meta, but it can change.
        """
        if self.start_meta:
            return self.start_meta
        return self.model._meta

    def quote_name_unless_alias(self, name):
        """
        A wrapper around connection.ops.quote_name that doesn't quote aliases
        for table names. This avoids problems with some SQL dialects that treat
        quoted strings specially (e.g. PostgreSQL).
        """
        if name in self.quote_cache:
            return self.quote_cache[name]
        if ((name in self.alias_map and name not in self.table_map) or
                name in self.extra_select):
            self.quote_cache[name] = name
            return name
        r = self.connection.ops.quote_name(name)
        self.quote_cache[name] = r
        return r

    def clone(self, klass=None, **kwargs):
        """
        Creates a copy of the current instance. The 'kwargs' parameter can be
        used by clients to update attributes after copying has taken place.
        """
        obj = Empty()
        obj.__class__ = klass or self.__class__
        obj.model = self.model
        obj.connection = self.connection
        obj.alias_refcount = self.alias_refcount.copy()
        obj.alias_map = self.alias_map.copy()
        obj.table_map = self.table_map.copy()
        obj.join_map = self.join_map.copy()
        obj.rev_join_map = self.rev_join_map.copy()
        obj.quote_cache = {}
        obj.default_cols = self.default_cols
        obj.default_ordering = self.default_ordering
        obj.standard_ordering = self.standard_ordering
        obj.ordering_aliases = []
        obj.start_meta = self.start_meta
        obj.select_fields = self.select_fields[:]
        obj.related_select_fields = self.related_select_fields[:]
        obj.select = self.select[:]
        obj.tables = self.tables[:]
        obj.where = deepcopy(self.where)
        obj.where_class = self.where_class
        obj.group_by = self.group_by[:]
        obj.having = self.having[:]
        obj.order_by = self.order_by[:]
        obj.low_mark, obj.high_mark = self.low_mark, self.high_mark
        obj.distinct = self.distinct
        obj.select_related = self.select_related
        obj.related_select_cols = []
        obj.max_depth = self.max_depth
        obj.extra_select = self.extra_select.copy()
        obj.extra_select_params = self.extra_select_params
        obj.extra_tables = self.extra_tables
        obj.extra_where = self.extra_where
        obj.extra_params = self.extra_params
        obj.extra_order_by = self.extra_order_by
        obj.__dict__.update(kwargs)
        if hasattr(obj, '_setup_query'):
            obj._setup_query()
        return obj

    def results_iter(self):
        """
        Returns an iterator over the results from executing this query.
        """
        resolve_columns = hasattr(self, 'resolve_columns')
        if resolve_columns:
            if self.select_fields:
                fields = self.select_fields + self.related_select_fields
            else:
                fields = self.model._meta.fields
        for rows in self.execute_sql(MULTI):
            for row in rows:
                if resolve_columns:
                    row = self.resolve_columns(row, fields)
                yield row

    def get_count(self):
        """
        Performs a COUNT() query using the current filter constraints.
        """
        from subqueries import CountQuery
        obj = self.clone()
        obj.clear_ordering(True)
        obj.clear_limits()
        obj.select_related = False
        obj.related_select_cols = []
        obj.related_select_fields = []
        if obj.distinct and len(obj.select) > 1:
            obj = self.clone(CountQuery, _query=obj, where=self.where_class(),
                    distinct=False)
            obj.select = []
            obj.extra_select = {}
        obj.add_count_column()
        data = obj.execute_sql(SINGLE)
        if not data:
            return 0
        number = data[0]

        # Apply offset and limit constraints manually, since using LIMIT/OFFSET
        # in SQL (in variants that provide them) doesn't change the COUNT
        # output.
        number = max(0, number - self.low_mark)
        if self.high_mark:
            number = min(number, self.high_mark - self.low_mark)

        return number

    def as_sql(self, with_limits=True, with_col_aliases=False):
        """
        Creates the SQL for this query. Returns the SQL string and list of
        parameters.

        If 'with_limits' is False, any limit/offset information is not included
        in the query.
        """
        self.pre_sql_setup()
        out_cols = self.get_columns(with_col_aliases)
        ordering = self.get_ordering()

        # This must come after 'select' and 'ordering' -- see docstring of
        # get_from_clause() for details.
        from_, f_params = self.get_from_clause()

        where, w_params = self.where.as_sql(qn=self.quote_name_unless_alias)
        params = list(self.extra_select_params)

        result = ['SELECT']
        if self.distinct:
            result.append('DISTINCT')
        result.append(', '.join(out_cols + self.ordering_aliases))

        result.append('FROM')
        result.extend(from_)
        params.extend(f_params)

        if where:
            result.append('WHERE %s' % where)
            params.extend(w_params)
        if self.extra_where:
            if not where:
                result.append('WHERE')
            else:
                result.append('AND')
            result.append(' AND '.join(self.extra_where))

        if self.group_by:
            grouping = self.get_grouping()
            result.append('GROUP BY %s' % ', '.join(grouping))

        if ordering:
            result.append('ORDER BY %s' % ', '.join(ordering))

        # FIXME: Pull this out to make life easier for Oracle et al.
        if with_limits:
            if self.high_mark:
                result.append('LIMIT %d' % (self.high_mark - self.low_mark))
            if self.low_mark:
                if not self.high_mark:
                    val = self.connection.ops.no_limit_value()
                    if val:
                        result.append('LIMIT %d' % val)
                result.append('OFFSET %d' % self.low_mark)

        params.extend(self.extra_params)
        return ' '.join(result), tuple(params)

    def combine(self, rhs, connector):
        """
        Merge the 'rhs' query into the current one (with any 'rhs' effects
        being applied *after* (that is, "to the right of") anything in the
        current query. 'rhs' is not modified during a call to this function.

        The 'connector' parameter describes how to connect filters from the
        'rhs' query.
        """
        assert self.model == rhs.model, \
                "Cannot combine queries on two different base models."
        assert self.can_filter(), \
                "Cannot combine queries once a slice has been taken."
        assert self.distinct == rhs.distinct, \
            "Cannot combine a unique query with a non-unique query."

        # Work out how to relabel the rhs aliases, if necessary.
        change_map = {}
        used = set()
        conjunction = (connector == AND)
        first = True
        for alias in rhs.tables:
            if not rhs.alias_refcount[alias]:
                # An unused alias.
                continue
            promote = (rhs.alias_map[alias][JOIN_TYPE] == self.LOUTER)
            new_alias = self.join(rhs.rev_join_map[alias],
                    (conjunction and not first), used, promote, not conjunction)
            used.add(new_alias)
            change_map[alias] = new_alias
            first = False

        # So that we don't exclude valid results in an "or" query combination,
        # the first join that is exclusive to the lhs (self) must be converted
        # to an outer join.
        if not conjunction:
            for alias in self.tables[1:]:
                if self.alias_refcount[alias] == 1:
                    self.promote_alias(alias, True)
                    break

        # Now relabel a copy of the rhs where-clause and add it to the current
        # one.
        if rhs.where:
            w = deepcopy(rhs.where)
            w.relabel_aliases(change_map)
            if not self.where:
                # Since 'self' matches everything, add an explicit "include
                # everything" where-constraint so that connections between the
                # where clauses won't exclude valid results.
                self.where.add(EverythingNode(), AND)
        elif self.where:
            # rhs has an empty where clause.
            w = self.where_class()
            w.add(EverythingNode(), AND)
        else:
            w = self.where_class()
        self.where.add(w, connector)

        # Selection columns and extra extensions are those provided by 'rhs'.
        self.select = []
        for col in rhs.select:
            if isinstance(col, (list, tuple)):
                self.select.append((change_map.get(col[0], col[0]), col[1]))
            else:
                item = deepcopy(col)
                item.relabel_aliases(change_map)
                self.select.append(item)
        self.select_fields = rhs.select_fields[:]
        self.extra_select = rhs.extra_select.copy()
        self.extra_tables = rhs.extra_tables
        self.extra_where = rhs.extra_where
        self.extra_params = rhs.extra_params

        # Ordering uses the 'rhs' ordering, unless it has none, in which case
        # the current ordering is used.
        self.order_by = rhs.order_by and rhs.order_by[:] or self.order_by
        self.extra_order_by = rhs.extra_order_by or self.extra_order_by

    def pre_sql_setup(self):
        """
        Does any necessary class setup immediately prior to producing SQL. This
        is for things that can't necessarily be done in __init__ because we
        might not have all the pieces in place at that time.
        """
        if not self.tables:
            self.join((None, self.model._meta.db_table, None, None))
        if self.select_related and not self.related_select_cols:
            self.fill_related_selections()

    def get_columns(self, with_aliases=False):
        """
        Return the list of columns to use in the select statement. If no
        columns have been specified, returns all columns relating to fields in
        the model.

        If 'with_aliases' is true, any column names that are duplicated
        (without the table names) are given unique aliases. This is needed in
        some cases to avoid ambiguitity with nested queries.
        """
        qn = self.quote_name_unless_alias
        result = ['(%s) AS %s' % (col, alias) for alias, col in self.extra_select.iteritems()]
        aliases = set(self.extra_select.keys())
        if with_aliases:
            col_aliases = aliases.copy()
        else:
            col_aliases = set()
        if self.select:
            for col in self.select:
                if isinstance(col, (list, tuple)):
                    r = '%s.%s' % (qn(col[0]), qn(col[1]))
                    if with_aliases and col[1] in col_aliases:
                        c_alias = 'Col%d' % len(col_aliases)
                        result.append('%s AS %s' % (r, c_alias))
                        aliases.add(c_alias)
                        col_aliases.add(c_alias)
                    else:
                        result.append(r)
                        aliases.add(r)
                        col_aliases.add(col[1])
                else:
                    result.append(col.as_sql(quote_func=qn))
                    if hasattr(col, 'alias'):
                        aliases.add(col.alias)
                        col_aliases.add(col.alias)
        elif self.default_cols:
            cols, new_aliases = self.get_default_columns(with_aliases,
                    col_aliases)
            result.extend(cols)
            aliases.update(new_aliases)
        for table, col in self.related_select_cols:
            r = '%s.%s' % (qn(table), qn(col))
            if with_aliases and col in col_aliases:
                c_alias = 'Col%d' % len(col_aliases)
                result.append('%s AS %s' % (r, c_alias))
                aliases.add(c_alias)
                col_aliases.add(c_alias)
            else:
                result.append(r)
                aliases.add(r)
                col_aliases.add(col)

        self._select_aliases = aliases
        return result

    def get_default_columns(self, with_aliases=False, col_aliases=None):
        """
        Computes the default columns for selecting every field in the base
        model.

        Returns a list of strings, quoted appropriately for use in SQL
        directly, as well as a set of aliases used in the select statement.
        """
        result = []
        table_alias = self.tables[0]
        root_pk = self.model._meta.pk.column
        seen = {None: table_alias}
        qn = self.quote_name_unless_alias
        qn2 = self.connection.ops.quote_name
        aliases = set()
        for field, model in self.model._meta.get_fields_with_model():
            try:
                alias = seen[model]
            except KeyError:
                alias = self.join((table_alias, model._meta.db_table,
                        root_pk, model._meta.pk.column))
                seen[model] = alias
            if with_aliases and field.column in col_aliases:
                c_alias = 'Col%d' % len(col_aliases)
                result.append('%s.%s AS %s' % (qn(alias),
                    qn2(field.column), c_alias))
                col_aliases.add(c_alias)
                aliases.add(c_alias)
            else:
                r = '%s.%s' % (qn(alias), qn2(field.column))
                result.append(r)
                aliases.add(r)
                if with_aliases:
                    col_aliases.add(field.column)
        return result, aliases

    def get_from_clause(self):
        """
        Returns a list of strings that are joined together to go after the
        "FROM" part of the query, as well as a list any extra parameters that
        need to be included. Sub-classes, can override this to create a
        from-clause via a "select", for example (e.g. CountQuery).

        This should only be called after any SQL construction methods that
        might change the tables we need. This means the select columns and
        ordering must be done first.
        """
        result = []
        qn = self.quote_name_unless_alias
        qn2 = self.connection.ops.quote_name
        first = True
        for alias in self.tables:
            if not self.alias_refcount[alias]:
                continue
            try:
                name, alias, join_type, lhs, lhs_col, col, nullable = self.alias_map[alias]
            except KeyError:
                # Extra tables can end up in self.tables, but not in the
                # alias_map if they aren't in a join. That's OK. We skip them.
                continue
            alias_str = (alias != name and ' %s' % alias or '')
            if join_type and not first:
                result.append('%s %s%s ON (%s.%s = %s.%s)'
                        % (join_type, qn(name), alias_str, qn(lhs),
                           qn2(lhs_col), qn(alias), qn2(col)))
            else:
                connector = not first and ', ' or ''
                result.append('%s%s%s' % (connector, qn(name), alias_str))
            first = False
        for t in self.extra_tables:
            alias, unused = self.table_alias(t)
            if alias not in self.alias_map:
                connector = not first and ', ' or ''
                result.append('%s%s' % (connector, qn(alias)))
                first = False
        return result, []

    def get_grouping(self):
        """
        Returns a tuple representing the SQL elements in the "group by" clause.
        """
        qn = self.quote_name_unless_alias
        result = []
        for col in self.group_by:
            if isinstance(col, (list, tuple)):
                result.append('%s.%s' % (qn(col[0]), qn(col[1])))
            elif hasattr(col, 'as_sql'):
                result.append(col.as_sql(qn))
            else:
                result.append(str(col))
        return result

    def get_ordering(self):
        """
        Returns list representing the SQL elements in the "order by" clause.
        Also sets the ordering_aliases attribute on this instance to a list of
        extra aliases needed in the select.

        Determining the ordering SQL can change the tables we need to include,
        so this should be run *before* get_from_clause().
        """
        if self.extra_order_by:
            ordering = self.extra_order_by
        elif not self.default_ordering:
            ordering = []
        else:
            ordering = self.order_by or self.model._meta.ordering
        qn = self.quote_name_unless_alias
        qn2 = self.connection.ops.quote_name
        distinct = self.distinct
        select_aliases = self._select_aliases
        result = []
        ordering_aliases = []
        if self.standard_ordering:
            asc, desc = ORDER_DIR['ASC']
        else:
            asc, desc = ORDER_DIR['DESC']
        for field in ordering:
            if field == '?':
                result.append(self.connection.ops.random_function_sql())
                continue
            if isinstance(field, int):
                if field < 0:
                    order = desc
                    field = -field
                else:
                    order = asc
                result.append('%s %s' % (field, order))
                continue
            if '.' in field:
                # This came in through an extra(order_by=...) addition. Pass it
                # on verbatim.
                col, order = get_order_dir(field, asc)
                table, col = col.split('.', 1)
                elt = '%s.%s' % (qn(table), col)
                if not distinct or elt in select_aliases:
                    result.append('%s %s' % (elt, order))
            elif get_order_dir(field)[0] not in self.extra_select:
                # 'col' is of the form 'field' or 'field1__field2' or
                # '-field1__field2__field', etc.
                for table, col, order in self.find_ordering_name(field,
                        self.model._meta, default_order=asc):
                    elt = '%s.%s' % (qn(table), qn2(col))
                    if distinct and elt not in select_aliases:
                        ordering_aliases.append(elt)
                    result.append('%s %s' % (elt, order))
            else:
                col, order = get_order_dir(field, asc)
                elt = qn(col)
                if distinct and elt not in select_aliases:
                    ordering_aliases.append(elt)
                result.append('%s %s' % (elt, order))
        self.ordering_aliases = ordering_aliases
        return result

    def find_ordering_name(self, name, opts, alias=None, default_order='ASC',
            already_seen=None):
        """
        Returns the table alias (the name might be ambiguous, the alias will
        not be) and column name for ordering by the given 'name' parameter.
        The 'name' is of the form 'field1__field2__...__fieldN'.
        """
        name, order = get_order_dir(name, default_order)
        pieces = name.split(LOOKUP_SEP)
        if not alias:
            alias = self.get_initial_alias()
        field, target, opts, joins, last = self.setup_joins(pieces, opts,
                alias, False)
        alias = joins[-1]
        col = target.column

        # If we get to this point and the field is a relation to another model,
        # append the default ordering for that model.
        if field.rel and len(joins) > 1 and opts.ordering:
            # Firstly, avoid infinite loops.
            if not already_seen:
                already_seen = set()
            join_tuple = tuple([self.alias_map[j][TABLE_NAME] for j in joins])
            if join_tuple in already_seen:
                raise FieldError('Infinite loop caused by ordering.')
            already_seen.add(join_tuple)

            results = []
            for item in opts.ordering:
                results.extend(self.find_ordering_name(item, opts, alias,
                        order, already_seen))
            return results

        if alias:
            # We have to do the same "final join" optimisation as in
            # add_filter, since the final column might not otherwise be part of
            # the select set (so we can't order on it).
            join = self.alias_map[alias]
            if col == join[RHS_JOIN_COL]:
                self.unref_alias(alias)
                alias = join[LHS_ALIAS]
                col = join[LHS_JOIN_COL]
        return [(alias, col, order)]

    def table_alias(self, table_name, create=False):
        """
        Returns a table alias for the given table_name and whether this is a
        new alias or not.

        If 'create' is true, a new alias is always created. Otherwise, the
        most recently created alias for the table (if one exists) is reused.
        """
        current = self.table_map.get(table_name)
        if not create and current:
            alias = current[0]
            self.alias_refcount[alias] += 1
            return alias, False

        # Create a new alias for this table.
        if current:
            alias = '%s%d' % (self.alias_prefix, len(self.alias_map) + 1)
            current.append(alias)
        else:
            # The first occurence of a table uses the table name directly.
            alias = table_name
            self.table_map[alias] = [alias]
        self.alias_refcount[alias] = 1
        #self.alias_map[alias] = None
        self.tables.append(alias)
        return alias, True

    def ref_alias(self, alias):
        """ Increases the reference count for this alias. """
        self.alias_refcount[alias] += 1

    def unref_alias(self, alias):
        """ Decreases the reference count for this alias. """
        self.alias_refcount[alias] -= 1

    def promote_alias(self, alias, unconditional=False):
        """
        Promotes the join type of an alias to an outer join if it's possible
        for the join to contain NULL values on the left. If 'unconditional' is
        False, the join is only promoted if it is nullable, otherwise it is
        always promoted.
        """
        if ((unconditional or self.alias_map[alias][NULLABLE]) and
                self.alias_map[alias] != self.LOUTER):
            data = list(self.alias_map[alias])
            data[JOIN_TYPE] = self.LOUTER
            self.alias_map[alias] = tuple(data)

    def change_aliases(self, change_map):
        """
        Changes the aliases in change_map (which maps old-alias -> new-alias),
        relabelling any references to them in select columns and the where
        clause.
        """
        assert set(change_map.keys()).intersection(set(change_map.values())) == set()

        # 1. Update references in "select" and "where".
        self.where.relabel_aliases(change_map)
        for pos, col in enumerate(self.select):
            if isinstance(col, (list, tuple)):
                self.select[pos] = (change_map.get(old_alias, old_alias), col[1])
            else:
                col.relabel_aliases(change_map)

        # 2. Rename the alias in the internal table/alias datastructures.
        for old_alias, new_alias in change_map.iteritems():
            alias_data = list(self.alias_map[old_alias])
            alias_data[RHS_ALIAS] = new_alias

            t = self.rev_join_map[old_alias]
            data = list(self.join_map[t])
            data[data.index(old_alias)] = new_alias
            self.join_map[t] = tuple(data)
            self.rev_join_map[new_alias] = t
            del self.rev_join_map[old_alias]
            self.alias_refcount[new_alias] = self.alias_refcount[old_alias]
            del self.alias_refcount[old_alias]
            self.alias_map[new_alias] = tuple(alias_data)
            del self.alias_map[old_alias]

            table_aliases = self.table_map[alias_data[TABLE_NAME]]
            for pos, alias in enumerate(table_aliases):
                if alias == old_alias:
                    table_aliases[pos] = new_alias
                    break
            for pos, alias in enumerate(self.tables):
                if alias == old_alias:
                    self.tables[pos] = new_alias
                    break

        # 3. Update any joins that refer to the old alias.
        for alias, data in self.alias_map.iteritems():
            lhs = data[LHS_ALIAS]
            if lhs in change_map:
                data = list(data)
                data[LHS_ALIAS] = change_map[lhs]
                self.alias_map[alias] = tuple(data)

    def bump_prefix(self, exceptions=()):
        """
        Changes the alias prefix to the next letter in the alphabet and
        relabels all the aliases. Even tables that previously had no alias will
        get an alias after this call (it's mostly used for nested queries and
        the outer query will already be using the non-aliased table name).

        Subclasses who create their own prefix should override this method to
        produce a similar result (a new prefix and relabelled aliases).

        The 'exceptions' parameter is a container that holds alias names which
        should not be changed.
        """
        assert ord(self.alias_prefix) < ord('Z')
        self.alias_prefix = chr(ord(self.alias_prefix) + 1)
        change_map = {}
        prefix = self.alias_prefix
        for pos, alias in enumerate(self.tables):
            if alias in exceptions:
                continue
            new_alias = '%s%d' % (prefix, pos)
            change_map[alias] = new_alias
            self.tables[pos] = new_alias
        self.change_aliases(change_map)

    def get_initial_alias(self):
        """
        Returns the first alias for this query, after increasing its reference
        count.
        """
        if self.tables:
            alias = self.tables[0]
            self.ref_alias(alias)
        else:
            alias = self.join((None, self.model._meta.db_table, None, None))
        return alias

    def count_active_tables(self):
        """
        Returns the number of tables in this query with a non-zero reference
        count.
        """
        return len([1 for count in self.alias_refcount.itervalues() if count])

    def join(self, connection, always_create=False, exclusions=(),
            promote=False, outer_if_first=False, nullable=False, reuse=None):
        """
        Returns an alias for the join in 'connection', either reusing an
        existing alias for that join or creating a new one. 'connection' is a
        tuple (lhs, table, lhs_col, col) where 'lhs' is either an existing
        table alias or a table name. The join correspods to the SQL equivalent
        of::

            lhs.lhs_col = table.col

        If 'always_create' is True and 'reuse' is None, a new alias is always
        created, regardless of whether one already exists or not. Otherwise
        'reuse' must be a set and a new join is created unless one of the
        aliases in `reuse` can be used.

        If 'exclusions' is specified, it is something satisfying the container
        protocol ("foo in exclusions" must work) and specifies a list of
        aliases that should not be returned, even if they satisfy the join.

        If 'promote' is True, the join type for the alias will be LOUTER (if
        the alias previously existed, the join type will be promoted from INNER
        to LOUTER, if necessary).

        If 'outer_if_first' is True and a new join is created, it will have the
        LOUTER join type. This is used when joining certain types of querysets
        and Q-objects together.

        If 'nullable' is True, the join can potentially involve NULL values and
        is a candidate for promotion (to "left outer") when combining querysets.
        """
        lhs, table, lhs_col, col = connection
        if lhs in self.alias_map:
            lhs_table = self.alias_map[lhs][TABLE_NAME]
        else:
            lhs_table = lhs

        if reuse and always_create and table in self.table_map:
            # Convert the 'reuse' to case to be "exclude everything but the
            # reusable set for this table".
            exclusions = set(self.table_map[table]).difference(reuse)
            always_create = False
        t_ident = (lhs_table, table, lhs_col, col)
        if not always_create:
            for alias in self.join_map.get(t_ident, ()):
                if alias not in exclusions:
                    self.ref_alias(alias)
                    if promote:
                        self.promote_alias(alias)
                    return alias

        # No reuse is possible, so we need a new alias.
        alias, _ = self.table_alias(table, True)
        if not lhs:
            # Not all tables need to be joined to anything. No join type
            # means the later columns are ignored.
            join_type = None
        elif promote or outer_if_first:
            join_type = self.LOUTER
        else:
            join_type = self.INNER
        join = (table, alias, join_type, lhs, lhs_col, col, nullable)
        self.alias_map[alias] = join
        if t_ident in self.join_map:
            self.join_map[t_ident] += (alias,)
        else:
            self.join_map[t_ident] = (alias,)
        self.rev_join_map[alias] = t_ident
        return alias

    def fill_related_selections(self, opts=None, root_alias=None, cur_depth=1,
            used=None, requested=None, restricted=None):
        """
        Fill in the information needed for a select_related query. The current
        depth is measured as the number of connections away from the root model
        (for example, cur_depth=1 means we are looking at models with direct
        connections to the root model).
        """
        if not restricted and self.max_depth and cur_depth > self.max_depth:
            # We've recursed far enough; bail out.
            return
        if not opts:
            opts = self.get_meta()
            root_alias = self.get_initial_alias()
            self.related_select_cols = []
            self.related_select_fields = []
        if not used:
            used = set()

        # Setup for the case when only particular related fields should be
        # included in the related selection.
        if requested is None and restricted is not False:
            if isinstance(self.select_related, dict):
                requested = self.select_related
                restricted = True
            else:
                restricted = False

        for f, model in opts.get_fields_with_model():
            if (not f.rel or (restricted and f.name not in requested) or
                    (not restricted and f.null) or f.rel.parent_link):
                continue
            table = f.rel.to._meta.db_table
            if model:
                int_opts = opts
                alias = root_alias
                for int_model in opts.get_base_chain(model):
                    lhs_col = int_opts.parents[int_model].column
                    int_opts = int_model._meta
                    alias = self.join((alias, int_opts.db_table, lhs_col,
                            int_opts.pk.column), exclusions=used,
                            promote=f.null)
            else:
                alias = root_alias
            alias = self.join((alias, table, f.column,
                    f.rel.get_related_field().column), exclusions=used,
                    promote=f.null)
            used.add(alias)
            self.related_select_cols.extend([(alias, f2.column)
                    for f2 in f.rel.to._meta.fields])
            self.related_select_fields.extend(f.rel.to._meta.fields)
            if restricted:
                next = requested.get(f.name, {})
            else:
                next = False
            self.fill_related_selections(f.rel.to._meta, alias, cur_depth + 1,
                    used, next, restricted)

    def add_filter(self, filter_expr, connector=AND, negate=False, trim=False,
            can_reuse=None):
        """
        Add a single filter to the query. The 'filter_expr' is a pair:
        (filter_string, value). E.g. ('name__contains', 'fred')

        If 'negate' is True, this is an exclude() filter. It's important to
        note that this method does not negate anything in the where-clause
        object when inserting the filter constraints. This is because negated
        filters often require multiple calls to add_filter() and the negation
        should only happen once. So the caller is responsible for this (the
        caller will normally be add_q(), so that as an example).

        If 'trim' is True, we automatically trim the final join group (used
        internally when constructing nested queries).

        If 'can_reuse' is a set, we are processing a component of a
        multi-component filter (e.g. filter(Q1, Q2)). In this case, 'can_reuse'
        will be a set of table aliases that can be reused in this filter, even
        if we would otherwise force the creation of new aliases for a join
        (needed for nested Q-filters). The set is updated by this method.
        """
        arg, value = filter_expr
        parts = arg.split(LOOKUP_SEP)
        if not parts:
            raise FieldError("Cannot parse keyword query %r" % arg)

        # Work out the lookup type and remove it from 'parts', if necessary.
        if len(parts) == 1 or parts[-1] not in self.query_terms:
            lookup_type = 'exact'
        else:
            lookup_type = parts.pop()

        # Interpret '__exact=None' as the sql 'is NULL'; otherwise, reject all
        # uses of None as a query value.
        if value is None:
            if lookup_type != 'exact':
                raise ValueError("Cannot use None as a query value")
            lookup_type = 'isnull'
            value = True
        elif callable(value):
            value = value()

        opts = self.get_meta()
        alias = self.get_initial_alias()
        allow_many = trim or not negate

        try:
            field, target, opts, join_list, last = self.setup_joins(parts, opts,
                    alias, True, allow_many, can_reuse=can_reuse)
        except MultiJoin, e:
            self.split_exclude(filter_expr, LOOKUP_SEP.join(parts[:e.level]))
            return
        final = len(join_list)
        penultimate = last.pop()
        if penultimate == final:
            penultimate = last.pop()
        if trim and len(join_list) > 1:
            extra = join_list[penultimate:]
            join_list = join_list[:penultimate]
            final = penultimate
            penultimate = last.pop()
            col = self.alias_map[extra[0]][LHS_JOIN_COL]
            for alias in extra:
                self.unref_alias(alias)
        else:
            col = target.column
        alias = join_list[-1]

        if final > 1:
            # An optimization: if the final join is against the same column as
            # we are comparing against, we can go back one step in the join
            # chain and compare against the lhs of the join instead. The result
            # (potentially) involves one less table join.
            join = self.alias_map[alias]
            if col == join[RHS_JOIN_COL]:
                self.unref_alias(alias)
                alias = join[LHS_ALIAS]
                col = join[LHS_JOIN_COL]
                join_list = join_list[:-1]
                final -= 1
                if final == penultimate:
                    penultimate = last.pop()

        if (lookup_type == 'isnull' and value is True and not negate and
                final > 1):
            # If the comparison is against NULL, we need to use a left outer
            # join when connecting to the previous model. We make that
            # adjustment here. We don't do this unless needed as it's less
            # efficient at the database level.
            self.promote_alias(join_list[penultimate])

        if connector == OR:
            # Some joins may need to be promoted when adding a new filter to a
            # disjunction. We walk the list of new joins and where it diverges
            # from any previous joins (ref count is 1 in the table list), we
            # make the new additions (and any existing ones not used in the new
            # join list) an outer join.
            join_it = iter(join_list)
            table_it = iter(self.tables)
            join_it.next(), table_it.next()
            for join in join_it:
                table = table_it.next()
                if join == table and self.alias_refcount[join] > 1:
                    continue
                self.promote_alias(join)
                if table != join:
                    self.promote_alias(table)
                break
            for join in join_it:
                self.promote_alias(join)
            for table in table_it:
                # Some of these will have been promoted from the join_list, but
                # that's harmless.
                self.promote_alias(table)

        self.where.add((alias, col, field, lookup_type, value), connector)
        if negate:
            for alias in join_list:
                self.promote_alias(alias)
            if final > 1 and lookup_type != 'isnull':
                for alias in join_list:
                    if self.alias_map[alias] == self.LOUTER:
                        j_col = self.alias_map[alias][RHS_JOIN_COL]
                        entry = Node([(alias, j_col, None, 'isnull', True)])
                        entry.negate()
                        self.where.add(entry, AND)
                        break
        if can_reuse is not None:
            can_reuse.update(join_list)

    def add_q(self, q_object, used_aliases=None):
        """
        Adds a Q-object to the current filter.

        Can also be used to add anything that has an 'add_to_query()' method.
        """
        if used_aliases is None:
            used_aliases = set()
        if hasattr(q_object, 'add_to_query'):
            # Complex custom objects are responsible for adding themselves.
            q_object.add_to_query(self, used_aliases)
            return

        if self.where and q_object.connector != AND and len(q_object) > 1:
            self.where.start_subtree(AND)
            subtree = True
        else:
            subtree = False
        connector = AND
        for child in q_object.children:
            if isinstance(child, Node):
                self.where.start_subtree(connector)
                self.add_q(child, used_aliases)
                self.where.end_subtree()
            else:
                self.add_filter(child, connector, q_object.negated,
                        can_reuse=used_aliases)
            connector = q_object.connector
        if q_object.negated:
            self.where.negate()
        if subtree:
            self.where.end_subtree()

    def setup_joins(self, names, opts, alias, dupe_multis, allow_many=True,
            allow_explicit_fk=False, can_reuse=None):
        """
        Compute the necessary table joins for the passage through the fields
        given in 'names'. 'opts' is the Options class for the current model
        (which gives the table we are joining to), 'alias' is the alias for the
        table we are joining to. If dupe_multis is True, any many-to-many or
        many-to-one joins will always create a new alias (necessary for
        disjunctive filters).

        Returns the final field involved in the join, the target database
        column (used for any 'where' constraint), the final 'opts' value and the
        list of tables joined.
        """
        joins = [alias]
        last = [0]
        for pos, name in enumerate(names):
            last.append(len(joins))
            if name == 'pk':
                name = opts.pk.name

            try:
                field, model, direct, m2m = opts.get_field_by_name(name)
            except FieldDoesNotExist:
                for f in opts.fields:
                    if allow_explicit_fk and name == f.attname:
                        # XXX: A hack to allow foo_id to work in values() for
                        # backwards compatibility purposes. If we dropped that
                        # feature, this could be removed.
                        field, model, direct, m2m = opts.get_field_by_name(f.name)
                        break
                else:
                    names = opts.get_all_field_names()
                    raise FieldError("Cannot resolve keyword %r into field. "
                            "Choices are: %s" % (name, ", ".join(names)))
            if not allow_many and (m2m or not direct):
                for alias in joins:
                    self.unref_alias(alias)
                raise MultiJoin(pos + 1)
            if model:
                # The field lives on a base class of the current model.
                alias_list = []
                for int_model in opts.get_base_chain(model):
                    lhs_col = opts.parents[int_model].column
                    opts = int_model._meta
                    alias = self.join((alias, opts.db_table, lhs_col,
                            opts.pk.column), exclusions=joins)
                    joins.append(alias)
            cached_data = opts._join_cache.get(name)
            orig_opts = opts

            if direct:
                if m2m:
                    # Many-to-many field defined on the current model.
                    if cached_data:
                        (table1, from_col1, to_col1, table2, from_col2,
                                to_col2, opts, target) = cached_data
                    else:
                        table1 = field.m2m_db_table()
                        from_col1 = opts.pk.column
                        to_col1 = field.m2m_column_name()
                        opts = field.rel.to._meta
                        table2 = opts.db_table
                        from_col2 = field.m2m_reverse_name()
                        to_col2 = opts.pk.column
                        target = opts.pk
                        orig_opts._join_cache[name] = (table1, from_col1,
                                to_col1, table2, from_col2, to_col2, opts,
                                target)

                    int_alias = self.join((alias, table1, from_col1, to_col1),
                            dupe_multis, joins, nullable=True, reuse=can_reuse)
                    alias = self.join((int_alias, table2, from_col2, to_col2),
                            dupe_multis, joins, nullable=True, reuse=can_reuse)
                    joins.extend([int_alias, alias])
                elif field.rel:
                    # One-to-one or many-to-one field
                    if cached_data:
                        (table, from_col, to_col, opts, target) = cached_data
                    else:
                        opts = field.rel.to._meta
                        target = field.rel.get_related_field()
                        table = opts.db_table
                        from_col = field.column
                        to_col = target.column
                        orig_opts._join_cache[name] = (table, from_col, to_col,
                                opts, target)

                    alias = self.join((alias, table, from_col, to_col),
                            exclusions=joins, nullable=field.null)
                    joins.append(alias)
                else:
                    # Non-relation fields.
                    target = field
                    break
            else:
                orig_field = field
                field = field.field
                if m2m:
                    # Many-to-many field defined on the target model.
                    if cached_data:
                        (table1, from_col1, to_col1, table2, from_col2,
                                to_col2, opts, target) = cached_data
                    else:
                        table1 = field.m2m_db_table()
                        from_col1 = opts.pk.column
                        to_col1 = field.m2m_reverse_name()
                        opts = orig_field.opts
                        table2 = opts.db_table
                        from_col2 = field.m2m_column_name()
                        to_col2 = opts.pk.column
                        target = opts.pk
                        orig_opts._join_cache[name] = (table1, from_col1,
                                to_col1, table2, from_col2, to_col2, opts,
                                target)

                    int_alias = self.join((alias, table1, from_col1, to_col1),
                            dupe_multis, joins, nullable=True, reuse=can_reuse)
                    alias = self.join((int_alias, table2, from_col2, to_col2),
                            dupe_multis, joins, nullable=True, reuse=can_reuse)
                    joins.extend([int_alias, alias])
                else:
                    # One-to-many field (ForeignKey defined on the target model)
                    if cached_data:
                        (table, from_col, to_col, opts, target) = cached_data
                    else:
                        local_field = opts.get_field_by_name(
                                field.rel.field_name)[0]
                        opts = orig_field.opts
                        table = opts.db_table
                        from_col = local_field.column
                        to_col = field.column
                        target = opts.pk
                        orig_opts._join_cache[name] = (table, from_col, to_col,
                                opts, target)

                    alias = self.join((alias, table, from_col, to_col),
                            dupe_multis, joins, nullable=True, reuse=can_reuse)
                    joins.append(alias)

        if pos != len(names) - 1:
            raise FieldError("Join on field %r not permitted." % name)

        return field, target, opts, joins, last

    def split_exclude(self, filter_expr, prefix):
        """
        When doing an exclude against any kind of N-to-many relation, we need
        to use a subquery. This method constructs the nested query, given the
        original exclude filter (filter_expr) and the portion up to the first
        N-to-many relation field.
        """
        query = Query(self.model, self.connection)
        query.add_filter(filter_expr)
        query.set_start(prefix)
        query.clear_ordering(True)
        self.add_filter(('%s__in' % prefix, query), negate=True, trim=True)

    def set_limits(self, low=None, high=None):
        """
        Adjusts the limits on the rows retrieved. We use low/high to set these,
        as it makes it more Pythonic to read and write. When the SQL query is
        created, they are converted to the appropriate offset and limit values.

        Any limits passed in here are applied relative to the existing
        constraints. So low is added to the current low value and both will be
        clamped to any existing high value.
        """
        if high:
            if self.high_mark:
                self.high_mark = min(self.high_mark, self.low_mark + high)
            else:
                self.high_mark = self.low_mark + high
        if low:
            if self.high_mark:
                self.low_mark = min(self.high_mark, self.low_mark + low)
            else:
                self.low_mark = self.low_mark + low

    def clear_limits(self):
        """
        Clears any existing limits.
        """
        self.low_mark, self.high_mark = 0, None

    def can_filter(self):
        """
        Returns True if adding filters to this instance is still possible.

        Typically, this means no limits or offsets have been put on the results.
        """
        return not (self.low_mark or self.high_mark)

    def add_fields(self, field_names, allow_m2m=True):
        """
        Adds the given (model) fields to the select set. The field names are
        added in the order specified.
        """
        alias = self.get_initial_alias()
        opts = self.get_meta()
        try:
            for name in field_names:
                field, target, u2, joins, u3 = self.setup_joins(
                        name.split(LOOKUP_SEP), opts, alias, False, allow_m2m,
                        True)
                final_alias = joins[-1]
                col = target.column
                if len(joins) > 1:
                    join = self.alias_map[final_alias]
                    if col == join[RHS_JOIN_COL]:
                        self.unref_alias(final_alias)
                        final_alias = join[LHS_ALIAS]
                        col = join[LHS_JOIN_COL]
                        joins = joins[:-1]
                for join in joins[1:]:
                    # Only nullable aliases are promoted, so we don't end up
                    # doing unnecessary left outer joins here.
                    self.promote_alias(join)
                self.select.append((final_alias, col))
                self.select_fields.append(field)
        except MultiJoin:
            raise FieldError("Invalid field name: '%s'" % name)
        except FieldError:
            names = opts.get_all_field_names() + self.extra_select.keys()
            names.sort()
            raise FieldError("Cannot resolve keyword %r into field. "
                    "Choices are: %s" % (name, ", ".join(names)))

    def add_ordering(self, *ordering):
        """
        Adds items from the 'ordering' sequence to the query's "order by"
        clause. These items are either field names (not column names) --
        possibly with a direction prefix ('-' or '?') -- or ordinals,
        corresponding to column positions in the 'select' list.

        If 'ordering' is empty, all ordering is cleared from the query.
        """
        errors = []
        for item in ordering:
            if not ORDER_PATTERN.match(item):
                errors.append(item)
        if errors:
            raise FieldError('Invalid order_by arguments: %s' % errors)
        if ordering:
            self.order_by.extend(ordering)
        else:
            self.default_ordering = False

    def clear_ordering(self, force_empty=False):
        """
        Removes any ordering settings. If 'force_empty' is True, there will be
        no ordering in the resulting query (not even the model's default).
        """
        self.order_by = []
        self.extra_order_by = ()
        if force_empty:
            self.default_ordering = False

    def add_count_column(self):
        """
        Converts the query to do count(...) or count(distinct(pk)) in order to
        get its size.
        """
        # TODO: When group_by support is added, this needs to be adjusted so
        # that it doesn't totally overwrite the select list.
        if not self.distinct:
            if not self.select:
                select = Count()
            else:
                assert len(self.select) == 1, \
                        "Cannot add count col with multiple cols in 'select': %r" % self.select
                select = Count(self.select[0])
        else:
            opts = self.model._meta
            if not self.select:
                select = Count((self.join((None, opts.db_table, None, None)),
                        opts.pk.column), True)
            else:
                # Because of SQL portability issues, multi-column, distinct
                # counts need a sub-query -- see get_count() for details.
                assert len(self.select) == 1, \
                        "Cannot add count col with multiple cols in 'select'."
                select = Count(self.select[0], True)

            # Distinct handling is done in Count(), so don't do it at this
            # level.
            self.distinct = False
        self.select = [select]
        self.select_fields = [None]
        self.extra_select = {}
        self.extra_select_params = ()

    def add_select_related(self, fields):
        """
        Sets up the select_related data structure so that we only select
        certain related models (as opposed to all models, when
        self.select_related=True).
        """
        field_dict = {}
        for field in fields:
            d = field_dict
            for part in field.split(LOOKUP_SEP):
                d = d.setdefault(part, {})
        self.select_related = field_dict
        self.related_select_cols = []
        self.related_select_fields = []

    def add_extra(self, select, select_params, where, params, tables, order_by):
        """
        Adds data to the various extra_* attributes for user-created additions
        to the query.
        """
        if select:
            # The extra select might be ordered (because it will be accepting
            # parameters).
            if (isinstance(select, SortedDict) and
                    not isinstance(self.extra_select, SortedDict)):
                self.extra_select = SortedDict(self.extra_select)
            self.extra_select.update(select)
        if select_params:
            self.extra_select_params += tuple(select_params)
        if where:
            self.extra_where += tuple(where)
        if params:
            self.extra_params += tuple(params)
        if tables:
            self.extra_tables += tuple(tables)
        if order_by:
            self.extra_order_by = order_by

    def trim_extra_select(self, names):
        """
        Removes any aliases in the extra_select dictionary that aren't in
        'names'.

        This is needed if we are selecting certain values that don't incldue
        all of the extra_select names.
        """
        for key in set(self.extra_select).difference(set(names)):
            del self.extra_select[key]

    def set_start(self, start):
        """
        Sets the table from which to start joining. The start position is
        specified by the related attribute from the base model. This will
        automatically set to the select column to be the column linked from the
        previous table.

        This method is primarily for internal use and the error checking isn't
        as friendly as add_filter(). Mostly useful for querying directly
        against the join table of many-to-many relation in a subquery.
        """
        opts = self.model._meta
        alias = self.get_initial_alias()
        field, col, opts, joins, last = self.setup_joins(
                start.split(LOOKUP_SEP), opts, alias, False)
        alias = joins[last[-1]]
        self.select = [(alias, self.alias_map[alias][RHS_JOIN_COL])]
        self.select_fields = [field]
        self.start_meta = opts

        # The call to setup_joins add an extra reference to everything in
        # joins. So we need to unref everything once, and everything prior to
        # the final join a second time.
        for alias in joins:
            self.unref_alias(alias)
        for alias in joins[:last[-1]]:
            self.unref_alias(alias)

    def execute_sql(self, result_type=MULTI):
        """
        Run the query against the database and returns the result(s). The
        return value is a single data item if result_type is SINGLE, or an
        iterator over the results if the result_type is MULTI.

        result_type is either MULTI (use fetchmany() to retrieve all rows),
        SINGLE (only retrieve a single row), or None (no results expected, but
        the cursor is returned, since it's used by subclasses such as
        InsertQuery).
        """
        try:
            sql, params = self.as_sql()
            if not sql:
                raise EmptyResultSet
        except EmptyResultSet:
            if result_type == MULTI:
                return empty_iter()
            else:
                return

        cursor = self.connection.cursor()
        cursor.execute(sql, params)

        if not result_type:
            return cursor
        if result_type == SINGLE:
            if self.ordering_aliases:
                return cursor.fetchone()[:-len(results.ordering_aliases)]
            return cursor.fetchone()

        # The MULTI case.
        if self.ordering_aliases:
            return order_modified_iter(cursor, len(self.ordering_aliases),
                    self.connection.features.empty_fetchmany_value)
        return iter((lambda: cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE)),
                self.connection.features.empty_fetchmany_value)

# Use the backend's custom Query class if it defines one. Otherwise, use the
# default.
if connection.features.uses_custom_query_class:
    Query = connection.ops.query_class(Query)

def get_order_dir(field, default='ASC'):
    """
    Returns the field name and direction for an order specification. For
    example, '-foo' is returned as ('foo', 'DESC').

    The 'default' param is used to indicate which way no prefix (or a '+'
    prefix) should sort. The '-' prefix always sorts the opposite way.
    """
    dirn = ORDER_DIR[default]
    if field[0] == '-':
        return field[1:], dirn[1]
    return field, dirn[0]

def empty_iter():
    """
    Returns an iterator containing no results.
    """
    yield iter([]).next()

def order_modified_iter(cursor, trim, sentinel):
    """
    Yields blocks of rows from a cursor. We use this iterator in the special
    case when extra output columns have been added to support ordering
    requirements. We must trim those extra columns before anything else can use
    the results, since they're only needed to make the SQL valid.
    """
    for rows in iter((lambda: cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE)),
            sentinel):
        yield [r[:-trim] for r in rows]

def setup_join_cache(sender):
    """
    The information needed to join between model fields is something that is
    invariant over the life of the model, so we cache it in the model's Options
    class, rather than recomputing it all the time.

    This method initialises the (empty) cache when the model is created.
    """
    sender._meta._join_cache = {}

dispatcher.connect(setup_join_cache, signal=signals.class_prepared)

