# -*- coding: utf-8 -*-

r"""
>>> floatformat(7.7)
u'7.7'
>>> floatformat(7.0)
u'7'
>>> floatformat(0.7)
u'0.7'
>>> floatformat(0.07)
u'0.1'
>>> floatformat(0.007)
u'0.0'
>>> floatformat(0.0)
u'0'
>>> floatformat(7.7,3)
u'7.700'
>>> floatformat(6.000000,3)
u'6.000'
>>> floatformat(13.1031,-3)
u'13.103'
>>> floatformat(11.1197, -2)
u'11.12'
>>> floatformat(11.0000, -2)
u'11'
>>> floatformat(11.000001, -2)
u'11.00'
>>> floatformat(8.2798, 3)
u'8.280'
>>> floatformat(u'foo')
u''
>>> floatformat(13.1031, u'bar')
u'13.1031'
>>> floatformat(u'foo', u'bar')
u''

>>> addslashes(u'"double quotes" and \'single quotes\'')
u'\\"double quotes\\" and \\\'single quotes\\\''

>>> addslashes(ur'\ : backslashes, too')
u'\\\\ : backslashes, too'

>>> capfirst(u'hello world')
u'Hello world'

>>> fix_ampersands(u'Jack & Jill & Jeroboam')
u'Jack &amp; Jill &amp; Jeroboam'

>>> linenumbers(u'line 1\nline 2')
u'1. line 1\n2. line 2'

>>> linenumbers(u'\n'.join([u'x'] * 10))
u'01. x\n02. x\n03. x\n04. x\n05. x\n06. x\n07. x\n08. x\n09. x\n10. x'

>>> lower('TEST')
u'test'

>>> lower(u'\xcb') # uppercase E umlaut
u'\xeb'

>>> make_list('abc')
[u'a', u'b', u'c']

>>> make_list(1234)
[u'1', u'2', u'3', u'4']

>>> slugify(' Jack & Jill like numbers 1,2,3 and 4 and silly characters ?%.$!/')
u'jack-jill-like-numbers-123-and-4-and-silly-characters'

>>> slugify(u"Un \xe9l\xe9phant \xe0 l'or\xe9e du bois")
u'un-elephant-a-loree-du-bois'

>>> stringformat(1, u'03d')
u'001'

>>> stringformat(1, u'z')
u''

>>> title('a nice title, isn\'t it?')
u"A Nice Title, Isn't It?"

>>> title(u'discoth\xe8que')
u'Discoth\xe8que'

>>> truncatewords(u'A sentence with a few words in it', 1)
u'A ...'

>>> truncatewords(u'A sentence with a few words in it', 5)
u'A sentence with a few ...'

>>> truncatewords(u'A sentence with a few words in it', 100)
u'A sentence with a few words in it'

>>> truncatewords(u'A sentence with a few words in it', 'not a number')
u'A sentence with a few words in it'

>>> truncatewords_html(u'<p>one <a href="#">two - three <br>four</a> five</p>', 0)
u''

>>> truncatewords_html(u'<p>one <a href="#">two - three <br>four</a> five</p>', 2)
u'<p>one <a href="#">two ...</a></p>'

>>> truncatewords_html(u'<p>one <a href="#">two - three <br>four</a> five</p>', 4)
u'<p>one <a href="#">two - three <br>four ...</a></p>'

>>> truncatewords_html(u'<p>one <a href="#">two - three <br>four</a> five</p>', 5)
u'<p>one <a href="#">two - three <br>four</a> five</p>'

>>> truncatewords_html(u'<p>one <a href="#">two - three <br>four</a> five</p>', 100)
u'<p>one <a href="#">two - three <br>four</a> five</p>'

>>> truncatewords_html(u'\xc5ngstr\xf6m was here', 1)
u'\xc5ngstr\xf6m ...'

>>> upper(u'Mixed case input')
u'MIXED CASE INPUT'

>>> upper(u'\xeb') # lowercase e umlaut
u'\xcb'


>>> urlencode(u'fran\xe7ois & jill')
u'fran%C3%A7ois%20%26%20jill'
>>> urlencode(1)
u'1'
>>> iriencode(u'S\xf8r-Tr\xf8ndelag')
u'S%C3%B8r-Tr%C3%B8ndelag'
>>> iriencode(urlencode(u'fran\xe7ois & jill'))
u'fran%C3%A7ois%20%26%20jill'

>>> urlizetrunc(u'http://short.com/', 20)
u'<a href="http://short.com/" rel="nofollow">http://short.com/</a>'

>>> urlizetrunc(u'http://www.google.co.uk/search?hl=en&q=some+long+url&btnG=Search&meta=', 20)
u'<a href="http://www.google.co.uk/search?hl=en&q=some+long+url&btnG=Search&meta=" rel="nofollow">http://www.google....</a>'

>>> urlizetrunc('http://www.google.co.uk/search?hl=en&q=some+long+url&btnG=Search&meta=', 20)
u'<a href="http://www.google.co.uk/search?hl=en&q=some+long+url&btnG=Search&meta=" rel="nofollow">http://www.google...</a>'

# Check truncating of URIs which are the exact length
>>> uri = 'http://31characteruri.com/test/'
>>> len(uri)
31
>>> urlizetrunc(uri, 31)
u'<a href="http://31characteruri.com/test/" rel="nofollow">http://31characteruri.com/test/</a>'
>>> urlizetrunc(uri, 30)
u'<a href="http://31characteruri.com/test/" rel="nofollow">http://31characteruri.com/t...</a>'
>>> urlizetrunc(uri, 2)
u'<a href="http://31characteruri.com/test/" rel="nofollow">...</a>'

>>> wordcount('')
0

>>> wordcount(u'oneword')
1

>>> wordcount(u'lots of words')
3

>>> wordwrap(u'this is a long paragraph of text that really needs to be wrapped I\'m afraid', 14)
u"this is a long\nparagraph of\ntext that\nreally needs\nto be wrapped\nI'm afraid"

>>> wordwrap(u'this is a short paragraph of text.\n  But this line should be indented',14)
u'this is a\nshort\nparagraph of\ntext.\n  But this\nline should be\nindented'

>>> wordwrap(u'this is a short paragraph of text.\n  But this line should be indented',15)
u'this is a short\nparagraph of\ntext.\n  But this line\nshould be\nindented'

>>> ljust(u'test', 10)
u'test      '

>>> ljust(u'test', 3)
u'test'

>>> rjust(u'test', 10)
u'      test'

>>> rjust(u'test', 3)
u'test'

>>> center(u'test', 6)
u' test '

>>> cut(u'a string to be mangled', 'a')
u' string to be mngled'

>>> cut(u'a string to be mangled', 'ng')
u'a stri to be maled'

>>> cut(u'a string to be mangled', 'strings')
u'a string to be mangled'

>>> escape(u'<some html & special characters > here')
u'&lt;some html &amp; special characters &gt; here'

>>> escape(u'<some html & special characters > here ĐÅ€£')
u'&lt;some html &amp; special characters &gt; here \xc4\x90\xc3\x85\xe2\x82\xac\xc2\xa3'

>>> linebreaks(u'line 1')
u'<p>line 1</p>'

>>> linebreaks(u'line 1\nline 2')
u'<p>line 1<br />line 2</p>'

>>> removetags(u'some <b>html</b> with <script>alert("You smell")</script> disallowed <img /> tags', 'script img')
u'some <b>html</b> with alert("You smell") disallowed  tags'

>>> striptags(u'some <b>html</b> with <script>alert("You smell")</script> disallowed <img /> tags')
u'some html with alert("You smell") disallowed  tags'

>>> dictsort([{'age': 23, 'name': 'Barbara-Ann'},
...           {'age': 63, 'name': 'Ra Ra Rasputin'},
...           {'name': 'Jonny B Goode', 'age': 18}], 'age')
[{'age': 18, 'name': 'Jonny B Goode'}, {'age': 23, 'name': 'Barbara-Ann'}, {'age': 63, 'name': 'Ra Ra Rasputin'}]

>>> dictsortreversed([{'age': 23, 'name': 'Barbara-Ann'},
...           {'age': 63, 'name': 'Ra Ra Rasputin'},
...           {'name': 'Jonny B Goode', 'age': 18}], 'age')
[{'age': 63, 'name': 'Ra Ra Rasputin'}, {'age': 23, 'name': 'Barbara-Ann'}, {'age': 18, 'name': 'Jonny B Goode'}]

>>> first([0,1,2])
0

>>> first(u'')
u''

>>> first(u'test')
u't'

>>> join([0,1,2], u'glue')
u'0glue1glue2'

>>> length(u'1234')
4

>>> length([1,2,3,4])
4

>>> length_is([], 0)
True

>>> length_is([], 1)
False

>>> length_is('a', 1)
True

>>> length_is(u'a', 10)
False

>>> slice_(u'abcdefg', u'0')
u''

>>> slice_(u'abcdefg', u'1')
u'a'

>>> slice_(u'abcdefg', u'-1')
u'abcdef'

>>> slice_(u'abcdefg', u'1:2')
u'b'

>>> slice_(u'abcdefg', u'1:3')
u'bc'

>>> slice_(u'abcdefg', u'0::2')
u'aceg'

>>> unordered_list([u'item 1', u'item 2'])
u'\t<li>item 1</li>\n\t<li>item 2</li>'

>>> unordered_list([u'item 1', [u'item 1.1']])
u'\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t</ul>\n\t</li>'

>>> unordered_list([u'item 1', [u'item 1.1', u'item1.2'], u'item 2'])
u'\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t\t<li>item1.2</li>\n\t</ul>\n\t</li>\n\t<li>item 2</li>'

>>> unordered_list([u'item 1', [u'item 1.1', [u'item 1.1.1', [u'item 1.1.1.1']]]])
u'\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1\n\t\t<ul>\n\t\t\t<li>item 1.1.1\n\t\t\t<ul>\n\t\t\t\t<li>item 1.1.1.1</li>\n\t\t\t</ul>\n\t\t\t</li>\n\t\t</ul>\n\t\t</li>\n\t</ul>\n\t</li>'

>>> unordered_list(['States', ['Kansas', ['Lawrence', 'Topeka'], 'Illinois']])
u'\t<li>States\n\t<ul>\n\t\t<li>Kansas\n\t\t<ul>\n\t\t\t<li>Lawrence</li>\n\t\t\t<li>Topeka</li>\n\t\t</ul>\n\t\t</li>\n\t\t<li>Illinois</li>\n\t</ul>\n\t</li>'

# Old format for unordered lists should still work
>>> unordered_list([u'item 1', []])
u'\t<li>item 1</li>'

>>> unordered_list([u'item 1', [[u'item 1.1', []]]])
u'\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t</ul>\n\t</li>'

>>> unordered_list([u'item 1', [[u'item 1.1', []], [u'item 1.2', []]]])
u'\t<li>item 1\n\t<ul>\n\t\t<li>item 1.1</li>\n\t\t<li>item 1.2</li>\n\t</ul>\n\t</li>'

>>> unordered_list(['States', [['Kansas', [['Lawrence', []], ['Topeka', []]]], ['Illinois', []]]])
u'\t<li>States\n\t<ul>\n\t\t<li>Kansas\n\t\t<ul>\n\t\t\t<li>Lawrence</li>\n\t\t\t<li>Topeka</li>\n\t\t</ul>\n\t\t</li>\n\t\t<li>Illinois</li>\n\t</ul>\n\t</li>'

>>> add(u'1', u'2')
3

>>> get_digit(123, 1)
3

>>> get_digit(123, 2)
2

>>> get_digit(123, 3)
1

>>> get_digit(123, 4)
0

>>> get_digit(123, 0)
123

>>> get_digit(u'xyz', 0)
u'xyz'

# real testing of date() is in dateformat.py
>>> date(datetime.datetime(2005, 12, 29), u"d F Y")
u'29 December 2005'
>>> date(datetime.datetime(2005, 12, 29), ur'jS o\f F')
u'29th of December'

# real testing of time() is done in dateformat.py
>>> time(datetime.time(13), u"h")
u'01'

>>> time(datetime.time(0), u"h")
u'12'

# real testing is done in timesince.py, where we can provide our own 'now'
>>> timesince(datetime.datetime.now() - datetime.timedelta(1))
u'1 day'

>>> default(u"val", u"default")
u'val'

>>> default(None, u"default")
u'default'

>>> default(u'', u"default")
u'default'

>>> default_if_none(u"val", u"default")
u'val'

>>> default_if_none(None, u"default")
u'default'

>>> default_if_none(u'', u"default")
u''

>>> divisibleby(4, 2)
True

>>> divisibleby(4, 3)
False

>>> yesno(True)
u'yes'

>>> yesno(False)
u'no'

>>> yesno(None)
u'maybe'

>>> yesno(True, u'certainly,get out of town,perhaps')
u'certainly'

>>> yesno(False, u'certainly,get out of town,perhaps')
u'get out of town'

>>> yesno(None, u'certainly,get out of town,perhaps')
u'perhaps'

>>> yesno(None, u'certainly,get out of town')
u'get out of town'

>>> filesizeformat(1023)
u'1023 bytes'

>>> filesizeformat(1024)
u'1.0 KB'

>>> filesizeformat(10*1024)
u'10.0 KB'

>>> filesizeformat(1024*1024-1)
u'1024.0 KB'

>>> filesizeformat(1024*1024)
u'1.0 MB'

>>> filesizeformat(1024*1024*50)
u'50.0 MB'

>>> filesizeformat(1024*1024*1024-1)
u'1024.0 MB'

>>> filesizeformat(1024*1024*1024)
u'1.0 GB'

>>> pluralize(1)
u''

>>> pluralize(0)
u's'

>>> pluralize(2)
u's'

>>> pluralize([1])
u''

>>> pluralize([])
u's'

>>> pluralize([1,2,3])
u's'

>>> pluralize(1,u'es')
u''

>>> pluralize(0,u'es')
u'es'

>>> pluralize(2,u'es')
u'es'

>>> pluralize(1,u'y,ies')
u'y'

>>> pluralize(0,u'y,ies')
u'ies'

>>> pluralize(2,u'y,ies')
u'ies'

>>> pluralize(0,u'y,ies,error')
u''

>>> phone2numeric(u'0800 flowers')
u'0800 3569377'

# Filters shouldn't break if passed non-strings
>>> addslashes(123)
u'123'
>>> linenumbers(123)
u'1. 123'
>>> lower(123)
u'123'
>>> make_list(123)
[u'1', u'2', u'3']
>>> slugify(123)
u'123'
>>> title(123)
u'123'
>>> truncatewords(123, 2)
u'123'
>>> upper(123)
u'123'
>>> urlencode(123)
u'123'
>>> urlize(123)
u'123'
>>> urlizetrunc(123, 1)
u'123'
>>> wordcount(123)
1
>>> wordwrap(123, 2)
u'123'
>>> ljust('123', 4)
u'123 '
>>> rjust('123', 4)
u' 123'
>>> center('123', 5)
u' 123 '
>>> center('123', 6)
u' 123  '
>>> cut(123, '2')
u'13'
>>> escape(123)
u'123'
>>> linebreaks(123)
u'<p>123</p>'
>>> linebreaksbr(123)
u'123'
>>> removetags(123, 'a')
u'123'
>>> striptags(123)
u'123'

"""

from django.template.defaultfilters import *
import datetime

if __name__ == '__main__':
    import doctest
    doctest.testmod()
