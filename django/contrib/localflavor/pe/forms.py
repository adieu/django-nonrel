# -*- coding: utf-8 -*-
"""
PE-specific Form helpers.
"""

from django.newforms import ValidationError
from django.newforms.fields import RegexField, CharField, Select, EMPTY_VALUES
from django.utils.translation import ugettext

class PEDepartmentSelect(Select):
    """
    A Select widget that uses a list of Peruvian Departments as its choices.
    """
    def __init__(self, attrs=None):
        from pe_department import DEPARTMENT_CHOICES
        super(PEDepartmentSelect, self).__init__(attrs, choices=DEPARTMENT_CHOICES)

class PEDNIField(CharField):
    """
    A field that validates `Documento Nacional de IdentidadŽ (DNI) numbers.
    """
    def __init__(self, *args, **kwargs):
        super(PEDNIField, self).__init__(max_length=8, min_length=8, *args,
                **kwargs)

    def clean(self, value):
        """
        Value must be a string in the XXXXXXXX formats.
        """
        value = super(PEDNIField, self).clean(value)
        if value in EMPTY_VALUES:
            return u''
        if not value.isdigit():
            raise ValidationError(ugettext("This field requires only numbers."))
        if len(value) != 8:
            raise ValidationError(ugettext("This field requires 8 digits."))

        return value

class PERUCField(RegexField):
    """
    This field validates a RUC (Registro Unico de Contribuyentes). A RUC is of
    the form XXXXXXXXXXX.
    """
    def __init__(self, *args, **kwargs):
        super(PERUCField, self).__init__(max_length=11, min_length=11, *args,
            **kwargs)

    def clean(self, value):
        """
        Value must be an 11-digit number.
        """
        value = super(PERUCField, self).clean(value)
        if value in EMPTY_VALUES:
            return u''
        if not value.isdigit():
            raise ValidationError(ugettext("This field requires only numbers."))
        if len(value) != 11:
            raise ValidationError(ugettext("This field requires 11 digits."))
        return value

