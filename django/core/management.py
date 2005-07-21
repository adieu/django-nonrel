# Django management-related functions, including "CREATE TABLE" generation and
# development-server initialization.

import django
import os, re, sys

MODULE_TEMPLATE = '''    {%% if perms.%(app)s.%(addperm)s or perms.%(app)s.%(changeperm)s %%}
    <tr>
        <th>{%% if perms.%(app)s.%(changeperm)s %%}<a href="/%(app)s/%(mod)s/">{%% endif %%}%(name)s{%% if perms.%(app)s.%(changeperm)s %%}</a>{%% endif %%}</th>
        <td class="x50">{%% if perms.%(app)s.%(addperm)s %%}<a href="/%(app)s/%(mod)s/add/" class="addlink">{%% endif %%}Add{%% if perms.%(app)s.%(addperm)s %%}</a>{%% endif %%}</td>
        <td class="x75">{%% if perms.%(app)s.%(changeperm)s %%}<a href="/%(app)s/%(mod)s/" class="changelink">{%% endif %%}Change{%% if perms.%(app)s.%(changeperm)s %%}</a>{%% endif %%}</td>
    </tr>
    {%% endif %%}'''

APP_ARGS = '[app app ...]'

# Use django.__path__[0] because we don't know which directory django into
# which has been installed.
PROJECT_TEMPLATE_DIR = django.__path__[0] + '/conf/%s_template'
ADMIN_TEMPLATE_DIR = django.__path__[0] + '/conf/admin_templates'

def _get_packages_insert(app_label):
    return "INSERT INTO packages (label, name) VALUES ('%s', '%s');" % (app_label, app_label)

def _get_permission_codename(action, opts):
    return '%s_%s' % (action, opts.object_name.lower())

def _get_all_permissions(opts):
    "Returns (codename, name) for all permissions in the given opts."
    perms = []
    if opts.admin:
        for action in ('add', 'change', 'delete'):
            perms.append((_get_permission_codename(action, opts), 'Can %s %s' % (action, opts.verbose_name)))
    return perms + list(opts.permissions)

def _get_permission_insert(name, codename, opts):
    return "INSERT INTO auth_permissions (name, package, codename) VALUES ('%s', '%s', '%s');" % \
        (name.replace("'", "''"), opts.app_label, codename)

def _get_contenttype_insert(opts):
    return "INSERT INTO content_types (name, package, python_module_name) VALUES ('%s', '%s', '%s');" % \
        (opts.verbose_name, opts.app_label, opts.module_name)

def _is_valid_dir_name(s):
    return bool(re.search(r'^\w+$', s))

def get_sql_create(mod):
    "Returns a list of the CREATE TABLE SQL statements for the given module."
    from django.core import db, meta
    final_output = []
    for klass in mod._MODELS:
        opts = klass._meta
        table_output = []
        for f in opts.fields:
            if isinstance(f, meta.ForeignKey):
                rel_field = f.rel.get_related_field()
                # If the foreign key points to an AutoField, the foreign key
                # should be an IntegerField, not an AutoField. Otherwise, the
                # foreign key should be the same type of field as the field
                # to which it points.
                if rel_field.__class__.__name__ == 'AutoField':
                    data_type = 'IntegerField'
                else:
                    data_type = rel_field.__class__.__name__
            else:
                rel_field = f
                data_type = f.__class__.__name__
            col_type = db.DATA_TYPES[data_type]
            if col_type is not None:
                field_output = [f.name, col_type % rel_field.__dict__]
                field_output.append('%sNULL' % (not f.null and 'NOT ' or ''))
                if f.unique:
                    field_output.append('UNIQUE')
                if f.primary_key:
                    field_output.append('PRIMARY KEY')
                if f.rel:
                    field_output.append('REFERENCES %s (%s)' % \
                        (f.rel.to.db_table, f.rel.to.get_field(f.rel.field_name).name))
                table_output.append(' '.join(field_output))
        if opts.order_with_respect_to:
            table_output.append('_order %s NULL' % db.DATA_TYPES['IntegerField'])
        for field_constraints in opts.unique_together:
            table_output.append('UNIQUE (%s)' % ", ".join(field_constraints))

        full_statement = ['CREATE TABLE %s (' % opts.db_table]
        for i, line in enumerate(table_output): # Combine and add commas.
            full_statement.append('    %s%s' % (line, i < len(table_output)-1 and ',' or ''))
        full_statement.append(');')
        final_output.append('\n'.join(full_statement))

    for klass in mod._MODELS:
        opts = klass._meta
        for f in opts.many_to_many:
            table_output = ['CREATE TABLE %s (' % f.get_m2m_db_table(opts)]
            table_output.append('    id %s NOT NULL PRIMARY KEY,' % db.DATA_TYPES['AutoField'])
            table_output.append('    %s_id %s NOT NULL REFERENCES %s (%s),' % \
                (opts.object_name.lower(), db.DATA_TYPES['IntegerField'], opts.db_table, opts.pk.name))
            table_output.append('    %s_id %s NOT NULL REFERENCES %s (%s),' % \
                (f.rel.to.object_name.lower(), db.DATA_TYPES['IntegerField'], f.rel.to.db_table, f.rel.to.pk.name))
            table_output.append('    UNIQUE (%s_id, %s_id)' % (opts.object_name.lower(), f.rel.to.object_name.lower()))
            table_output.append(');')
            final_output.append('\n'.join(table_output))
    return final_output
get_sql_create.help_doc = "Prints the CREATE TABLE SQL statements for the given app(s)."
get_sql_create.args = APP_ARGS

def get_sql_delete(mod):
    "Returns a list of the DROP TABLE SQL statements for the given module."
    from django.core import db
    try:
        cursor = db.db.cursor()
    except:
        cursor = None
    output = []
    for klass in mod._MODELS:
        try:
            if cursor is not None:
                # Check whether the table exists.
                cursor.execute("SELECT 1 FROM %s LIMIT 1" % klass._meta.db_table)
        except:
            # The table doesn't exist, so it doesn't need to be dropped.
            pass
        else:
            output.append("DROP TABLE %s;" % klass._meta.db_table)
    for klass in mod._MODELS:
        opts = klass._meta
        for f in opts.many_to_many:
            try:
                if cursor is not None:
                    cursor.execute("SELECT 1 FROM %s LIMIT 1" % f.get_m2m_db_table(opts))
            except:
                pass
            else:
                output.append("DROP TABLE %s;" % f.get_m2m_db_table(opts))
    output.append("DELETE FROM packages WHERE label = '%s';" % mod._MODELS[0]._meta.app_label)
    output.append("DELETE FROM auth_permissions WHERE package = '%s';" % mod._MODELS[0]._meta.app_label)
    output.append("DELETE FROM content_types WHERE package = '%s';" % mod._MODELS[0]._meta.app_label)
    return output[::-1] # Reverse it, to deal with table dependencies.
get_sql_delete.help_doc = "Prints the DROP TABLE SQL statements for the given app(s)."
get_sql_delete.args = APP_ARGS

def get_sql_reset(mod):
    "Returns a list of the DROP TABLE SQL, then the CREATE TABLE SQL, for the given module."
    return get_sql_delete(mod) + get_sql_all(mod)
get_sql_reset.help_doc = "Prints the DROP TABLE SQL, then the CREATE TABLE SQL, for the given app(s)."
get_sql_reset.args = APP_ARGS

def get_sql_initial_data(mod):
    "Returns a list of the initial INSERT SQL statements for the given module."
    output = []
    app_label = mod._MODELS[0]._meta.app_label
    output.append(_get_packages_insert(app_label))
    app_dir = os.path.normpath(os.path.join(os.path.dirname(mod.__file__), '../sql'))
    for klass in mod._MODELS:
        opts = klass._meta
        # Add custom SQL, if it's available.
        sql_file_name = os.path.join(app_dir, opts.module_name + '.sql')
        if os.path.exists(sql_file_name):
            fp = open(sql_file_name, 'r')
            output.append(fp.read())
            fp.close()
        # Content types.
        output.append(_get_contenttype_insert(opts))
        # Permissions.
        for codename, name in _get_all_permissions(opts):
            output.append(_get_permission_insert(name, codename, opts))
    return output
get_sql_initial_data.help_doc = "Prints the initial INSERT SQL statements for the given app(s)."
get_sql_initial_data.args = APP_ARGS

def get_sql_sequence_reset(mod):
    "Returns a list of the SQL statements to reset PostgreSQL sequences for the given module."
    from django.core import meta
    output = []
    for klass in mod._MODELS:
        for f in klass._meta.fields:
            if isinstance(f, meta.AutoField):
                output.append("SELECT setval('%s_%s_seq', (SELECT max(%s) FROM %s));" % (klass._meta.db_table, f.name, f.name, klass._meta.db_table))
    return output
get_sql_sequence_reset.help_doc = "Prints the SQL statements for resetting PostgreSQL sequences for the given app(s)."
get_sql_sequence_reset.args = APP_ARGS

def get_sql_indexes(mod):
    "Returns a list of the CREATE INDEX SQL statements for the given module."
    output = []
    for klass in mod._MODELS:
        for f in klass._meta.fields:
            if f.db_index:
                unique = f.unique and "UNIQUE " or ""
                output.append("CREATE %sINDEX %s_%s ON %s (%s);" % \
                    (unique, klass._meta.db_table, f.name, klass._meta.db_table, f.name))
    return output
get_sql_indexes.help_doc = "Prints the CREATE INDEX SQL statements for the given app(s)."
get_sql_indexes.args = APP_ARGS

def get_sql_all(mod):
    "Returns a list of CREATE TABLE SQL and initial-data insert for the given module."
    return get_sql_create(mod) + get_sql_initial_data(mod)
get_sql_all.help_doc = "Prints the CREATE TABLE and initial-data SQL statements for the given app(s)."
get_sql_all.args = APP_ARGS

def database_check(mod):
    "Checks that everything is properly installed in the database for the given module."
    from django.core import db
    cursor = db.db.cursor()
    app_label = mod._MODELS[0]._meta.app_label

    # Check that the package exists in the database.
    cursor.execute("SELECT 1 FROM packages WHERE label = %s", [app_label])
    if cursor.rowcount < 1:
#         sys.stderr.write("The '%s' package isn't installed.\n" % app_label)
        print _get_packages_insert(app_label)

    # Check that the permissions and content types are in the database.
    perms_seen = {}
    contenttypes_seen = {}
    for klass in mod._MODELS:
        opts = klass._meta
        perms = _get_all_permissions(opts)
        perms_seen.update(dict(perms))
        contenttypes_seen[opts.module_name] = 1
        for codename, name in perms:
            cursor.execute("SELECT 1 FROM auth_permissions WHERE package = %s AND codename = %s", (app_label, codename))
            if cursor.rowcount < 1:
#                 sys.stderr.write("The '%s.%s' permission doesn't exist.\n" % (app_label, codename))
                print _get_permission_insert(name, codename, opts)
        cursor.execute("SELECT 1 FROM content_types WHERE package = %s AND python_module_name = %s", (app_label, opts.module_name))
        if cursor.rowcount < 1:
#             sys.stderr.write("The '%s.%s' content type doesn't exist.\n" % (app_label, opts.module_name))
            print _get_contenttype_insert(opts)

    # Check that there aren't any *extra* permissions in the DB that the model
    # doesn't know about.
    cursor.execute("SELECT codename FROM auth_permissions WHERE package = %s", (app_label,))
    for row in cursor.fetchall():
        try:
            perms_seen[row[0]]
        except KeyError:
#             sys.stderr.write("A permission called '%s.%s' was found in the database but not in the model.\n" % (app_label, row[0]))
            print "DELETE FROM auth_permissions WHERE package='%s' AND codename = '%s';" % (app_label, row[0])

    # Check that there aren't any *extra* content types in the DB that the
    # model doesn't know about.
    cursor.execute("SELECT python_module_name FROM content_types WHERE package = %s", (app_label,))
    for row in cursor.fetchall():
        try:
            contenttypes_seen[row[0]]
        except KeyError:
#             sys.stderr.write("A content type called '%s.%s' was found in the database but not in the model.\n" % (app_label, row[0]))
            print "DELETE FROM content_types WHERE package='%s' AND python_module_name = '%s';" % (app_label, row[0])
database_check.help_doc = "Checks that everything is installed in the database for the given app(s) and prints SQL statements if needed."
database_check.args = APP_ARGS

def get_admin_index(mod):
    "Returns admin-index template snippet (in list form) for the given module."
    from django.core import meta
    output = []
    app_label = mod._MODELS[0]._meta.app_label
    output.append('{%% if perms.%s %%}' % app_label)
    output.append('<div class="module"><h2>%s</h2><table>' % app_label.title())
    for klass in mod._MODELS:
        if klass._meta.admin:
            output.append(MODULE_TEMPLATE % {
                'app': app_label,
                'mod': klass._meta.module_name,
                'name': meta.capfirst(klass._meta.verbose_name_plural),
                'addperm': klass._meta.get_add_permission(),
                'changeperm': klass._meta.get_change_permission(),
            })
    output.append('</table></div>')
    output.append('{% endif %}')
    return output
get_admin_index.help_doc = "Prints the admin-index template snippet for the given app(s)."
get_admin_index.args = APP_ARGS

def init():
    "Initializes the database with auth and core."
    from django.core import db, meta
    auth = meta.get_app('auth')
    core = meta.get_app('core')
    try:
        cursor = db.db.cursor()
        for sql in get_sql_create(core) + get_sql_create(auth) + get_sql_initial_data(core) + get_sql_initial_data(auth):
            cursor.execute(sql)
        cursor.execute("INSERT INTO %s (domain, name) VALUES ('mysite.com', 'My Django site')" % core.Site._meta.db_table)
    except Exception, e:
        sys.stderr.write("Error: The database couldn't be initialized. Here's the full exception:\n%s\n" % e)
        db.db.rollback()
        sys.exit(1)
    db.db.commit()
init.args = ''

def install(mod):
    "Executes the equivalent of 'get_sql_all' in the current database."
    from django.core import db
    sql_list = get_sql_all(mod)
    try:
        cursor = db.db.cursor()
        for sql in sql_list:
            cursor.execute(sql)
    except Exception, e:
        mod_name = mod.__name__[mod.__name__.rindex('.')+1:]
        sys.stderr.write("""Error: %s couldn't be installed. Possible reasons:
  * The database isn't running or isn't configured correctly.
  * At least one of the database tables already exists.
  * The SQL was invalid.
Hint: Look at the output of 'django-admin.py sqlall %s'. That's the SQL this command wasn't able to run.
The full error: %s\n""" % \
            (mod_name, mod_name, e))
        db.db.rollback()
        sys.exit(1)
    db.db.commit()
install.args = APP_ARGS

def _start_helper(app_or_project, name, directory, other_name=''):
    other = {'project': 'app', 'app': 'project'}[app_or_project]
    if not _is_valid_dir_name(name):
        sys.stderr.write("Error: %r is not a valid %s name. Please use only numbers, letters and underscores.\n" % (name, app_or_project))
        sys.exit(1)
    top_dir = os.path.join(directory, name)
    try:
        os.mkdir(top_dir)
    except OSError, e:
        sys.stderr.write("Error: %s\n" % e)
        sys.exit(1)
    template_dir = PROJECT_TEMPLATE_DIR % app_or_project
    for d, subdirs, files in os.walk(template_dir):
        relative_dir = d[len(template_dir)+1:].replace('%s_name' % app_or_project, name)
        if relative_dir:
            os.mkdir(os.path.join(top_dir, relative_dir))
        for i, subdir in enumerate(subdirs):
            if subdir.startswith('.'):
                del subdirs[i]
        for f in files:
            if f.endswith('.pyc'):
                continue
            fp_old = open(os.path.join(d, f), 'r')
            fp_new = open(os.path.join(top_dir, relative_dir, f.replace('%s_name' % app_or_project, name)), 'w')
            fp_new.write(fp_old.read().replace('{{ %s_name }}' % app_or_project, name).replace('{{ %s_name }}' % other, other_name))
            fp_old.close()
            fp_new.close()

def startproject(project_name, directory):
    "Creates a Django project for the given project_name in the given directory."
    from random import choice
    _start_helper('project', project_name, directory)
    # Populate TEMPLATE_DIRS for the admin templates, based on where Django is
    # installed.
    admin_settings_file = os.path.join(directory, project_name, 'settings/admin.py')
    settings_contents = open(admin_settings_file, 'r').read()
    fp = open(admin_settings_file, 'w')
    settings_contents = re.sub(r'(?s)\b(TEMPLATE_DIRS\s*=\s*\()(.*?)\)', "\\1\n    '%s',\\2)" % ADMIN_TEMPLATE_DIR, settings_contents)
    fp.write(settings_contents)
    fp.close()
    # Create a random SECRET_KEY hash, and put it in the main settings.
    main_settings_file = os.path.join(directory, project_name, 'settings/main.py')
    settings_contents = open(main_settings_file, 'r').read()
    fp = open(main_settings_file, 'w')
    secret_key = ''.join([choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50)])
    settings_contents = re.sub(r"(?<=SECRET_KEY = ')'", secret_key + "'", settings_contents)
    fp.write(settings_contents)
    fp.close()
startproject.help_doc = "Creates a Django project directory structure for the given project name in the current directory."
startproject.args = "[projectname]"

def startapp(app_name, directory):
    "Creates a Django app for the given project_name in the given directory."
    # Determine the project_name a bit naively -- by looking at the name of
    # the parent directory.
    project_dir = os.path.normpath(os.path.join(directory, '../'))
    project_name = os.path.basename(project_dir)
    _start_helper('app', app_name, directory, project_name)
startapp.help_doc = "Creates a Django app directory structure for the given app name in the current directory."
startapp.args = "[appname]"

def createsuperuser():
    "Creates a superuser account."
    from django.core import validators
    from django.models.auth import users
    import getpass
    try:
        while 1:
            username = raw_input('Username (only letters, digits and underscores): ')
            if not username.isalnum():
                sys.stderr.write("Error: That username is invalid.\n")
                continue
            try:
                users.get_object(username__exact=username)
            except users.UserDoesNotExist:
                break
            else:
                sys.stderr.write("Error: That username is already taken.\n")
        while 1:
            email = raw_input('E-mail address: ')
            try:
                validators.isValidEmail(email, None)
            except validators.ValidationError:
                sys.stderr.write("Error: That e-mail address is invalid.\n")
            else:
                break
        while 1:
            password = getpass.getpass()
            password2 = getpass.getpass('Password (again): ')
            if password == password2:
                break
            sys.stderr.write("Error: Your passwords didn't match.\n")
    except KeyboardInterrupt:
        sys.stderr.write("\nOperation cancelled.\n")
        sys.exit(1)
    u = users.create_user(username, email, password)
    u.is_staff = True
    u.is_active = True
    u.is_superuser = True
    u.save()
    print "User created successfully."
createsuperuser.args = ''

def runserver(port):
    "Starts a lightweight Web server for development."
    from django.core.servers.basehttp import run, WSGIServerException
    from django.core.handlers.wsgi import AdminMediaHandler, WSGIHandler
    if not port.isdigit():
        sys.stderr.write("Error: %r is not a valid port number.\n" % port)
        sys.exit(1)
    def inner_run():
        from django.conf.settings import SETTINGS_MODULE
        print "Starting server on port %s with settings module %r." % (port, SETTINGS_MODULE)
        print "Go to http://127.0.0.1:%s/ for Django." % port
        print "Quit the server with CONTROL-C (Unix) or CTRL-BREAK (Windows)."
        try:
            run(int(port), AdminMediaHandler(WSGIHandler()))
        except WSGIServerException, e:
            # Use helpful error messages instead of ugly tracebacks.
            ERRORS = {
                13: "You don't have permission to access that port.",
                98: "That port is already in use.",
            }
            try:
                error_text = ERRORS[e.args[0].args[0]]
            except (AttributeError, KeyError):
                error_text = str(e)
            sys.stderr.write("Error: %s\n" % error_text)
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(0)
    from django.utils import autoreload
    autoreload.main(inner_run)
runserver.args = '[optional port number]'
