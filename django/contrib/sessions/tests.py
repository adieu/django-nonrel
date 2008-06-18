r"""

>>> from django.conf import settings
>>> from django.contrib.sessions.backends.db import SessionStore as DatabaseSession
>>> from django.contrib.sessions.backends.cache import SessionStore as CacheSession
>>> from django.contrib.sessions.backends.file import SessionStore as FileSession
>>> from django.contrib.sessions.backends.base import SessionBase

>>> db_session = DatabaseSession()
>>> db_session.modified
False
>>> db_session['cat'] = "dog"
>>> db_session.modified
True
>>> db_session.pop('cat')
'dog'
>>> db_session.pop('some key', 'does not exist')
'does not exist'
>>> db_session.save()
>>> db_session.exists(db_session.session_key)
True
>>> db_session.delete(db_session.session_key)
>>> db_session.exists(db_session.session_key)
False

>>> file_session = FileSession()
>>> file_session.modified
False
>>> file_session['cat'] = "dog"
>>> file_session.modified
True
>>> file_session.pop('cat')
'dog'
>>> file_session.pop('some key', 'does not exist')
'does not exist'
>>> file_session.save()
>>> file_session.exists(file_session.session_key)
True
>>> file_session.delete(file_session.session_key)
>>> file_session.exists(file_session.session_key)
False

# Make sure the file backend checks for a good storage dir
>>> settings.SESSION_FILE_PATH = "/if/this/directory/exists/you/have/a/weird/computer"
>>> FileSession()
Traceback (innermost last):
    ...
ImproperlyConfigured: The session storage path '/if/this/directory/exists/you/have/a/weird/computer' doesn't exist. Please set your SESSION_FILE_PATH setting to an existing directory in which Django can store session data.

>>> cache_session = CacheSession()
>>> cache_session.modified
False
>>> cache_session['cat'] = "dog"
>>> cache_session.modified
True
>>> cache_session.pop('cat')
'dog'
>>> cache_session.pop('some key', 'does not exist')
'does not exist'
>>> cache_session.save()
>>> cache_session.delete(cache_session.session_key)
>>> cache_session.exists(cache_session.session_key)
False

>>> s = SessionBase()
>>> s._session['some key'] = 'exists' # Pre-populate the session with some data
>>> s.accessed = False   # Reset to pretend this wasn't accessed previously

>>> s.accessed, s.modified
(False, False)

>>> s.pop('non existant key', 'does not exist')
'does not exist'
>>> s.accessed, s.modified
(True, False)

>>> s.setdefault('foo', 'bar')
'bar'
>>> s.setdefault('foo', 'baz')
'bar'

>>> s.accessed = False  # Reset the accessed flag

>>> s.pop('some key')
'exists'
>>> s.accessed, s.modified
(True, True)

>>> s.pop('some key', 'does not exist')
'does not exist'


>>> s.get('update key', None)

# test .update()
>>> s.modified = s.accessed = False   # Reset to pretend this wasn't accessed previously
>>> s.update({'update key':1})
>>> s.accessed, s.modified
(True, True)
>>> s.get('update key', None)
1

# test .has_key()
>>> s.modified = s.accessed = False   # Reset to pretend this wasn't accessed previously
>>> s.has_key('update key')
True
>>> s.accessed, s.modified
(True, False)

# test .values()
>>> s = SessionBase()
>>> s.values()
[]
>>> s.accessed
True
>>> s['x'] = 1
>>> s.values()
[1]

# test .iterkeys()
>>> s.accessed = False
>>> i = s.iterkeys()
>>> hasattr(i,'__iter__')
True
>>> s.accessed
True
>>> list(i)
['x']

# test .itervalues()
>>> s.accessed = False
>>> i = s.itervalues()
>>> hasattr(i,'__iter__')
True
>>> s.accessed
True
>>> list(i)
[1]

# test .iteritems()
>>> s.accessed = False
>>> i = s.iteritems()
>>> hasattr(i,'__iter__')
True
>>> s.accessed
True
>>> list(i)
[('x', 1)]

 

#########################
# Custom session expiry #
#########################

>>> from django.conf import settings
>>> from datetime import datetime, timedelta

>>> td10 = timedelta(seconds=10)

# A normal session has a max age equal to settings
>>> s.get_expiry_age() == settings.SESSION_COOKIE_AGE
True

# So does a custom session with an idle expiration time of 0 (but it'll expire
# at browser close)
>>> s.set_expiry(0)
>>> s.get_expiry_age() == settings.SESSION_COOKIE_AGE
True

# Custom session idle expiration time
>>> s.set_expiry(10)
>>> delta = s.get_expiry_date() - datetime.now()
>>> delta.seconds in (9, 10)
True
>>> age = s.get_expiry_age()
>>> age in (9, 10)
True

# Custom session fixed expiry date (timedelta)
>>> s.set_expiry(td10)
>>> delta = s.get_expiry_date() - datetime.now()
>>> delta.seconds in (9, 10)
True
>>> age = s.get_expiry_age()
>>> age in (9, 10)
True

# Custom session fixed expiry date (fixed datetime)
>>> s.set_expiry(datetime.now() + td10)
>>> delta = s.get_expiry_date() - datetime.now()
>>> delta.seconds in (9, 10)
True
>>> age = s.get_expiry_age()
>>> age in (9, 10)
True

# Set back to default session age
>>> s.set_expiry(None)
>>> s.get_expiry_age() == settings.SESSION_COOKIE_AGE
True

# Allow to set back to default session age even if no alternate has been set
>>> s.set_expiry(None)


# We're changing the setting then reverting back to the original setting at the
# end of these tests.
>>> original_expire_at_browser_close = settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
>>> settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Custom session age
>>> s.set_expiry(10)
>>> s.get_expire_at_browser_close()
False

# Custom expire-at-browser-close
>>> s.set_expiry(0)
>>> s.get_expire_at_browser_close()
True

# Default session age
>>> s.set_expiry(None)
>>> s.get_expire_at_browser_close()
False

>>> settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Custom session age
>>> s.set_expiry(10)
>>> s.get_expire_at_browser_close()
False

# Custom expire-at-browser-close
>>> s.set_expiry(0)
>>> s.get_expire_at_browser_close()
True

# Default session age
>>> s.set_expiry(None)
>>> s.get_expire_at_browser_close()
True

>>> settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = original_expire_at_browser_close
"""

if __name__ == '__main__':
    import doctest
    doctest.testmod()
