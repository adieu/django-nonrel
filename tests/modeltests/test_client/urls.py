from django.conf.urls.defaults import *
import views

urlpatterns = patterns('',
    (r'^no_template_view/$', views.no_template_view),
    (r'^get_view/$', views.get_view),
    (r'^post_view/$', views.post_view),
    (r'^raw_post_view/$', views.raw_post_view),
    (r'^redirect_view/$', views.redirect_view),
    (r'^form_view/$', views.form_view),
    (r'^form_view_with_template/$', views.form_view_with_template),
    (r'^login_protected_view/$', views.login_protected_view),
    (r'^session_view/$', views.session_view),
    (r'^broken_view/$', views.broken_view),
    (r'^mail_sending_view/$', views.mail_sending_view),
    (r'^mass_mail_sending_view/$', views.mass_mail_sending_view)
)
