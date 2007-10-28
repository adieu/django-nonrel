# -*- coding: utf-8 -*-
from extra import tests as extra_tests
from fields import tests as fields_tests
from forms import tests as form_tests
from error_messages import tests as custom_error_message_tests
from localflavor.ar import tests as localflavor_ar_tests
from localflavor.au import tests as localflavor_au_tests
from localflavor.br import tests as localflavor_br_tests
from localflavor.ca import tests as localflavor_ca_tests
from localflavor.ch import tests as localflavor_ch_tests
from localflavor.cl import tests as localflavor_cl_tests
from localflavor.de import tests as localflavor_de_tests
from localflavor.es import tests as localflavor_es_tests
from localflavor.fi import tests as localflavor_fi_tests
from localflavor.fr import tests as localflavor_fr_tests
from localflavor.generic import tests as localflavor_generic_tests
from localflavor.is_ import tests as localflavor_is_tests
from localflavor.it import tests as localflavor_it_tests
from localflavor.jp import tests as localflavor_jp_tests
from localflavor.nl import tests as localflavor_nl_tests
from localflavor.pl import tests as localflavor_pl_tests
from localflavor.sk import tests as localflavor_sk_tests
from localflavor.uk import tests as localflavor_uk_tests
from localflavor.us import tests as localflavor_us_tests
from regressions import tests as regression_tests
from util import tests as util_tests
from widgets import tests as widgets_tests

__test__ = {
    'extra_tests': extra_tests,
    'fields_tests': fields_tests,
    'form_tests': form_tests,
    'custom_error_message_tests': custom_error_message_tests,
    'localflavor_ar_tests': localflavor_ar_tests,
    'localflavor_au_tests': localflavor_au_tests,
    'localflavor_br_tests': localflavor_br_tests,
    'localflavor_ca_tests': localflavor_ca_tests,
    'localflavor_ch_tests': localflavor_ch_tests,
    'localflavor_cl_tests': localflavor_cl_tests,
    'localflavor_de_tests': localflavor_de_tests,
    'localflavor_es_tests': localflavor_es_tests,
    'localflavor_fi_tests': localflavor_fi_tests,
    'localflavor_fr_tests': localflavor_fr_tests,
    'localflavor_generic_tests': localflavor_generic_tests,
    'localflavor_is_tests': localflavor_is_tests,
    'localflavor_it_tests': localflavor_it_tests,
    'localflavor_jp_tests': localflavor_jp_tests,
    'localflavor_nl_tests': localflavor_nl_tests,
    'localflavor_pl_tests': localflavor_pl_tests,
    'localflavor_sk_tests': localflavor_sk_tests,
    'localflavor_uk_tests': localflavor_uk_tests,
    'localflavor_us_tests': localflavor_us_tests,
    'regressions_tests': regression_tests,
    'util_tests': util_tests,
    'widgets_tests': widgets_tests,
}

if __name__ == "__main__":
    import doctest
    doctest.testmod()
