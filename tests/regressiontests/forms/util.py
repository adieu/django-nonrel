# coding: utf-8
"""
Tests for newforms/util.py module.
"""

util_tests = r"""
>>> from django.newforms.util import *
>>> from django.utils.translation import ugettext_lazy

###################
# ValidationError #
###################

# Can take a string.
>>> print ValidationError("There was an error.").messages
<ul class="errorlist"><li>There was an error.</li></ul>

# Can take a unicode string.
>>> print ValidationError(u"Not \u03C0.").messages
<ul class="errorlist"><li>Not π.</li></ul>

# Can take a lazy string.
>>> print ValidationError(ugettext_lazy("Error.")).messages
<ul class="errorlist"><li>Error.</li></ul>

# Can take a list.
>>> print ValidationError(["Error one.", "Error two."]).messages
<ul class="errorlist"><li>Error one.</li><li>Error two.</li></ul>

# Can take a mixture in a list.
>>> print ValidationError(["First error.", u"Not \u03C0.", ugettext_lazy("Error.")]).messages
<ul class="errorlist"><li>First error.</li><li>Not π.</li><li>Error.</li></ul>
"""
