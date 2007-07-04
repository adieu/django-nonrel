from django.db import models

class Animal(models.Model):
    name = models.CharField(maxlength=150)
    latin_name = models.CharField(maxlength=150)

    def __unicode__(self):
        return self.common_name

class Plant(models.Model):
    name = models.CharField(maxlength=150)

    class Meta:
        # For testing when upper case letter in app name; regression for #4057
        db_table = "Fixtures_regress_plant"

__test__ = {'API_TESTS':"""
>>> from django.core import management

# Load a fixture that uses PK=1
>>> management.load_data(['sequence'], verbosity=0)
        
# Create a new animal. Without a sequence reset, this new object
# will take a PK of 1 (on Postgres), and the save will fail.
# This is a regression test for ticket #3790.
>>> animal = Animal(name='Platypus', latin_name='Ornithorhynchus anatinus')
>>> animal.save()

"""}
