from django.core.management.base import CommandError
import os
import re

try:
    set
except NameError:
    from sets import Set as set   # Python 2.3 fallback

def table_list():
    "Returns a list of all table names that exist in the database."
    from django.db import connection, get_introspection_module
    cursor = connection.cursor()
    return get_introspection_module().get_table_list(cursor)

def installed_models(table_list):
    "Returns a set of all models that are installed, given a list of existing table names."
    from django.db import backend, models
    all_models = []
    for app in models.get_apps():
        for model in models.get_models(app):
            all_models.append(model)
    if backend.uses_case_insensitive_names:
        converter = lambda x: x.upper()
    else:
        converter = lambda x: x
    return set([m for m in all_models if converter(m._meta.db_table) in map(converter, table_list)])

def sequence_list():
    "Returns a list of information about all DB sequences for all models in all apps."
    from django.db import models

    apps = models.get_apps()
    sequence_list = []

    for app in apps:
        for model in models.get_models(app):
            for f in model._meta.fields:
                if isinstance(f, models.AutoField):
                    sequence_list.append({'table': model._meta.db_table, 'column': f.column})
                    break # Only one AutoField is allowed per model, so don't bother continuing.

            for f in model._meta.many_to_many:
                sequence_list.append({'table': f.m2m_db_table(), 'column': None})

    return sequence_list

def sql_create(app, style):
    "Returns a list of the CREATE TABLE SQL statements for the given app."
    from django.db import models
    from django.conf import settings

    if settings.DATABASE_ENGINE == 'dummy':
        # This must be the "dummy" database backend, which means the user
        # hasn't set DATABASE_ENGINE.
        raise CommandError("Django doesn't know which syntax to use for your SQL statements,\n" +
            "because you haven't specified the DATABASE_ENGINE setting.\n" +
            "Edit your settings file and change DATABASE_ENGINE to something like 'postgresql' or 'mysql'.")

    # Get installed models, so we generate REFERENCES right.
    # We trim models from the current app so that the sqlreset command does not
    # generate invalid SQL (leaving models out of known_models is harmless, so
    # we can be conservative).
    app_models = models.get_models(app)
    final_output = []
    known_models = set([model for model in installed_models(table_list()) if model not in app_models])
    pending_references = {}

    for model in app_models:
        output, references = sql_model_create(model, style, known_models)
        final_output.extend(output)
        for refto, refs in references.items():
            pending_references.setdefault(refto, []).extend(refs)
        final_output.extend(sql_for_pending_references(model, style, pending_references))
        # Keep track of the fact that we've created the table for this model.
        known_models.add(model)

    # Create the many-to-many join tables.
    for model in app_models:
        final_output.extend(many_to_many_sql_for_model(model, style))

    # Handle references to tables that are from other apps
    # but don't exist physically.
    not_installed_models = set(pending_references.keys())
    if not_installed_models:
        alter_sql = []
        for model in not_installed_models:
            alter_sql.extend(['-- ' + sql for sql in
                sql_for_pending_references(model, style, pending_references)])
        if alter_sql:
            final_output.append('-- The following references should be added but depend on non-existent tables:')
            final_output.extend(alter_sql)

    return final_output

def sql_delete(app, style):
    "Returns a list of the DROP TABLE SQL statements for the given app."
    from django.db import backend, connection, models, get_introspection_module
    from django.db.backends.util import truncate_name
    introspection = get_introspection_module()

    # This should work even if a connection isn't available
    try:
        cursor = connection.cursor()
    except:
        cursor = None

    # Figure out which tables already exist
    if cursor:
        table_names = introspection.get_table_list(cursor)
    else:
        table_names = []
    if backend.uses_case_insensitive_names:
        table_name_converter = str.upper
    else:
        table_name_converter = lambda x: x

    output = []

    # Output DROP TABLE statements for standard application tables.
    to_delete = set()

    references_to_delete = {}
    app_models = models.get_models(app)
    for model in app_models:
        if cursor and table_name_converter(model._meta.db_table) in table_names:
            # The table exists, so it needs to be dropped
            opts = model._meta
            for f in opts.fields:
                if f.rel and f.rel.to not in to_delete:
                    references_to_delete.setdefault(f.rel.to, []).append( (model, f) )

            to_delete.add(model)

    for model in app_models:
        if cursor and table_name_converter(model._meta.db_table) in table_names:
            # Drop the table now
            output.append('%s %s;' % (style.SQL_KEYWORD('DROP TABLE'),
                style.SQL_TABLE(backend.quote_name(model._meta.db_table))))
            if backend.supports_constraints and model in references_to_delete:
                for rel_class, f in references_to_delete[model]:
                    table = rel_class._meta.db_table
                    col = f.column
                    r_table = model._meta.db_table
                    r_col = model._meta.get_field(f.rel.field_name).column
                    r_name = '%s_refs_%s_%x' % (col, r_col, abs(hash((table, r_table))))
                    output.append('%s %s %s %s;' % \
                        (style.SQL_KEYWORD('ALTER TABLE'),
                        style.SQL_TABLE(backend.quote_name(table)),
                        style.SQL_KEYWORD(backend.get_drop_foreignkey_sql()),
                        style.SQL_FIELD(truncate_name(r_name, backend.get_max_name_length()))))
                del references_to_delete[model]
            if model._meta.has_auto_field and hasattr(backend, 'get_drop_sequence'):
                output.append(backend.get_drop_sequence(model._meta.db_table))

    # Output DROP TABLE statements for many-to-many tables.
    for model in app_models:
        opts = model._meta
        for f in opts.many_to_many:
            if cursor and table_name_converter(f.m2m_db_table()) in table_names:
                output.append("%s %s;" % (style.SQL_KEYWORD('DROP TABLE'),
                    style.SQL_TABLE(backend.quote_name(f.m2m_db_table()))))
                if hasattr(backend, 'get_drop_sequence'):
                    output.append(backend.get_drop_sequence("%s_%s" % (model._meta.db_table, f.column)))

    app_label = app_models[0]._meta.app_label

    # Close database connection explicitly, in case this output is being piped
    # directly into a database client, to avoid locking issues.
    if cursor:
        cursor.close()
        connection.close()

    return output[::-1] # Reverse it, to deal with table dependencies.

def sql_reset(app, style):
    "Returns a list of the DROP TABLE SQL, then the CREATE TABLE SQL, for the given module."
    return sql_delete(app, style) + sql_all(app, style)

def sql_flush(style):
    "Returns a list of the SQL statements used to flush the database"
    from django.db import backend
    statements = backend.get_sql_flush(style, table_list(), sequence_list())
    return statements

def sql_custom(app):
    "Returns a list of the custom table modifying SQL statements for the given app."
    from django.db.models import get_models
    output = []

    app_models = get_models(app)
    app_dir = os.path.normpath(os.path.join(os.path.dirname(app.__file__), 'sql'))

    for model in app_models:
        output.extend(custom_sql_for_model(model))

    return output

def sql_indexes(app, style):
    "Returns a list of the CREATE INDEX SQL statements for all models in the given app."
    from django.db import models
    output = []
    for model in models.get_models(app):
        output.extend(sql_indexes_for_model(model, style))
    return output

def sql_all(app, style):
    "Returns a list of CREATE TABLE SQL, initial-data inserts, and CREATE INDEX SQL for the given module."
    return sql_create(app, style) + sql_custom(app) + sql_indexes(app, style)

def sql_model_create(model, style, known_models=set()):
    """
    Returns the SQL required to create a single model, as a tuple of:
        (list_of_sql, pending_references_dict)
    """
    from django.db import backend, connection, models

    opts = model._meta
    final_output = []
    table_output = []
    pending_references = {}
    for f in opts.fields:
        col_type = f.db_type()
        tablespace = f.db_tablespace or opts.db_tablespace
        if col_type is None:
            # Skip ManyToManyFields, because they're not represented as
            # database columns in this table.
            continue
        # Make the definition (e.g. 'foo VARCHAR(30)') for this field.
        field_output = [style.SQL_FIELD(backend.quote_name(f.column)),
            style.SQL_COLTYPE(col_type)]
        field_output.append(style.SQL_KEYWORD('%sNULL' % (not f.null and 'NOT ' or '')))
        if f.unique and (not f.primary_key or backend.allows_unique_and_pk):
            field_output.append(style.SQL_KEYWORD('UNIQUE'))
        if f.primary_key:
            field_output.append(style.SQL_KEYWORD('PRIMARY KEY'))
        if tablespace and backend.supports_tablespaces and (f.unique or f.primary_key) and backend.autoindexes_primary_keys:
            # We must specify the index tablespace inline, because we
            # won't be generating a CREATE INDEX statement for this field.
            field_output.append(backend.get_tablespace_sql(tablespace, inline=True))
        if f.rel:
            if f.rel.to in known_models:
                field_output.append(style.SQL_KEYWORD('REFERENCES') + ' ' + \
                    style.SQL_TABLE(backend.quote_name(f.rel.to._meta.db_table)) + ' (' + \
                    style.SQL_FIELD(backend.quote_name(f.rel.to._meta.get_field(f.rel.field_name).column)) + ')' +
                    backend.get_deferrable_sql()
                )
            else:
                # We haven't yet created the table to which this field
                # is related, so save it for later.
                pr = pending_references.setdefault(f.rel.to, []).append((model, f))
        table_output.append(' '.join(field_output))
    if opts.order_with_respect_to:
        table_output.append(style.SQL_FIELD(backend.quote_name('_order')) + ' ' + \
            style.SQL_COLTYPE(models.IntegerField().db_type()) + ' ' + \
            style.SQL_KEYWORD('NULL'))
    for field_constraints in opts.unique_together:
        table_output.append(style.SQL_KEYWORD('UNIQUE') + ' (%s)' % \
            ", ".join([backend.quote_name(style.SQL_FIELD(opts.get_field(f).column)) for f in field_constraints]))

    full_statement = [style.SQL_KEYWORD('CREATE TABLE') + ' ' + style.SQL_TABLE(backend.quote_name(opts.db_table)) + ' (']
    for i, line in enumerate(table_output): # Combine and add commas.
        full_statement.append('    %s%s' % (line, i < len(table_output)-1 and ',' or ''))
    full_statement.append(')')
    if opts.db_tablespace and backend.supports_tablespaces:
        full_statement.append(backend.get_tablespace_sql(opts.db_tablespace))
    full_statement.append(';')
    final_output.append('\n'.join(full_statement))

    if opts.has_auto_field:
        # Add any extra SQL needed to support auto-incrementing primary keys.
        autoinc_sql = connection.ops.autoinc_sql(opts.db_table)
        if autoinc_sql:
            for stmt in autoinc_sql:
                final_output.append(stmt)

    return final_output, pending_references

def sql_for_pending_references(model, style, pending_references):
    """
    Returns any ALTER TABLE statements to add constraints after the fact.
    """
    from django.db import backend
    from django.db.backends.util import truncate_name

    final_output = []
    if backend.supports_constraints:
        opts = model._meta
        if model in pending_references:
            for rel_class, f in pending_references[model]:
                rel_opts = rel_class._meta
                r_table = rel_opts.db_table
                r_col = f.column
                table = opts.db_table
                col = opts.get_field(f.rel.field_name).column
                # For MySQL, r_name must be unique in the first 64 characters.
                # So we are careful with character usage here.
                r_name = '%s_refs_%s_%x' % (r_col, col, abs(hash((r_table, table))))
                final_output.append(style.SQL_KEYWORD('ALTER TABLE') + ' %s ADD CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s (%s)%s;' % \
                    (backend.quote_name(r_table), truncate_name(r_name, backend.get_max_name_length()),
                    backend.quote_name(r_col), backend.quote_name(table), backend.quote_name(col),
                    backend.get_deferrable_sql()))
            del pending_references[model]
    return final_output

def many_to_many_sql_for_model(model, style):
    from django.db import backend, models
    from django.contrib.contenttypes import generic

    opts = model._meta
    final_output = []
    for f in opts.many_to_many:
        if not isinstance(f.rel, generic.GenericRel):
            tablespace = f.db_tablespace or opts.db_tablespace
            if tablespace and backend.supports_tablespaces and backend.autoindexes_primary_keys:
                tablespace_sql = ' ' + backend.get_tablespace_sql(tablespace, inline=True)
            else:
                tablespace_sql = ''
            table_output = [style.SQL_KEYWORD('CREATE TABLE') + ' ' + \
                style.SQL_TABLE(backend.quote_name(f.m2m_db_table())) + ' (']
            table_output.append('    %s %s %s%s,' % \
                (style.SQL_FIELD(backend.quote_name('id')),
                style.SQL_COLTYPE(models.AutoField(primary_key=True).db_type()),
                style.SQL_KEYWORD('NOT NULL PRIMARY KEY'),
                tablespace_sql))
            table_output.append('    %s %s %s %s (%s)%s,' % \
                (style.SQL_FIELD(backend.quote_name(f.m2m_column_name())),
                style.SQL_COLTYPE(models.ForeignKey(model).db_type()),
                style.SQL_KEYWORD('NOT NULL REFERENCES'),
                style.SQL_TABLE(backend.quote_name(opts.db_table)),
                style.SQL_FIELD(backend.quote_name(opts.pk.column)),
                backend.get_deferrable_sql()))
            table_output.append('    %s %s %s %s (%s)%s,' % \
                (style.SQL_FIELD(backend.quote_name(f.m2m_reverse_name())),
                style.SQL_COLTYPE(models.ForeignKey(f.rel.to).db_type()),
                style.SQL_KEYWORD('NOT NULL REFERENCES'),
                style.SQL_TABLE(backend.quote_name(f.rel.to._meta.db_table)),
                style.SQL_FIELD(backend.quote_name(f.rel.to._meta.pk.column)),
                backend.get_deferrable_sql()))
            table_output.append('    %s (%s, %s)%s' % \
                (style.SQL_KEYWORD('UNIQUE'),
                style.SQL_FIELD(backend.quote_name(f.m2m_column_name())),
                style.SQL_FIELD(backend.quote_name(f.m2m_reverse_name())),
                tablespace_sql))
            table_output.append(')')
            if opts.db_tablespace and backend.supports_tablespaces:
                # f.db_tablespace is only for indices, so ignore its value here.
                table_output.append(backend.get_tablespace_sql(opts.db_tablespace))
            table_output.append(';')
            final_output.append('\n'.join(table_output))

            # Add any extra SQL needed to support auto-incrementing PKs
            autoinc_sql = backend.get_autoinc_sql(f.m2m_db_table())
            if autoinc_sql:
                for stmt in autoinc_sql:
                    final_output.append(stmt)

    return final_output

def custom_sql_for_model(model):
    from django.db import models
    from django.conf import settings

    opts = model._meta
    app_dir = os.path.normpath(os.path.join(os.path.dirname(models.get_app(model._meta.app_label).__file__), 'sql'))
    output = []

    # Some backends can't execute more than one SQL statement at a time,
    # so split into separate statements.
    statements = re.compile(r";[ \t]*$", re.M)

    # Find custom SQL, if it's available.
    sql_files = [os.path.join(app_dir, "%s.%s.sql" % (opts.object_name.lower(), settings.DATABASE_ENGINE)),
                 os.path.join(app_dir, "%s.sql" % opts.object_name.lower())]
    for sql_file in sql_files:
        if os.path.exists(sql_file):
            fp = open(sql_file, 'U')
            for statement in statements.split(fp.read().decode(settings.FILE_CHARSET)):
                # Remove any comments from the file
                statement = re.sub(ur"--.*[\n\Z]", "", statement)
                if statement.strip():
                    output.append(statement + u";")
            fp.close()

    return output

def sql_indexes_for_model(model, style):
    "Returns the CREATE INDEX SQL statements for a single model"
    from django.db import backend
    output = []

    for f in model._meta.fields:
        if f.db_index and not ((f.primary_key or f.unique) and backend.autoindexes_primary_keys):
            unique = f.unique and 'UNIQUE ' or ''
            tablespace = f.db_tablespace or model._meta.db_tablespace
            if tablespace and backend.supports_tablespaces:
                tablespace_sql = ' ' + backend.get_tablespace_sql(tablespace)
            else:
                tablespace_sql = ''
            output.append(
                style.SQL_KEYWORD('CREATE %sINDEX' % unique) + ' ' + \
                style.SQL_TABLE(backend.quote_name('%s_%s' % (model._meta.db_table, f.column))) + ' ' + \
                style.SQL_KEYWORD('ON') + ' ' + \
                style.SQL_TABLE(backend.quote_name(model._meta.db_table)) + ' ' + \
                "(%s)" % style.SQL_FIELD(backend.quote_name(f.column)) + \
                "%s;" % tablespace_sql
            )
    return output

def emit_post_sync_signal(created_models, verbosity, interactive):
    from django.db import models
    from django.dispatch import dispatcher
    # Emit the post_sync signal for every application.
    for app in models.get_apps():
        app_name = app.__name__.split('.')[-2]
        if verbosity >= 2:
            print "Running post-sync handlers for application", app_name
        dispatcher.send(signal=models.signals.post_syncdb, sender=app,
            app=app, created_models=created_models,
            verbosity=verbosity, interactive=interactive)
