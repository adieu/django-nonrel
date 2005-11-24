from django.core import formfields, validators
from django.core.extensions import DjangoContext, render_to_response
from django.core.template import loader
from django.models.auth import users
from django.views.decorators.auth import login_required
from django.utils.httpwrappers import HttpResponseRedirect

class PasswordResetForm(formfields.Manipulator):
    "A form that lets a user request a password reset"
    def __init__(self):
        self.fields = (
            formfields.EmailField(field_name="email", length=40, is_required=True,
                validator_list=[self.isValidUserEmail]),
        )

    def isValidUserEmail(self, new_data, all_data):
        "Validates that a user exists with the given e-mail address"
        try:
            self.user_cache = users.get_object(email__iexact=new_data)
        except users.UserDoesNotExist:
            raise validators.ValidationError, "That e-mail address doesn't have an associated user acount. Are you sure you've registered?"

    def save(self, domain_override=None):
        "Calculates a new password randomly and sends it to the user"
        from django.core.mail import send_mail
        from django.models.core import sites
        new_pass = users.make_random_password()
        self.user_cache.set_password(new_pass)
        self.user_cache.save()
        if not domain_override:
            current_site = sites.get_current()
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override
        t = loader.get_template('registration/password_reset_email')
        c = {
            'new_password': new_pass,
            'email': self.user_cache.email,
            'domain': domain,
            'site_name': site_name,
            'user': self.user_cache,
        }
        send_mail('Password reset on %s' % site_name, t.render(Context(c)), None, [self.user_cache.email])

class PasswordChangeForm(formfields.Manipulator):
    "A form that lets a user change his password."
    def __init__(self, user):
        self.user = user
        self.fields = (
            formfields.PasswordField(field_name="old_password", length=30, maxlength=30, is_required=True,
                validator_list=[self.isValidOldPassword]),
            formfields.PasswordField(field_name="new_password1", length=30, maxlength=30, is_required=True,
                validator_list=[validators.AlwaysMatchesOtherField('new_password2', "The two 'new password' fields didn't match.")]),
            formfields.PasswordField(field_name="new_password2", length=30, maxlength=30, is_required=True),
        )

    def isValidOldPassword(self, new_data, all_data):
        "Validates that the old_password field is correct."
        if not self.user.check_password(new_data):
            raise validators.ValidationError, "Your old password was entered incorrectly. Please enter it again."

    def save(self, new_data):
        "Saves the new password."
        self.user.set_password(new_data['new_password1'])
        self.user.save()

def password_reset(request, is_admin_site=False):
    new_data, errors = {}, {}
    form = PasswordResetForm()
    if request.POST:
        new_data = request.POST.copy()
        errors = form.get_validation_errors(new_data)
        if not errors:
            if is_admin_site:
                form.save(request.META['HTTP_HOST'])
            else:
                form.save()
            return HttpResponseRedirect('%sdone/' % request.path)
    return render_to_response('registration/password_reset_form', {'form': formfields.FormWrapper(form, new_data, errors)},
        context_instance=DjangoContext(request))

def password_reset_done(request):
    return render_to_response('registration/password_reset_done', context_instance=DjangoContext(request))

def password_change(request):
    new_data, errors = {}, {}
    form = PasswordChangeForm(request.user)
    if request.POST:
        new_data = request.POST.copy()
        errors = form.get_validation_errors(new_data)
        if not errors:
            form.save(new_data)
            return HttpResponseRedirect('%sdone/' % request.path)
    return render_to_response('registration/password_change_form', {'form': formfields.FormWrapper(form, new_data, errors)},
        context_instance=DjangoContext(request))
password_change = login_required(password_change)

def password_change_done(request):
    return render_to_response('registration/password_change_done', context_instance=DjangoContext(request))
