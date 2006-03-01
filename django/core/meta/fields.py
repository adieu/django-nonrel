from django.conf import settings
from django.core import formfields, validators
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import curry, lazy
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy, ngettext
import datetime, os

class NOT_PROVIDED:
    pass

# Values for filter_interface.
HORIZONTAL, VERTICAL = 1, 2

# The values to use for "blank" in SelectFields. Will be appended to the start of most "choices" lists.
BLANK_CHOICE_DASH = [("", "---------")]
BLANK_CHOICE_NONE = [("", "None")]

# Values for Relation.edit_inline.
TABULAR, STACKED = 1, 2

RECURSIVE_RELATIONSHIP_CONSTANT = 'self'

# prepares a value for use in a LIKE query
prep_for_like_query = lambda x: str(x).replace("%", "\%").replace("_", "\_")

# returns the <ul> class for a given radio_admin value
get_ul_class = lambda x: 'radiolist%s' % ((x == HORIZONTAL) and ' inline' or '')

def string_concat(*strings):
    """"
    lazy variant of string concatenation, needed for translations that are
    constructed from multiple parts. Handles lazy strings and non-strings by
    first turning all arguments to strings, before joining them.
    """
    return ''.join([str(el) for el in strings])

string_concat = lazy(string_concat, str)

def manipulator_valid_rel_key(f, self, field_data, all_data):
    "Validates that the value is a valid foreign key"
    mod = f.rel.to.get_model_module()
    try:
        mod.get_object(pk=field_data)
    except ObjectDoesNotExist:
        raise validators.ValidationError, _("Please enter a valid %s.") % f.verbose_name

def manipulator_validator_unique(f, opts, self, field_data, all_data):
    "Validates that the value is unique for this field."
    if f.rel and isinstance(f.rel, ManyToOne):
        lookup_type = '%s__%s__exact' % (f.name, f.rel.get_related_field().name)
    else:
        lookup_type = '%s__exact' % f.name
    try:
        old_obj = opts.get_model_module().get_object(**{lookup_type: field_data})
    except ObjectDoesNotExist:
        return
    if hasattr(self, 'original_object') and getattr(self.original_object, opts.pk.attname) == getattr(old_obj, opts.pk.attname):
        return
    raise validators.ValidationError, _("%(optname)s with this %(fieldname)s already exists.") % {'optname': capfirst(opts.verbose_name), 'fieldname': f.verbose_name}

class BoundField(object):
    def __init__(self, field, field_mapping, original):
        self.field = field
        self.original = original
        self.form_fields = self.resolve_form_fields(field_mapping)

    def resolve_form_fields(self, field_mapping):
        return [field_mapping[name] for name in self.field.get_manipulator_field_names('')]

    def as_field_list(self):
        return [self.field]

    def original_value(self):
        if self.original:
            return self.original.__dict__[self.field.column]

    def __repr__(self):
        return "BoundField:(%s, %s)" % (self.field.name, self.form_fields)

# A guide to Field parameters:
#
#   * name:      The name of the field specifed in the model.
#   * attname:   The attribute to use on the model object. This is the same as
#                "name", except in the case of ForeignKeys, where "_id" is
#                appended.
#   * db_column: The db_column specified in the model (or None).
#   * column:    The database column for this field. This is the same as
#                "attname", except if db_column is specified.
#
# Code that introspects values, or does other dynamic things, should use
# attname. For example, this gets the primary key value of object "obj":
#
#     getattr(obj, opts.pk.attname)

class Field(object):

    # Designates whether empty strings fundamentally are allowed at the
    # database level.
    empty_strings_allowed = True

    # Tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, verbose_name=None, name=None, primary_key=False,
        maxlength=None, unique=False, blank=False, null=False, db_index=None,
        core=False, rel=None, default=NOT_PROVIDED, editable=True,
        prepopulate_from=None, unique_for_date=None, unique_for_month=None,
        unique_for_year=None, validator_list=None, choices=None, radio_admin=None,
        help_text='', db_column=None):
        self.name = name
        self.verbose_name = verbose_name or (name and name.replace('_', ' '))
        self.primary_key = primary_key
        self.maxlength, self.unique = maxlength, unique
        self.blank, self.null = blank, null
        self.core, self.rel, self.default = core, rel, default
        self.editable = editable
        self.validator_list = validator_list or []
        self.prepopulate_from = prepopulate_from
        self.unique_for_date, self.unique_for_month = unique_for_date, unique_for_month
        self.unique_for_year = unique_for_year
        self.choices = choices or []
        self.radio_admin = radio_admin
        self.help_text = help_text
        self.db_column = db_column
        if rel and isinstance(rel, ManyToMany):
            if rel.raw_id_admin:
                self.help_text = string_concat(self.help_text,
                    gettext_lazy(' Separate multiple IDs with commas.'))
            else:
                self.help_text = string_concat(self.help_text,
                    gettext_lazy(' Hold down "Control", or "Command" on a Mac, to select more than one.'))

        # Set db_index to True if the field has a relationship and doesn't explicitly set db_index.
        if db_index is None:
            if isinstance(rel, OneToOne) or isinstance(rel, ManyToOne):
                self.db_index = True
            else:
                self.db_index = False
        else:
            self.db_index = db_index

        # Increase the creation counter, and save our local copy.
        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

        self.attname, self.column = self.get_attname_column()

    def set_name(self, name):
        self.name = name
        self.verbose_name = self.verbose_name or name.replace('_', ' ')
        self.attname, self.column = self.get_attname_column()

    def get_attname_column(self):
        if isinstance(self.rel, ManyToOne):
            attname = '%s_id' % self.name
        else:
            attname = self.name
        column = self.db_column or attname
        return attname, column

    def get_cache_name(self):
        return '_%s_cache' % self.name

    def get_internal_type(self):
        return self.__class__.__name__

    def pre_save(self, value, add):
        "Returns field's value just before saving."
        return value

    def get_db_prep_save(self, value):
        "Returns field's value prepared for saving into a database."
        return value

    def get_db_prep_lookup(self, lookup_type, value):
        "Returns field's value prepared for database lookup."
        if lookup_type in ('exact', 'gt', 'gte', 'lt', 'lte', 'ne', 'year', 'month', 'day'):
            return [value]
        elif lookup_type in ('range', 'in'):
            return value
        elif lookup_type in ('contains', 'icontains'):
            return ["%%%s%%" % prep_for_like_query(value)]
        elif lookup_type == 'iexact':
            return [prep_for_like_query(value)]
        elif lookup_type in ('startswith', 'istartswith'):
            return ["%s%%" % prep_for_like_query(value)]
        elif lookup_type in ('endswith', 'iendswith'):
            return ["%%%s" % prep_for_like_query(value)]
        elif lookup_type == 'isnull':
            return []
        raise TypeError, "Field has invalid lookup: %s" % lookup_type

    def has_default(self):
        "Returns a boolean of whether this field has a default value."
        return self.default is not NOT_PROVIDED

    def get_default(self):
        "Returns the default value for this field."
        if self.default is not NOT_PROVIDED:
            if hasattr(self.default, '__get_value__'):
                return self.default.__get_value__()
            return self.default
        if not self.empty_strings_allowed or self.null:
            return None
        return ""

    def get_manipulator_field_names(self, name_prefix):
        """
        Returns a list of field names that this object adds to the manipulator.
        """
        return [name_prefix + self.name]

    def get_manipulator_fields(self, opts, manipulator, change, name_prefix='', rel=False):
        """
        Returns a list of formfields.FormField instances for this field. It
        calculates the choices at runtime, not at compile time.

        name_prefix is a prefix to prepend to the "field_name" argument.
        rel is a boolean specifying whether this field is in a related context.
        """
        params = {'validator_list': self.validator_list[:]}
        if self.maxlength and not self.choices: # Don't give SelectFields a maxlength parameter.
            params['maxlength'] = self.maxlength
        if isinstance(self.rel, ManyToOne):
            params['member_name'] = name_prefix + self.attname
            if self.rel.raw_id_admin:
                field_objs = self.get_manipulator_field_objs()
                params['validator_list'].append(curry(manipulator_valid_rel_key, self, manipulator))
            else:
                if self.radio_admin:
                    field_objs = [formfields.RadioSelectField]
                    params['ul_class'] = get_ul_class(self.radio_admin)
                else:
                    if self.null:
                        field_objs = [formfields.NullSelectField]
                    else:
                        field_objs = [formfields.SelectField]
                params['choices'] = self.get_choices_default()
        elif self.choices:
            if self.radio_admin:
                field_objs = [formfields.RadioSelectField]
                params['ul_class'] = get_ul_class(self.radio_admin)
            else:
                field_objs = [formfields.SelectField]

            params['choices'] = self.get_choices_default()
        else:
            field_objs = self.get_manipulator_field_objs()

        # Add the "unique" validator(s).
        for field_name_list in opts.unique_together:
            if field_name_list[0] == self.name:
                params['validator_list'].append(getattr(manipulator, 'isUnique%s' % '_'.join(field_name_list)))

        # Add the "unique for..." validator(s).
        if self.unique_for_date:
            params['validator_list'].append(getattr(manipulator, 'isUnique%sFor%s' % (self.name, self.unique_for_date)))
        if self.unique_for_month:
            params['validator_list'].append(getattr(manipulator, 'isUnique%sFor%s' % (self.name, self.unique_for_month)))
        if self.unique_for_year:
            params['validator_list'].append(getattr(manipulator, 'isUnique%sFor%s' % (self.name, self.unique_for_year)))
        if self.unique or (self.primary_key and not rel):
            params['validator_list'].append(curry(manipulator_validator_unique, self, opts, manipulator))

        # Only add is_required=True if the field cannot be blank. Primary keys
        # are a special case, and fields in a related context should set this
        # as False, because they'll be caught by a separate validator --
        # RequiredIfOtherFieldGiven.
        params['is_required'] = not self.blank and not self.primary_key and not rel

        # If this field is in a related context, check whether any other fields
        # in the related object have core=True. If so, add a validator --
        # RequiredIfOtherFieldsGiven -- to this FormField.
        if rel and not self.blank and not isinstance(self, AutoField) and not isinstance(self, FileField):
            # First, get the core fields, if any.
            core_field_names = []
            for f in opts.fields:
                if f.core and f != self:
                    core_field_names.extend(f.get_manipulator_field_names(name_prefix))
            # Now, if there are any, add the validator to this FormField.
            if core_field_names:
                params['validator_list'].append(validators.RequiredIfOtherFieldsGiven(core_field_names, gettext_lazy("This field is required.")))

        # BooleanFields (CheckboxFields) are a special case. They don't take
        # is_required or validator_list.
        if isinstance(self, BooleanField):
            del params['validator_list'], params['is_required']

        # Finally, add the field_names.
        field_names = self.get_manipulator_field_names(name_prefix)
        return [man(field_name=field_names[i], **params) for i, man in enumerate(field_objs)]

    def get_manipulator_new_data(self, new_data, rel=False):
        """
        Given the full new_data dictionary (from the manipulator), returns this
        field's data.
        """
        if rel:
            return new_data.get(self.name, [self.get_default()])[0]
        else:
            val = new_data.get(self.name, self.get_default())
            if not self.empty_strings_allowed and val == '' and self.null:
                val = None
            return val

    def get_choices(self, include_blank=True, blank_choice=BLANK_CHOICE_DASH):
        "Returns a list of tuples used as SelectField choices for this field."
        first_choice = include_blank and blank_choice or []
        if self.choices:
            return first_choice + list(self.choices)
        rel_obj = self.rel.to
        return first_choice + [(getattr(x, rel_obj.pk.attname), str(x))
                               for x in rel_obj.get_model_module().get_list(**self.rel.limit_choices_to)]

    def get_choices_default(self):
        if(self.radio_admin):
            return self.get_choices(include_blank=self.blank, blank_choice=BLANK_CHOICE_NONE)
        else:
            return self.get_choices()

    def _get_val_from_obj(self, obj):
        if obj:
           return getattr(obj, self.attname)
        else:
           return self.get_default()

    def flatten_data(self, follow, obj=None):
        """
        Returns a dictionary mapping the field's manipulator field names to its
        "flattened" string values for the admin view. obj is the instance to
        extract the values from.
        """
        return {self.attname: self._get_val_from_obj(obj)}

    def get_follow(self, override=None):
        if override != None:
            return override
        else:
            return self.editable

    def bind(self, fieldmapping, original, bound_field_class=BoundField):
        return bound_field_class(self, fieldmapping, original)

class AutoField(Field):
    empty_strings_allowed = False
    def __init__(self, *args, **kwargs):
        assert kwargs.get('primary_key', False) is True, "%ss must have primary_key=True." % self.__class__.__name__
        Field.__init__(self, *args, **kwargs)

    def get_manipulator_fields(self, opts, manipulator, change, name_prefix='', rel=False):
        if not rel:
            return [] # Don't add a FormField unless it's in a related context.
        return Field.get_manipulator_fields(self, opts, manipulator, change, name_prefix, rel)

    def get_manipulator_field_objs(self):
        return [formfields.HiddenField]

    def get_manipulator_new_data(self, new_data, rel=False):
        if not rel:
            return None
        return Field.get_manipulator_new_data(self, new_data, rel)

class BooleanField(Field):
    def __init__(self, *args, **kwargs):
        kwargs['blank'] = True
        Field.__init__(self, *args, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.CheckboxField]

class CharField(Field):
    def get_manipulator_field_objs(self):
        return [formfields.TextField]

class CommaSeparatedIntegerField(CharField):
    def get_manipulator_field_objs(self):
        return [formfields.CommaSeparatedIntegerField]

class DateField(Field):
    empty_strings_allowed = False
    def __init__(self, verbose_name=None, name=None, auto_now=False, auto_now_add=False, **kwargs):
        self.auto_now, self.auto_now_add = auto_now, auto_now_add
        #HACKs : auto_now_add/auto_now should be done as a default or a pre_save...
        if auto_now or auto_now_add:
            kwargs['editable'] = False
            kwargs['blank'] = True
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_db_prep_lookup(self, lookup_type, value):
        if lookup_type == 'range':
            value = [str(v) for v in value]
        else:
            value = str(value)
        return Field.get_db_prep_lookup(self, lookup_type, value)

    def pre_save(self, value, add):
        if self.auto_now or (self.auto_now_add and add):
            return datetime.datetime.now()
        return value

    # Needed because of horrible auto_now[_add] behaviour wrt. editable
    def get_follow(self, override=None):
        if override != None:
            return override
        else:
            return self.editable or self.auto_now or self.auto_now_add

    def get_db_prep_save(self, value):
        # Casts dates into string format for entry into database.
        if value is not None:
            value = value.strftime('%Y-%m-%d')
        return Field.get_db_prep_save(self, value)

    def get_manipulator_field_objs(self):
        return [formfields.DateField]

    def flatten_data(self, follow, obj = None):
        val = self._get_val_from_obj(obj)
        return {self.attname: (val is not None and val.strftime("%Y-%m-%d") or '')}

class DateTimeField(DateField):
    def get_db_prep_save(self, value):
        # Casts dates into string format for entry into database.
        if value is not None:
            # MySQL will throw a warning if microseconds are given, because it
            # doesn't support microseconds.
            if settings.DATABASE_ENGINE == 'mysql':
                value = value.replace(microsecond=0)
            value = str(value)
        return Field.get_db_prep_save(self, value)

    def get_manipulator_field_objs(self):
        return [formfields.DateField, formfields.TimeField]

    def get_manipulator_field_names(self, name_prefix):
        return [name_prefix + self.name + '_date', name_prefix + self.name + '_time']

    def get_manipulator_new_data(self, new_data, rel=False):
        date_field, time_field = self.get_manipulator_field_names('')
        if rel:
            d = new_data.get(date_field, [None])[0]
            t = new_data.get(time_field, [None])[0]
        else:
            d = new_data.get(date_field, None)
            t = new_data.get(time_field, None)
        if d is not None and t is not None:
            return datetime.datetime.combine(d, t)
        return self.get_default()

    def flatten_data(self,follow, obj = None):
        val = self._get_val_from_obj(obj)
        date_field, time_field = self.get_manipulator_field_names('')
        return {date_field: (val is not None and val.strftime("%Y-%m-%d") or ''),
                time_field: (val is not None and val.strftime("%H:%M:%S") or '')}

class EmailField(Field):
    def __init__(self, *args, **kwargs):
        kwargs['maxlength'] = 75
        Field.__init__(self, *args, **kwargs)

    def get_internal_type(self):
        return "CharField"

    def get_manipulator_field_objs(self):
        return [formfields.EmailField]

class FileField(Field):
    def __init__(self, verbose_name=None, name=None, upload_to='', **kwargs):
        self.upload_to = upload_to
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_manipulator_fields(self, opts, manipulator, change, name_prefix='', rel=False):
        field_list = Field.get_manipulator_fields(self, opts, manipulator, change, name_prefix, rel)

        if not self.blank:
            if rel:
                # This validator makes sure FileFields work in a related context.
                class RequiredFileField:
                    def __init__(self, other_field_names, other_file_field_name):
                        self.other_field_names = other_field_names
                        self.other_file_field_name = other_file_field_name
                        self.always_test = True
                    def __call__(self, field_data, all_data):
                        if not all_data.get(self.other_file_field_name, False):
                            c = validators.RequiredIfOtherFieldsGiven(self.other_field_names, gettext_lazy("This field is required."))
                            c(field_data, all_data)
                # First, get the core fields, if any.
                core_field_names = []
                for f in opts.fields:
                    if f.core and f != self:
                        core_field_names.extend(f.get_manipulator_field_names(name_prefix))
                # Now, if there are any, add the validator to this FormField.
                if core_field_names:
                    field_list[0].validator_list.append(RequiredFileField(core_field_names, field_list[1].field_name))
            else:
                v = validators.RequiredIfOtherFieldNotGiven(field_list[1].field_name, gettext_lazy("This field is required."))
                v.always_test = True
                field_list[0].validator_list.append(v)
                field_list[0].is_required = field_list[1].is_required = False

        # If the raw path is passed in, validate it's under the MEDIA_ROOT.
        def isWithinMediaRoot(field_data, all_data):
            f = os.path.abspath(os.path.join(settings.MEDIA_ROOT, field_data))
            if not f.startswith(os.path.normpath(settings.MEDIA_ROOT)):
                raise validators.ValidationError, _("Enter a valid filename.")
        field_list[1].validator_list.append(isWithinMediaRoot)
        return field_list

    def get_manipulator_field_objs(self):
        return [formfields.FileUploadField, formfields.HiddenField]

    def get_manipulator_field_names(self, name_prefix):
        return [name_prefix + self.name + '_file', name_prefix + self.name]

    def save_file(self, new_data, new_object, original_object, change, rel):
        upload_field_name = self.get_manipulator_field_names('')[0]
        if new_data.get(upload_field_name, False):
            func = getattr(new_object, 'save_%s_file' % self.name)
            if rel:
                func(new_data[upload_field_name][0]["filename"], new_data[upload_field_name][0]["content"])
            else:
                func(new_data[upload_field_name]["filename"], new_data[upload_field_name]["content"])

    def get_directory_name(self):
        return os.path.normpath(datetime.datetime.now().strftime(self.upload_to))

    def get_filename(self, filename):
        from django.utils.text import get_valid_filename
        f = os.path.join(self.get_directory_name(), get_valid_filename(os.path.basename(filename)))
        return os.path.normpath(f)

class FilePathField(Field):
    def __init__(self, verbose_name=None, name=None, path='', match=None, recursive=False, **kwargs):
        self.path, self.match, self.recursive = path, match, recursive
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_manipulator_field_objs(self):
        return [curry(formfields.FilePathField, path=self.path, match=self.match, recursive=self.recursive)]

class FloatField(Field):
    empty_strings_allowed = False
    def __init__(self, verbose_name=None, name=None, max_digits=None, decimal_places=None, **kwargs):
        self.max_digits, self.decimal_places = max_digits, decimal_places
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_manipulator_field_objs(self):
        return [curry(formfields.FloatField, max_digits=self.max_digits, decimal_places=self.decimal_places)]

class ImageField(FileField):
    def __init__(self, verbose_name=None, name=None, width_field=None, height_field=None, **kwargs):
        self.width_field, self.height_field = width_field, height_field
        FileField.__init__(self, verbose_name, name, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.ImageUploadField, formfields.HiddenField]

    def save_file(self, new_data, new_object, original_object, change, rel):
        FileField.save_file(self, new_data, new_object, original_object, change, rel)
        # If the image has height and/or width field(s) and they haven't
        # changed, set the width and/or height field(s) back to their original
        # values.
        if change and (self.width_field or self.height_field):
            if self.width_field:
                setattr(new_object, self.width_field, getattr(original_object, self.width_field))
            if self.height_field:
                setattr(new_object, self.height_field, getattr(original_object, self.height_field))
            new_object.save()

class IntegerField(Field):
    empty_strings_allowed = False
    def get_manipulator_field_objs(self):
        return [formfields.IntegerField]

class IPAddressField(Field):
    def __init__(self, *args, **kwargs):
        kwargs['maxlength'] = 15
        Field.__init__(self, *args, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.IPAddressField]

class NullBooleanField(Field):
    def __init__(self, *args, **kwargs):
        kwargs['null'] = True
        Field.__init__(self, *args, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.NullBooleanField]

class PhoneNumberField(IntegerField):
    def get_manipulator_field_objs(self):
        return [formfields.PhoneNumberField]

class PositiveIntegerField(IntegerField):
    def get_manipulator_field_objs(self):
        return [formfields.PositiveIntegerField]

class PositiveSmallIntegerField(IntegerField):
    def get_manipulator_field_objs(self):
        return [formfields.PositiveSmallIntegerField]

class SlugField(Field):
    def __init__(self, *args, **kwargs):
        # Default to a maxlength of 50 but allow overrides.
        kwargs['maxlength'] = kwargs.get('maxlength', 50)
        kwargs.setdefault('validator_list', []).append(validators.isSlug)
        # Set db_index=True unless it's been set manually.
        if not kwargs.has_key('db_index'):
            kwargs['db_index'] = True
        Field.__init__(self, *args, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.TextField]

class SmallIntegerField(IntegerField):
    def get_manipulator_field_objs(self):
        return [formfields.SmallIntegerField]

class TextField(Field):
    def get_manipulator_field_objs(self):
        return [formfields.LargeTextField]

class TimeField(Field):
    empty_strings_allowed = False
    def __init__(self, verbose_name=None, name=None, auto_now=False, auto_now_add=False, **kwargs):
        self.auto_now, self.auto_now_add  = auto_now, auto_now_add
        if auto_now or auto_now_add:
            kwargs['editable'] = False
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_db_prep_lookup(self, lookup_type, value):
        if lookup_type == 'range':
            value = [str(v) for v in value]
        else:
            value = str(value)
        return Field.get_db_prep_lookup(self, lookup_type, value)

    def pre_save(self, value, add):
        if self.auto_now or (self.auto_now_add and add):
            return datetime.datetime.now().time()
        return value

    def get_db_prep_save(self, value):
        # Casts dates into string format for entry into database.
        if value is not None:
            # MySQL will throw a warning if microseconds are given, because it
            # doesn't support microseconds.
            if settings.DATABASE_ENGINE == 'mysql':
                value = value.replace(microsecond=0)
            value = str(value)
        return Field.get_db_prep_save(self, value)

    def get_manipulator_field_objs(self):
        return [formfields.TimeField]

    def flatten_data(self,follow, obj = None):
        val = self._get_val_from_obj(obj)
        return {self.attname: (val is not None and val.strftime("%H:%M:%S") or '')}

class URLField(Field):
    def __init__(self, verbose_name=None, name=None, verify_exists=True, **kwargs):
        if verify_exists:
            kwargs.setdefault('validator_list', []).append(validators.isExistingURL)
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_manipulator_field_objs(self):
        return [formfields.URLField]

class USStateField(Field):
    def get_manipulator_field_objs(self):
        return [formfields.USStateField]

class XMLField(TextField):
    def __init__(self, verbose_name=None, name=None, schema_path=None, **kwargs):
        self.schema_path = schema_path
        Field.__init__(self, verbose_name, name, **kwargs)

    def get_internal_type(self):
        return "TextField"

    def get_manipulator_field_objs(self):
        return [curry(formfields.XMLLargeTextField, schema_path=self.schema_path)]

class ForeignKey(Field):
    empty_strings_allowed = False
    def __init__(self, to, to_field=None, **kwargs):
        try:
            to_name = to._meta.object_name.lower()
        except AttributeError: # to._meta doesn't exist, so it must be RECURSIVE_RELATIONSHIP_CONSTANT
            assert to == 'self', "ForeignKey(%r) is invalid. First parameter to ForeignKey must be either a model or the string %r" % (to, RECURSIVE_RELATIONSHIP_CONSTANT)
        else:
            to_field = to_field or to._meta.pk.name
        kwargs['verbose_name'] = kwargs.get('verbose_name', '')

        if kwargs.has_key('edit_inline_type'):
            import warnings
            warnings.warn("edit_inline_type is deprecated. Use edit_inline instead.")
            kwargs['edit_inline'] = kwargs.pop('edit_inline_type')

        kwargs['rel'] = ManyToOne(to, to_field,
            num_in_admin=kwargs.pop('num_in_admin', 3),
            min_num_in_admin=kwargs.pop('min_num_in_admin', None),
            max_num_in_admin=kwargs.pop('max_num_in_admin', None),
            num_extra_on_change=kwargs.pop('num_extra_on_change', 1),
            edit_inline=kwargs.pop('edit_inline', False),
            related_name=kwargs.pop('related_name', None),
            limit_choices_to=kwargs.pop('limit_choices_to', None),
            lookup_overrides=kwargs.pop('lookup_overrides', None),
            raw_id_admin=kwargs.pop('raw_id_admin', False))
        Field.__init__(self, **kwargs)

    def get_manipulator_field_objs(self):
        rel_field = self.rel.get_related_field()
        if self.rel.raw_id_admin and not isinstance(rel_field, AutoField):
            return rel_field.get_manipulator_field_objs()
        else:
            return [formfields.IntegerField]

    def get_db_prep_save(self,value):
        if value == '' or value == None:
            return None
        else:
            return self.rel.get_related_field().get_db_prep_save(value)

    def flatten_data(self, follow, obj=None):
        if not obj:
            # In required many-to-one fields with only one available choice,
            # select that one available choice. Note: For SelectFields
            # (radio_admin=False), we have to check that the length of choices
            # is *2*, not 1, because SelectFields always have an initial
            # "blank" value. Otherwise (radio_admin=True), we check that the
            # length is 1.
            if not self.blank and (not self.rel.raw_id_admin or self.choices):
                choice_list = self.get_choices_default()
                if self.radio_admin and len(choice_list) == 1:
                    return {self.attname: choice_list[0][0]}
                if not self.radio_admin and len(choice_list) == 2:
                    return {self.attname: choice_list[1][0]}
        return Field.flatten_data(self, follow, obj)

class ManyToManyField(Field):
    def __init__(self, to, **kwargs):
        kwargs['verbose_name'] = kwargs.get('verbose_name', to._meta.verbose_name_plural)
        kwargs['rel'] = ManyToMany(to, kwargs.pop('singular', None),
            num_in_admin=kwargs.pop('num_in_admin', 0),
            related_name=kwargs.pop('related_name', None),
            filter_interface=kwargs.pop('filter_interface', None),
            limit_choices_to=kwargs.pop('limit_choices_to', None),
            raw_id_admin=kwargs.pop('raw_id_admin', False))
        if kwargs["rel"].raw_id_admin:
            kwargs.setdefault("validator_list", []).append(self.isValidIDList)
        Field.__init__(self, **kwargs)

    def get_manipulator_field_objs(self):
        if self.rel.raw_id_admin:
            return [formfields.RawIdAdminField]
        else:
            choices = self.get_choices_default()
            return [curry(formfields.SelectMultipleField, size=min(max(len(choices), 5), 15), choices=choices)]

    def get_choices_default(self):
        return Field.get_choices(self, include_blank=False)

    def get_m2m_db_table(self, original_opts):
        "Returns the name of the many-to-many 'join' table."
        return '%s_%s' % (original_opts.db_table, self.name)

    def isValidIDList(self, field_data, all_data):
        "Validates that the value is a valid list of foreign keys"
        mod = self.rel.to.get_model_module()
        try:
            pks = map(int, field_data.split(','))
        except ValueError:
            # the CommaSeparatedIntegerField validator will catch this error
            return
        objects = mod.get_in_bulk(pks)
        if len(objects) != len(pks):
            badkeys = [k for k in pks if k not in objects]
            raise validators.ValidationError, ngettext("Please enter valid %(self)s IDs. The value %(value)r is invalid.",
                    "Please enter valid %(self)s IDs. The values %(value)r are invalid.", len(badkeys)) % {
                'self': self.verbose_name,
                'value': len(badkeys) == 1 and badkeys[0] or tuple(badkeys),
            }

    def flatten_data(self, follow, obj = None):
        new_data = {}
        if obj:
            get_list_func = getattr(obj, 'get_%s_list' % self.rel.singular)
            instance_ids = [getattr(instance, self.rel.to.pk.attname) for instance in get_list_func()]
            if self.rel.raw_id_admin:
                 new_data[self.name] = ",".join([str(id) for id in instance_ids])
            else:
                 new_data[self.name] = instance_ids
        else:
            # In required many-to-many fields with only one available choice,
            # select that one available choice.
            if not self.blank and not self.rel.edit_inline and not self.rel.raw_id_admin:
               choices_list = self.get_choices_default()
               if len(choices_list) == 1:
                   print self.name, choices_list[0][0]
                   new_data[self.name] = [choices_list[0][0]]
        return new_data

class OneToOneField(IntegerField):
    def __init__(self, to, to_field=None, **kwargs):
        kwargs['verbose_name'] = kwargs.get('verbose_name', 'ID')
        to_field = to_field or to._meta.pk.name

        if kwargs.has_key('edit_inline_type'):
            import warnings
            warnings.warn("edit_inline_type is deprecated. Use edit_inline instead.")
            kwargs['edit_inline'] = kwargs.pop('edit_inline_type')

        kwargs['rel'] = OneToOne(to, to_field,
            num_in_admin=kwargs.pop('num_in_admin', 0),
            edit_inline=kwargs.pop('edit_inline', False),
            related_name=kwargs.pop('related_name', None),
            limit_choices_to=kwargs.pop('limit_choices_to', None),
            lookup_overrides=kwargs.pop('lookup_overrides', None),
            raw_id_admin=kwargs.pop('raw_id_admin', False))
        kwargs['primary_key'] = True
        IntegerField.__init__(self, **kwargs)

class ManyToOne:
    def __init__(self, to, field_name, num_in_admin=3, min_num_in_admin=None,
        max_num_in_admin=None, num_extra_on_change=1, edit_inline=False,
        related_name=None, limit_choices_to=None, lookup_overrides=None, raw_id_admin=False):
        try:
            self.to = to._meta
        except AttributeError: # to._meta doesn't exist, so it must be RECURSIVE_RELATIONSHIP_CONSTANT
            assert to == RECURSIVE_RELATIONSHIP_CONSTANT, "'to' must be either a model or the string '%s'" % RECURSIVE_RELATIONSHIP_CONSTANT
            self.to = to
        self.field_name = field_name
        self.num_in_admin, self.edit_inline = num_in_admin, edit_inline
        self.min_num_in_admin, self.max_num_in_admin = min_num_in_admin, max_num_in_admin
        self.num_extra_on_change, self.related_name = num_extra_on_change, related_name
        self.limit_choices_to = limit_choices_to or {}
        self.lookup_overrides = lookup_overrides or {}
        self.raw_id_admin = raw_id_admin

    def get_related_field(self):
        "Returns the Field in the 'to' object to which this relationship is tied."
        return self.to.get_field(self.field_name)

class ManyToMany:
    def __init__(self, to, singular=None, num_in_admin=0, related_name=None,
        filter_interface=None, limit_choices_to=None, raw_id_admin=False):
        self.to = to._meta
        self.singular = singular or to._meta.object_name.lower()
        self.num_in_admin = num_in_admin
        self.related_name = related_name
        self.filter_interface = filter_interface
        self.limit_choices_to = limit_choices_to or {}
        self.edit_inline = False
        self.raw_id_admin = raw_id_admin
        assert not (self.raw_id_admin and self.filter_interface), "ManyToMany relationships may not use both raw_id_admin and filter_interface"

class OneToOne(ManyToOne):
    def __init__(self, to, field_name, num_in_admin=0, edit_inline=False,
        related_name=None, limit_choices_to=None, lookup_overrides=None,
        raw_id_admin=False):
        self.to, self.field_name = to._meta, field_name
        self.num_in_admin, self.edit_inline = num_in_admin, edit_inline
        self.related_name = related_name
        self.limit_choices_to = limit_choices_to or {}
        self.lookup_overrides = lookup_overrides or {}
        self.raw_id_admin = raw_id_admin

class BoundFieldLine(object):
    def __init__(self, field_line, field_mapping, original, bound_field_class=BoundField):
        self.bound_fields = [field.bind(field_mapping, original, bound_field_class) for field in field_line]

    def __iter__(self):
        for bound_field in self.bound_fields:
            yield bound_field

    def __len__(self):
        return len(self.bound_fields)

class FieldLine(object):
    def __init__(self, field_locator_func, linespec):
        if isinstance(linespec, basestring):
            self.fields = [field_locator_func(linespec)]
        else:
            self.fields = [field_locator_func(field_name) for field_name in linespec]

    def bind(self, field_mapping, original, bound_field_line_class=BoundFieldLine):
        return bound_field_line_class(self, field_mapping, original)

    def __iter__(self):
        for field in self.fields:
            yield field

    def __len__(self):
        return len(self.fields)

class BoundFieldSet(object):
    def __init__(self, field_set, field_mapping, original, bound_field_line_class=BoundFieldLine):
        self.name = field_set.name
        self.classes = field_set.classes
        self.bound_field_lines = [field_line.bind(field_mapping,original, bound_field_line_class) for field_line in field_set]

    def __iter__(self):
        for bound_field_line in self.bound_field_lines:
            yield bound_field_line

    def __len__(self):
        return len(self.bound_field_lines)

class FieldSet(object):
    def __init__(self, name, classes, field_locator_func, line_specs):
        self.name = name
        self.field_lines = [FieldLine(field_locator_func, line_spec) for line_spec in line_specs]
        self.classes = classes

    def __repr__(self):
         return "FieldSet:(%s,%s)" % (self.name, self.field_lines)

    def bind(self, field_mapping, original, bound_field_set_class=BoundFieldSet):
        return bound_field_set_class(self, field_mapping, original)

    def __iter__(self):
        for field_line in self.field_lines:
            yield field_line

    def __len__(self):
        return len(self.field_lines)

class Admin:
    def __init__(self, fields=None, js=None, list_display=None, list_filter=None, date_hierarchy=None,
        save_as=False, ordering=None, search_fields=None, save_on_top=False, list_select_related=False):
        self.fields = fields
        self.js = js or []
        self.list_display = list_display or ['__repr__']
        self.list_filter = list_filter or []
        self.date_hierarchy = date_hierarchy
        self.save_as, self.ordering = save_as, ordering
        self.search_fields = search_fields or []
        self.save_on_top = save_on_top
        self.list_select_related = list_select_related

    def get_field_sets(self, opts):
        if self.fields is None:
            field_struct = ((None, {
                'fields': [f.name for f in opts.fields + opts.many_to_many if f.editable and not isinstance(f, AutoField)]
                }),)
        else:
            field_struct = self.fields
        new_fieldset_list = []
        for fieldset in field_struct:
            name = fieldset[0]
            fs_options = fieldset[1]
            classes = fs_options.get('classes', ())
            line_specs = fs_options['fields']
            new_fieldset_list.append(FieldSet(name, classes, opts.get_field, line_specs))
        return new_fieldset_list
