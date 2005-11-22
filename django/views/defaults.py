from django.core.exceptions import Http404, ObjectDoesNotExist
from django.core.template import Context, loader
from django.models.core import sites, contenttypes
from django.utils import httpwrappers

def shortcut(request, content_type_id, object_id):
    "Redirect to an object's page based on a content-type ID and an object ID."
    # Look up the object, making sure it's got a get_absolute_url() function.
    try:
        content_type = contenttypes.get_object(pk=content_type_id)
        obj = content_type.get_object_for_this_type(pk=object_id)
    except ObjectDoesNotExist:
        raise Http404, "Content type %s object %s doesn't exist" % (content_type_id, object_id)
    try:
        absurl = obj.get_absolute_url()
    except AttributeError:
        raise Http404, "%s objects don't have get_absolute_url() methods" % content_type.name

    # Try to figure out the object's domain, so we can do a cross-site redirect
    # if necessary.

    # If the object actually defines a domain, we're done.
    if absurl.startswith('http://'):
        return httpwrappers.HttpResponseRedirect(absurl)

    object_domain = None

    # Next, look for an many-to-many relationship to sites
    if hasattr(obj, 'get_site_list'):
        site_list = obj.get_site_list()
        if site_list:
            object_domain = site_list[0].domain

    # Next, look for a many-to-one relationship to sites
    elif hasattr(obj, 'get_site'):
        try:
            object_domain = obj.get_site().domain
        except sites.SiteDoesNotExist:
            pass

    # Then, fall back to the current site (if possible)
    else:
        try:
            object_domain = sites.get_current().domain
        except sites.SiteDoesNotExist:
            # Finally, give up and use a URL without the domain name
            return httpwrappers.HttpResponseRedirect(obj.get_absolute_url())
    return httpwrappers.HttpResponseRedirect('http://%s%s' % (object_domain, obj.get_absolute_url()))

def page_not_found(request, template_name='404'):
    """
    Default 404 handler, which looks for the requested URL in the redirects
    table, redirects if found, and displays 404 page if not redirected.

    Templates: `404`
    Context: None
    """
    t = loader.get_template(template_name)
    return httpwrappers.HttpResponseNotFound(t.render(Context()))

def server_error(request, template_name='500'):
    """
    500 error handler.

    Templates: `500`
    Context: None
    """
    t = loader.get_template(template_name)
    return httpwrappers.HttpResponseServerError(t.render(Context()))
