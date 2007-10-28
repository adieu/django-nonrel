# -*- coding: utf-8 -*-
tests = r"""
>>> from django.newforms import *

# CharField ###################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['min_length'] = 'LENGTH %(length)s, MIN LENGTH %(min)s'
>>> e['max_length'] = 'LENGTH %(length)s, MAX LENGTH %(max)s'
>>> f = CharField(min_length=5, max_length=10, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('1234')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 4, MIN LENGTH 5']
>>> f.clean('12345678901')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 11, MAX LENGTH 10']

# IntegerField ################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['min_value'] = 'MIN VALUE IS %s'
>>> e['max_value'] = 'MAX VALUE IS %s'
>>> f = IntegerField(min_value=5, max_value=10, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('4')
Traceback (most recent call last):
...
ValidationError: [u'MIN VALUE IS 5']
>>> f.clean('11')
Traceback (most recent call last):
...
ValidationError: [u'MAX VALUE IS 10']

# FloatField ##################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['min_value'] = 'MIN VALUE IS %s'
>>> e['max_value'] = 'MAX VALUE IS %s'
>>> f = FloatField(min_value=5, max_value=10, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('4')
Traceback (most recent call last):
...
ValidationError: [u'MIN VALUE IS 5']
>>> f.clean('11')
Traceback (most recent call last):
...
ValidationError: [u'MAX VALUE IS 10']

# DecimalField ################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['min_value'] = 'MIN VALUE IS %s'
>>> e['max_value'] = 'MAX VALUE IS %s'
>>> e['max_digits'] = 'MAX DIGITS IS %s'
>>> e['max_decimal_places'] = 'MAX DP IS %s'
>>> e['max_whole_digits'] = 'MAX DIGITS BEFORE DP IS %s'
>>> f = DecimalField(min_value=5, max_value=10, error_messages=e)
>>> f2 = DecimalField(max_digits=4, decimal_places=2, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('4')
Traceback (most recent call last):
...
ValidationError: [u'MIN VALUE IS 5']
>>> f.clean('11')
Traceback (most recent call last):
...
ValidationError: [u'MAX VALUE IS 10']
>>> f2.clean('123.45')
Traceback (most recent call last):
...
ValidationError: [u'MAX DIGITS IS 4']
>>> f2.clean('1.234')
Traceback (most recent call last):
...
ValidationError: [u'MAX DP IS 2']
>>> f2.clean('123.4')
Traceback (most recent call last):
...
ValidationError: [u'MAX DIGITS BEFORE DP IS 2']

# DateField ###################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> f = DateField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']

# TimeField ###################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> f = TimeField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']

# DateTimeField ###############################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> f = DateTimeField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']

# RegexField ##################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['min_length'] = 'LENGTH %(length)s, MIN LENGTH %(min)s'
>>> e['max_length'] = 'LENGTH %(length)s, MAX LENGTH %(max)s'
>>> f = RegexField(r'^\d+$', min_length=5, max_length=10, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abcde')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('1234')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 4, MIN LENGTH 5']
>>> f.clean('12345678901')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 11, MAX LENGTH 10']

# EmailField ##################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['min_length'] = 'LENGTH %(length)s, MIN LENGTH %(min)s'
>>> e['max_length'] = 'LENGTH %(length)s, MAX LENGTH %(max)s'
>>> f = EmailField(min_length=8, max_length=10, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abcdefgh')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('a@b.com')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 7, MIN LENGTH 8']
>>> f.clean('aye@bee.com')
Traceback (most recent call last):
...
ValidationError: [u'LENGTH 11, MAX LENGTH 10']

# FileField ##################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['missing'] = 'MISSING'
>>> e['empty'] = 'EMPTY FILE'
>>> f = FileField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean({})
Traceback (most recent call last):
...
ValidationError: [u'MISSING']
>>> f.clean({'filename': 'name', 'content':''})
Traceback (most recent call last):
...
ValidationError: [u'EMPTY FILE']

# URLField ##################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID'
>>> e['invalid_link'] = 'INVALID LINK'
>>> f = URLField(verify_exists=True, error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('abc.c')
Traceback (most recent call last):
...
ValidationError: [u'INVALID']
>>> f.clean('http://www.jfoiwjfoi23jfoijoaijfoiwjofiwjefewl.com')
Traceback (most recent call last):
...
ValidationError: [u'INVALID LINK']

# BooleanField ################################################################

>>> e = {'required': 'REQUIRED'}
>>> f = BooleanField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']

# ChoiceField #################################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid_choice'] = '%(value)s IS INVALID CHOICE'
>>> f = ChoiceField(choices=[('a', 'aye')], error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('b')
Traceback (most recent call last):
...
ValidationError: [u'b IS INVALID CHOICE']

# MultipleChoiceField #########################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid_choice'] = '%(value)s IS INVALID CHOICE'
>>> e['invalid_list'] = 'NOT A LIST'
>>> f = MultipleChoiceField(choices=[('a', 'aye')], error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('b')
Traceback (most recent call last):
...
ValidationError: [u'NOT A LIST']
>>> f.clean(['b'])
Traceback (most recent call last):
...
ValidationError: [u'b IS INVALID CHOICE']

# SplitDateTimeField ##########################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid_date'] = 'INVALID DATE'
>>> e['invalid_time'] = 'INVALID TIME'
>>> f = SplitDateTimeField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean(['a', 'b'])
Traceback (most recent call last):
...
ValidationError: [u'INVALID DATE', u'INVALID TIME']

# IPAddressField ##############################################################

>>> e = {'required': 'REQUIRED'}
>>> e['invalid'] = 'INVALID IP ADDRESS'
>>> f = IPAddressField(error_messages=e)
>>> f.clean('')
Traceback (most recent call last):
...
ValidationError: [u'REQUIRED']
>>> f.clean('127.0.0')
Traceback (most recent call last):
...
ValidationError: [u'INVALID IP ADDRESS']
"""
