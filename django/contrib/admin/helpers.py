
from django import forms
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.contrib.admin.util import flatten_fieldsets
from django.contrib.contenttypes.models import ContentType

class AdminForm(object):
    def __init__(self, form, fieldsets, prepopulated_fields):
        self.form, self.fieldsets = form, fieldsets
        self.prepopulated_fields = [{
            'field': form[field_name],
            'dependencies': [form[f] for f in dependencies]
        } for field_name, dependencies in prepopulated_fields.items()]

    def __iter__(self):
        for name, options in self.fieldsets:
            yield Fieldset(self.form, name, **options)

    def first_field(self):
        for bf in self.form:
            return bf

    def _media(self):
        media = self.form.media
        for fs in self:
            media = media + fs.media
        return media
    media = property(_media)

class Fieldset(object):
    def __init__(self, form, name=None, fields=(), classes=(), description=None):
        self.form = form
        self.name, self.fields = name, fields
        self.classes = u' '.join(classes)
        self.description = description

    def _media(self):
        if 'collapse' in self.classes:
            return forms.Media(js=['%sjs/admin/CollapsedFieldsets.js' % settings.ADMIN_MEDIA_PREFIX])
        return forms.Media()
    media = property(_media)

    def __iter__(self):
        for field in self.fields:
            yield Fieldline(self.form, field)

class Fieldline(object):
    def __init__(self, form, field):
        self.form = form # A django.forms.Form instance
        if isinstance(field, basestring):
            self.fields = [field]
        else:
            self.fields = field

    def __iter__(self):
        for i, field in enumerate(self.fields):
            yield AdminField(self.form, field, is_first=(i == 0))

    def errors(self):
        return mark_safe(u'\n'.join([self.form[f].errors.as_ul() for f in self.fields]).strip('\n'))

class AdminField(object):
    def __init__(self, form, field, is_first):
        self.field = form[field] # A django.forms.BoundField instance
        self.is_first = is_first # Whether this field is first on the line
        self.is_checkbox = isinstance(self.field.field.widget, forms.CheckboxInput)

    def label_tag(self):
        classes = []
        if self.is_checkbox:
            classes.append(u'vCheckboxLabel')
            contents = force_unicode(escape(self.field.label))
        else:
            contents = force_unicode(escape(self.field.label)) + u':'
        if self.field.field.required:
            classes.append(u'required')
        if not self.is_first:
            classes.append(u'inline')
        attrs = classes and {'class': u' '.join(classes)} or {}
        return self.field.label_tag(contents=contents, attrs=attrs)

class InlineAdminFormSet(object):
    """
    A wrapper around an inline formset for use in the admin system.
    """
    def __init__(self, inline, formset, fieldsets):
        self.opts = inline
        self.formset = formset
        self.fieldsets = fieldsets

    def __iter__(self):
        for form, original in zip(self.formset.initial_forms, self.formset.get_queryset()):
            yield InlineAdminForm(self.formset, form, self.fieldsets, self.opts.prepopulated_fields, original)
        for form in self.formset.extra_forms:
            yield InlineAdminForm(self.formset, form, self.fieldsets, self.opts.prepopulated_fields, None)

    def fields(self):
        for field_name in flatten_fieldsets(self.fieldsets):
            yield self.formset.form.base_fields[field_name]

    def _media(self):
        media = self.opts.media + self.formset.media
        for fs in self:
            media = media + fs.media
        return media
    media = property(_media)

class InlineAdminForm(AdminForm):
    """
    A wrapper around an inline form for use in the admin system.
    """
    def __init__(self, formset, form, fieldsets, prepopulated_fields, original):
        self.formset = formset
        self.original = original
        if original is not None:
            self.original.content_type_id = ContentType.objects.get_for_model(original).pk
        self.show_url = original and hasattr(original, 'get_absolute_url')
        super(InlineAdminForm, self).__init__(form, fieldsets, prepopulated_fields)

    def pk_field(self):
        return AdminField(self.form, self.formset._pk_field_name, False)

    def deletion_field(self):
        from django.forms.formsets import DELETION_FIELD_NAME
        return AdminField(self.form, DELETION_FIELD_NAME, False)

    def ordering_field(self):
        from django.forms.formsets import ORDERING_FIELD_NAME
        return AdminField(self.form, ORDERING_FIELD_NAME, False)

class AdminErrorList(forms.util.ErrorList):
    """
    Stores all errors for the form/formsets in an add/change stage view.
    """
    def __init__(self, form, inline_formsets):
        if form.is_bound:
            self.extend(form.errors.values())
            for inline_formset in inline_formsets:
                self.extend(inline_formset.non_form_errors())
                for errors_in_inline_form in inline_formset.errors:
                    self.extend(errors_in_inline_form.values())
