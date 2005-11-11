from django.core import meta
from django.models.core import Site
from django.utils.translation import gettext_lazy as _

class Redirect(meta.Model):
    site = meta.ForeignKey(Site, radio_admin=meta.VERTICAL)
    old_path = meta.CharField(_('redirect from'), maxlength=200, db_index=True,
        help_text=_("This should be an absolute path, excluding the domain name. Example: '/events/search/'."))
    new_path = meta.CharField(_('redirect to'), maxlength=200, blank=True,
        help_text=_("This can be either an absolute path (as above) or a full URL starting with 'http://'."))
    class META:
        verbose_name = _('redirect')
        verbose_name_plural = _('redirects')
        db_table = 'django_redirects'
        unique_together=(('site', 'old_path'),)
        ordering = ('old_path',)
        admin = meta.Admin(
            list_filter = ('site',),
            search_fields = ('old_path', 'new_path'),
        )

    def __repr__(self):
        return "%s ---> %s" % (self.old_path, self.new_path)
