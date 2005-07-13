from django.utils import httpwrappers
from django.core import template_loader
from django.core.extensions import CMSContext as Context
from django.models.auth import sessions, users
from django.views.registration import passwords
import base64, md5
import cPickle as pickle

# secret used in pickled data to guard against tampering
TAMPER_SECRET = '09VJWE9_RIZZO_j0jwfe09j'

ERROR_MESSAGE = "Please enter a correct username and password. Note that both fields are case-sensitive."

class AdminUserRequired:
    """
    Admin middleware.  If this is enabled, access to the site will be granted only
    to valid users with the "is_staff" flag set.
    """

    def process_view(self, request, view_func, param_dict):
        """
        Make sure the user is logged in and is a valid admin user before
        allowing any access.

        Done at the view point because we need to know if we're running the
        password reset function.
        """

        # If this is the password reset view, we don't want to require login
        # Otherwise the password reset would need its own entry in the httpd
        # conf, which is a little uglier than this.
        if view_func == passwords.password_reset or view_func == passwords.password_reset_done:
            return

        # Check for a logged in, valid user
        if self.user_is_valid(request.user):
            return

        # If this isn't alreay the login page, display it
        if not request.POST.has_key('this_is_the_login_form'):
            if request.POST:
                message = "Please log in again, because your session has expired. "\
                          "Don't worry: Your submission has been saved."
            else:
                message = ""
            return self.display_login_form(request, message)

        # Check the password
        username = request.POST.get('username', '')
        try:
            user = users.get_object(username__exact=username)
        except users.UserDoesNotExist:
            message = ERROR_MESSAGE
            if '@' in username:
                # Mistakenly entered e-mail address instead of username? Look it up.
                try:
                    user = users.get_object(email__exact=username)
                except users.UserDoesNotExist:
                    message = "Usernames cannot contain the '@' character."
                else:
                    message = "Your e-mail address is not your username. Try '%s' instead." % user.username
            return self.display_login_form(request, message)

        # The user data is correct; log in the user in and continue
        else:
            if self.authenticate_user(user, request.POST.get('password', '')):
                if request.POST.has_key('post_data'):
                    post_data = decode_post_data(request.POST['post_data'])
                    if post_data and not post_data.has_key('this_is_the_login_form'):
                        # overwrite request.POST with the saved post_data, and continue
                        request.POST = post_data
                        request.user = user
                        request.session = sessions.create_session(user.id)
                        return
                    else:
                        response = httpwrappers.HttpResponseRedirect(request.path)
                        sessions.start_web_session(user.id, request, response)
                        return response
            else:
                return self.display_login_form(request, ERROR_MESSAGE)

    def display_login_form(self, request, error_message=''):
        if request.POST and request.POST.has_key('post_data'):
            # User has failed login BUT has previously saved 'post_data'
            post_data = request.POST['post_data']
        elif request.POST:
            # User's session must have expired; save their post data
            post_data = encode_post_data(request.POST)
        else:
            post_data = encode_post_data({})
        t = template_loader.get_template(self.get_login_template_name())
        c = Context(request, {
            'title': 'Log in',
            'app_path': request.path,
            'post_data': post_data,
            'error_message': error_message
        })
        return httpwrappers.HttpResponse(t.render(c))

    def authenticate_user(self, user, password):
        return user.check_password(password) and user.is_staff

    def user_is_valid(self, user):
        return not user.is_anonymous() and user.is_staff

    def get_login_template_name(self):
        return "login"

def encode_post_data(post_data):
    pickled = pickle.dumps(post_data)
    pickled_md5 = md5.new(pickled + TAMPER_SECRET).hexdigest()
    return base64.encodestring(pickled + pickled_md5)

def decode_post_data(encoded_data):
    encoded_data = base64.decodestring(encoded_data)
    pickled, tamper_check = encoded_data[:-32], encoded_data[-32:]
    if md5.new(pickled + TAMPER_SECRET).hexdigest() != tamper_check:
        from django.core.exceptions import SuspiciousOperation
        raise SuspiciousOperation, "User may have tampered with session cookie."
    return pickle.loads(pickled)
