from django.core import template_loader
from django.core.extensions import get_object_or_404, DjangoContext
from django.models.flatpages import flatpages
from django.utils.httpwrappers import HttpResponse
from django.conf.settings import SITE_ID

DEFAULT_TEMPLATE = 'flatpages/default'

def flatpage(request, url):
    """
    Flat page view.

    Models: `flatpages.flatpages`
    Templates: Uses the template defined by the ``template_name`` field,
        or `flatpages/default` if template_name is not defined.
    Context:
        flatpage
            `flatpages.flatpages` object
    """
    if not url.startswith('/'):
        url = "/" + url
    f = get_object_or_404(flatpages, url__exact=url, sites__id__exact=SITE_ID)
    # If registration is required for accessing this page, and the user isn't
    # logged in, redirect to the login page.
    if f.registration_required and request.user.is_anonymous():
        from django.views.auth.login import redirect_to_login
        return redirect_to_login(request.path)
    if f.template_name:
        t = template_loader.select_template((f.template_name, DEFAULT_TEMPLATE))
    else:
        t = template_loader.get_template(DEFAULT_TEMPLATE)
    c = DjangoContext(request, {
        'flatpage': f,
    })
    return HttpResponse(t.render(c))
