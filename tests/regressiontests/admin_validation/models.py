"""
Tests of ModelAdmin validation logic.
"""

from django.db import models

class Album(models.Model):
    title = models.CharField(max_length=150)

class Song(models.Model):
    title = models.CharField(max_length=150)
    album = models.ForeignKey(Album)

    class Meta:
        ordering = ('title',)

    def __unicode__(self):
        return self.title

__test__ = {'API_TESTS':"""

>>> from django import forms
>>> from django.contrib import admin
>>> from django.contrib.admin.validation import validate

# Regression test for #8027: custom ModelForms with fields/fieldsets

>>> class SongForm(forms.ModelForm):
...     pass

>>> class ValidFields(admin.ModelAdmin):
...     form = SongForm
...     fields = ['title']

>>> class InvalidFields(admin.ModelAdmin):
...     form = SongForm
...     fields = ['spam']

>>> validate(ValidFields, Song)
>>> validate(InvalidFields, Song)
Traceback (most recent call last):
    ...
ImproperlyConfigured: 'InvalidFields.fields' refers to field 'spam' that is missing from the form.

# Regression test for #9932 - exclude in InlineModelAdmin
# should not contain the ForeignKey field used in ModelAdmin.model

>>> class SongInline(admin.StackedInline):
...     model = Song
...     exclude = ['album']

>>> class AlbumAdmin(admin.ModelAdmin):
...     model = Album
...     inlines = [SongInline]

>>> validate(AlbumAdmin, Album)
Traceback (most recent call last):
    ...
ImproperlyConfigured: SongInline cannot exclude the field 'album' - this is the foreign key to the parent model Album.

"""}
