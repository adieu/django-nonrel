from django.forms.models import modelform_factory, inlineformset_factory
from django.test import TestCase

from models import User, UserSite, Restaurant, Manager

class InlineFormsetTests(TestCase):
    def test_formset_over_to_field(self):
        "A formset over a ForeignKey with a to_field can be saved. Regression for #10243"
        Form = modelform_factory(User)
        FormSet = inlineformset_factory(User, UserSite)

        # Instantiate the Form and FormSet to prove
        # you can create a form with no data
        form = Form()
        form_set = FormSet(instance=User())

        # Now create a new User and UserSite instance
        data = {
            'serial': u'1',
            'username': u'apollo13',
            'usersite_set-TOTAL_FORMS': u'1',
            'usersite_set-INITIAL_FORMS': u'0',
            'usersite_set-MAX_NUM_FORMS': u'0',
            'usersite_set-0-data': u'10',
            'usersite_set-0-user': u'apollo13'
        }
        user = User()
        form = Form(data)
        if form.is_valid():
            user = form.save()
        else:
            self.fail('Errors found on form:%s' % form_set)

        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.all().values()
            self.assertEqual(usersite[0]['data'], 10)
            self.assertEqual(usersite[0]['user_id'], u'apollo13')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

        # Now update the UserSite instance
        data = {
            'usersite_set-TOTAL_FORMS': u'1',
            'usersite_set-INITIAL_FORMS': u'1',
            'usersite_set-MAX_NUM_FORMS': u'0',
            'usersite_set-0-id': unicode(usersite[0]['id']),
            'usersite_set-0-data': u'11',
            'usersite_set-0-user': u'apollo13'
        }
        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.all().values()
            self.assertEqual(usersite[0]['data'], 11)
            self.assertEqual(usersite[0]['user_id'], u'apollo13')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

        # Now add a new UserSite instance
        data = {
            'usersite_set-TOTAL_FORMS': u'2',
            'usersite_set-INITIAL_FORMS': u'1',
            'usersite_set-MAX_NUM_FORMS': u'0',
            'usersite_set-0-id': unicode(usersite[0]['id']),
            'usersite_set-0-data': u'11',
            'usersite_set-0-user': u'apollo13',
            'usersite_set-1-data': u'42',
            'usersite_set-1-user': u'apollo13'
        }
        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.all().values().order_by('data')
            self.assertEqual(usersite[0]['data'], 11)
            self.assertEqual(usersite[0]['user_id'], u'apollo13')
            self.assertEqual(usersite[1]['data'], 42)
            self.assertEqual(usersite[1]['user_id'], u'apollo13')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

    def test_formset_over_inherited_model(self):
        "A formset over a ForeignKey with a to_field can be saved. Regression for #11120"
        Form = modelform_factory(Restaurant)
        FormSet = inlineformset_factory(Restaurant, Manager)

        # Instantiate the Form and FormSet to prove
        # you can create a form with no data
        form = Form()
        form_set = FormSet(instance=Restaurant())

        # Now create a new Restaurant and Manager instance
        data = {
            'name': u"Guido's House of Pasta",
            'manager_set-TOTAL_FORMS': u'1',
            'manager_set-INITIAL_FORMS': u'0',
            'manager_set-MAX_NUM_FORMS': u'0',
            'manager_set-0-name': u'Guido Van Rossum'
        }
        restaurant = User()
        form = Form(data)
        if form.is_valid():
            restaurant = form.save()
        else:
            self.fail('Errors found on form:%s' % form_set)

        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.all().values()
            self.assertEqual(manager[0]['name'], 'Guido Van Rossum')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

        # Now update the Manager instance
        data = {
            'manager_set-TOTAL_FORMS': u'1',
            'manager_set-INITIAL_FORMS': u'1',
            'manager_set-MAX_NUM_FORMS': u'0',
            'manager_set-0-id': unicode(manager[0]['id']),
            'manager_set-0-name': u'Terry Gilliam'
        }
        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.all().values()
            self.assertEqual(manager[0]['name'], 'Terry Gilliam')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

        # Now add a new Manager instance
        data = {
            'manager_set-TOTAL_FORMS': u'2',
            'manager_set-INITIAL_FORMS': u'1',
            'manager_set-MAX_NUM_FORMS': u'0',
            'manager_set-0-id': unicode(manager[0]['id']),
            'manager_set-0-name': u'Terry Gilliam',
            'manager_set-1-name': u'John Cleese'
        }
        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.all().values().order_by('name')
            self.assertEqual(manager[0]['name'], 'John Cleese')
            self.assertEqual(manager[1]['name'], 'Terry Gilliam')
        else:
            self.fail('Errors found on formset:%s' % form_set.errors)

    def test_formset_with_none_instance(self):
        "A formset with instance=None can be created. Regression for #11872"
        Form = modelform_factory(User)
        FormSet = inlineformset_factory(User, UserSite)

        # Instantiate the Form and FormSet to prove
        # you can create a formset with an instance of None
        form = Form(instance=None)
        formset = FormSet(instance=None)
