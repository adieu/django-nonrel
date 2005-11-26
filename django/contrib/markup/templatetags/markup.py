"""
Set of "markup" template filters for Django.  These filters transform plain text
markup syntaxes to HTML; currently there is support for:

    * Textile, which requires the PyTextile library available at
      http://dealmeida.net/projects/textile/

    * Markdown, which requires the Python-markdown library from
      http://www.freewisdom.org/projects/python-markdown

    * ReStructuredText, which requires docutils from http://docutils.sf.net/

In each case, if the required library is not installed, the filter will
silently fail and return the un-marked-up text.
"""

from django.core import template

register = template.Library()

def textile(value):
    try:
        import textile
    except ImportError:
        return value
    else:
        return textile.textile(value)

def markdown(value):
    try:
        import markdown
    except ImportError:
        return value
    else:
        return markdown.markdown(value)

def restructuredtext(value):
    try:
        from docutils.core import publish_parts
    except ImportError:
        return value
    else:
        parts = publish_parts(source=value, writer_name="html4css1")
        return parts["fragment"]

register.filter(textile)
register.filter(markdown)
register.filter(restructuredtext)
