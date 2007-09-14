import sys
from django.core.management.color import color_style
from django.utils.itercompat import is_iterable

class ModelErrorCollection:
    def __init__(self, outfile=sys.stdout):
        self.errors = []
        self.outfile = outfile
        self.style = color_style()

    def add(self, context, error):
        self.errors.append((context, error))
        self.outfile.write(self.style.ERROR("%s: %s\n" % (context, error)))

def get_validation_errors(outfile, app=None):
    """
    Validates all models that are part of the specified app. If no app name is provided,
    validates all models of all installed apps. Writes errors, if any, to outfile.
    Returns number of errors.
    """
    from django.conf import settings
    from django.db import models, connection
    from django.db.models.loading import get_app_errors
    from django.db.models.fields.related import RelatedObject

    e = ModelErrorCollection(outfile)

    for (app_name, error) in get_app_errors().items():
        e.add(app_name, error)

    for cls in models.get_models(app):
        opts = cls._meta

        # Do field-specific validation.
        for f in opts.fields:
            if f.name == 'id' and not f.primary_key and opts.pk.name == 'id':
                e.add(opts, '"%s": You can\'t use "id" as a field name, because each model automatically gets an "id" field if none of the fields have primary_key=True. You need to either remove/rename your "id" field or add primary_key=True to a field.' % f.name)
            if isinstance(f, models.CharField) and f.max_length in (None, 0):
                e.add(opts, '"%s": CharFields require a "max_length" attribute.' % f.name)
            if isinstance(f, models.DecimalField):
                if f.decimal_places is None:
                    e.add(opts, '"%s": DecimalFields require a "decimal_places" attribute.' % f.name)
                if f.max_digits is None:
                    e.add(opts, '"%s": DecimalFields require a "max_digits" attribute.' % f.name)
            if isinstance(f, models.FileField) and not f.upload_to:
                e.add(opts, '"%s": FileFields require an "upload_to" attribute.' % f.name)
            if isinstance(f, models.ImageField):
                try:
                    from PIL import Image
                except ImportError:
                    e.add(opts, '"%s": To use ImageFields, you need to install the Python Imaging Library. Get it at http://www.pythonware.com/products/pil/ .' % f.name)
            if f.prepopulate_from is not None and type(f.prepopulate_from) not in (list, tuple):
                e.add(opts, '"%s": prepopulate_from should be a list or tuple.' % f.name)
            if f.choices:
                if isinstance(f.choices, basestring) or not is_iterable(f.choices):
                    e.add(opts, '"%s": "choices" should be iterable (e.g., a tuple or list).' % f.name)
                else:
                    for c in f.choices:
                        if not type(c) in (tuple, list) or len(c) != 2:
                            e.add(opts, '"%s": "choices" should be a sequence of two-tuples.' % f.name)
            if f.db_index not in (None, True, False):
                e.add(opts, '"%s": "db_index" should be either None, True or False.' % f.name)

            # Check that max_length <= 255 if using older MySQL versions.
            if settings.DATABASE_ENGINE == 'mysql':
                db_version = connection.get_server_version()
                if db_version < (5, 0, 3) and isinstance(f, (models.CharField, models.CommaSeparatedIntegerField, models.SlugField)) and f.max_length > 255:
                    e.add(opts, '"%s": %s cannot have a "max_length" greater than 255 when you are using a version of MySQL prior to 5.0.3 (you are using %s).' % (f.name, f.__class__.__name__, '.'.join([str(n) for n in db_version[:3]])))

            # Check to see if the related field will clash with any
            # existing fields, m2m fields, m2m related objects or related objects
            if f.rel:
                rel_opts = f.rel.to._meta
                if f.rel.to not in models.get_models():
                    e.add(opts, "'%s' has relation with model %s, which has not been installed" % (f.name, rel_opts.object_name))

                rel_name = RelatedObject(f.rel.to, cls, f).get_accessor_name()
                rel_query_name = f.related_query_name()
                for r in rel_opts.fields:
                    if r.name == rel_name:
                        e.add(opts, "Accessor for field '%s' clashes with field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                    if r.name == rel_query_name:
                        e.add(opts, "Reverse query name for field '%s' clashes with field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                for r in rel_opts.many_to_many:
                    if r.name == rel_name:
                        e.add(opts, "Accessor for field '%s' clashes with m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                    if r.name == rel_query_name:
                        e.add(opts, "Reverse query name for field '%s' clashes with m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                for r in rel_opts.get_all_related_many_to_many_objects():
                    if r.get_accessor_name() == rel_name:
                        e.add(opts, "Accessor for field '%s' clashes with related m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                    if r.get_accessor_name() == rel_query_name:
                        e.add(opts, "Reverse query name for field '%s' clashes with related m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                for r in rel_opts.get_all_related_objects():
                    if r.field is not f:
                        if r.get_accessor_name() == rel_name:
                            e.add(opts, "Accessor for field '%s' clashes with related field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                        if r.get_accessor_name() == rel_query_name:
                            e.add(opts, "Reverse query name for field '%s' clashes with related field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))

        for i, f in enumerate(opts.many_to_many):
            # Check to see if the related m2m field will clash with any
            # existing fields, m2m fields, m2m related objects or related objects
            rel_opts = f.rel.to._meta
            if f.rel.to not in models.get_models():
                e.add(opts, "'%s' has m2m relation with model %s, which has not been installed" % (f.name, rel_opts.object_name))

            rel_name = RelatedObject(f.rel.to, cls, f).get_accessor_name()
            rel_query_name = f.related_query_name()
            # If rel_name is none, there is no reverse accessor.
            # (This only occurs for symmetrical m2m relations to self).
            # If this is the case, there are no clashes to check for this field, as
            # there are no reverse descriptors for this field.
            if rel_name is not None:
                for r in rel_opts.fields:
                    if r.name == rel_name:
                        e.add(opts, "Accessor for m2m field '%s' clashes with field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                    if r.name == rel_query_name:
                        e.add(opts, "Reverse query name for m2m field '%s' clashes with field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                for r in rel_opts.many_to_many:
                    if r.name == rel_name:
                        e.add(opts, "Accessor for m2m field '%s' clashes with m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                    if r.name == rel_query_name:
                        e.add(opts, "Reverse query name for m2m field '%s' clashes with m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.name, f.name))
                for r in rel_opts.get_all_related_many_to_many_objects():
                    if r.field is not f:
                        if r.get_accessor_name() == rel_name:
                            e.add(opts, "Accessor for m2m field '%s' clashes with related m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                        if r.get_accessor_name() == rel_query_name:
                            e.add(opts, "Reverse query name for m2m field '%s' clashes with related m2m field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                for r in rel_opts.get_all_related_objects():
                    if r.get_accessor_name() == rel_name:
                        e.add(opts, "Accessor for m2m field '%s' clashes with related field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))
                    if r.get_accessor_name() == rel_query_name:
                        e.add(opts, "Reverse query name for m2m field '%s' clashes with related field '%s.%s'. Add a related_name argument to the definition for '%s'." % (f.name, rel_opts.object_name, r.get_accessor_name(), f.name))

        # Check admin attribute.
        if opts.admin is not None:
            if not isinstance(opts.admin, models.AdminOptions):
                e.add(opts, '"admin" attribute, if given, must be set to a models.AdminOptions() instance.')
            else:
                # list_display
                if not isinstance(opts.admin.list_display, (list, tuple)):
                    e.add(opts, '"admin.list_display", if given, must be set to a list or tuple.')
                else:
                    for fn in opts.admin.list_display:
                        try:
                            f = opts.get_field(fn)
                        except models.FieldDoesNotExist:
                            if not hasattr(cls, fn):
                                e.add(opts, '"admin.list_display" refers to %r, which isn\'t an attribute, method or property.' % fn)
                        else:
                            if isinstance(f, models.ManyToManyField):
                                e.add(opts, '"admin.list_display" doesn\'t support ManyToManyFields (%r).' % fn)
                # list_display_links
                if opts.admin.list_display_links and not opts.admin.list_display:
                    e.add(opts, '"admin.list_display" must be defined for "admin.list_display_links" to be used.')
                if not isinstance(opts.admin.list_display_links, (list, tuple)):
                    e.add(opts, '"admin.list_display_links", if given, must be set to a list or tuple.')
                else:
                    for fn in opts.admin.list_display_links:
                        try:
                            f = opts.get_field(fn)
                        except models.FieldDoesNotExist:
                            if not hasattr(cls, fn):
                                e.add(opts, '"admin.list_display_links" refers to %r, which isn\'t an attribute, method or property.' % fn)
                        if fn not in opts.admin.list_display:
                            e.add(opts, '"admin.list_display_links" refers to %r, which is not defined in "admin.list_display".' % fn)
                # list_filter
                if not isinstance(opts.admin.list_filter, (list, tuple)):
                    e.add(opts, '"admin.list_filter", if given, must be set to a list or tuple.')
                else:
                    for fn in opts.admin.list_filter:
                        try:
                            f = opts.get_field(fn)
                        except models.FieldDoesNotExist:
                            e.add(opts, '"admin.list_filter" refers to %r, which isn\'t a field.' % fn)
                # date_hierarchy
                if opts.admin.date_hierarchy:
                    try:
                        f = opts.get_field(opts.admin.date_hierarchy)
                    except models.FieldDoesNotExist:
                        e.add(opts, '"admin.date_hierarchy" refers to %r, which isn\'t a field.' % opts.admin.date_hierarchy)

        # Check ordering attribute.
        if opts.ordering:
            for field_name in opts.ordering:
                if field_name == '?': continue
                if field_name.startswith('-'):
                    field_name = field_name[1:]
                if opts.order_with_respect_to and field_name == '_order':
                    continue
                if '.' in field_name: continue # Skip ordering in the format 'table.field'.
                try:
                    opts.get_field(field_name, many_to_many=False)
                except models.FieldDoesNotExist:
                    e.add(opts, '"ordering" refers to "%s", a field that doesn\'t exist.' % field_name)

        # Check core=True, if needed.
        for related in opts.get_followed_related_objects():
            if not related.edit_inline:
                continue
            try:
                for f in related.opts.fields:
                    if f.core:
                        raise StopIteration
                e.add(related.opts, "At least one field in %s should have core=True, because it's being edited inline by %s.%s." % (related.opts.object_name, opts.module_name, opts.object_name))
            except StopIteration:
                pass

        # Check unique_together.
        for ut in opts.unique_together:
            for field_name in ut:
                try:
                    f = opts.get_field(field_name, many_to_many=True)
                except models.FieldDoesNotExist:
                    e.add(opts, '"unique_together" refers to %s, a field that doesn\'t exist. Check your syntax.' % field_name)
                else:
                    if isinstance(f.rel, models.ManyToManyRel):
                        e.add(opts, '"unique_together" refers to %s. ManyToManyFields are not supported in unique_together.' % f.name)

    return len(e.errors)
