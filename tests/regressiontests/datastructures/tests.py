"""
# Tests for stuff in django.utils.datastructures.

>>> from django.utils.datastructures import *

### MergeDict #################################################################

>>> d1 = {'chris':'cool','camri':'cute','cotton':'adorable','tulip':'snuggable', 'twoofme':'firstone'}
>>> d2 = {'chris2':'cool2','camri2':'cute2','cotton2':'adorable2','tulip2':'snuggable2'}
>>> d3 = {'chris3':'cool3','camri3':'cute3','cotton3':'adorable3','tulip3':'snuggable3'}
>>> d4 = {'twoofme':'secondone'}
>>> md = MergeDict( d1,d2,d3 )
>>> md['chris']
'cool'
>>> md['camri']
'cute'
>>> md['twoofme']
'firstone'
>>> md2 = md.copy()
>>> md2['chris']
'cool'

### MultiValueDict ##########################################################

>>> d = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
>>> d['name']
'Simon'
>>> d.get('name')
'Simon'
>>> d.getlist('name')
['Adrian', 'Simon']
>>> d['lastname']
Traceback (most recent call last):
...
MultiValueDictKeyError: "Key 'lastname' not found in <MultiValueDict: {'position': ['Developer'], 'name': ['Adrian', 'Simon']}>"
>>> d.get('lastname')

>>> d.get('lastname', 'nonexistent')
'nonexistent'
>>> d.getlist('lastname')
[]
>>> d.setlist('lastname', ['Holovaty', 'Willison'])
>>> d.getlist('lastname')
['Holovaty', 'Willison']

### SortedDict #################################################################

>>> d = SortedDict()
>>> d['one'] = 'one'
>>> d['two'] = 'two'
>>> d['three'] = 'three'
>>> d['one']
'one'
>>> d['two']
'two'
>>> d['three']
'three'
>>> d.keys()
['one', 'two', 'three']
>>> d.values()
['one', 'two', 'three']
>>> d['one'] = 'not one'
>>> d['one']
'not one'
>>> d.keys() == d.copy().keys()
True
>>> print repr(d)
{'one': 'not one', 'two': 'two', 'three': 'three'}
>>> d.pop('one', 'missing')
'not one'
>>> d.pop('one', 'missing')
'missing'

We don't know which item will be popped in popitem(), so we'll just check that
the number of keys has decreased.
>>> l = len(d)
>>> _ = d.popitem()
>>> l - len(d)
1

Init from sequence of tuples
>>> d = SortedDict((
... (1, "one"),
... (0, "zero"),
... (2, "two")))
>>> print repr(d)
{1: 'one', 0: 'zero', 2: 'two'}

### DotExpandedDict ############################################################

>>> d = DotExpandedDict({'person.1.firstname': ['Simon'], 'person.1.lastname': ['Willison'], 'person.2.firstname': ['Adrian'], 'person.2.lastname': ['Holovaty']})
>>> d['person']['1']['lastname']
['Willison']
>>> d['person']['2']['lastname']
['Holovaty']
>>> d['person']['2']['firstname']
['Adrian']

### FileDict ################################################################

>>> d = FileDict({'content': 'once upon a time...'})
>>> repr(d)
"{'content': '<omitted>'}"
>>> d = FileDict({'other-key': 'once upon a time...'})
>>> repr(d)
"{'other-key': 'once upon a time...'}"
"""
