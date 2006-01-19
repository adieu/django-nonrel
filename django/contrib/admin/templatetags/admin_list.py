from django.contrib.admin.views.main import MAX_SHOW_ALL_ALLOWED, DEFAULT_RESULTS_PER_PAGE, ALL_VAR
from django.contrib.admin.views.main import ORDER_VAR, ORDER_TYPE_VAR, PAGE_VAR, SEARCH_VAR
from django.contrib.admin.views.main import IS_POPUP_VAR, EMPTY_CHANGELIST_VALUE, MONTHS
from django.core import meta, template
from django.core.exceptions import ObjectDoesNotExist
from django.utils import dateformat
from django.utils.html import escape
from django.utils.text import capfirst
from django.utils.translation import get_date_formats
from django.conf.settings import ADMIN_MEDIA_PREFIX
from django.core.template import Library

register = Library()

DOT = '.'

def paginator_number(cl,i):
    if i == DOT:
       return '... '
    elif i == cl.page_num:
       return '<span class="this-page">%d</span> ' % (i+1)
    else:
       return '<a href="%s"%s>%d</a> ' % (cl.get_query_string({PAGE_VAR: i}), (i == cl.paginator.pages-1 and ' class="end"' or ''), i+1)
paginator_number = register.simple_tag(paginator_number)

def pagination(cl):
    paginator, page_num = cl.paginator, cl.page_num

    pagination_required = (not cl.show_all or not cl.can_show_all) and cl.multi_page
    if not pagination_required:
        page_range = []
    else:
        ON_EACH_SIDE = 3
        ON_ENDS = 2

        # If there are 10 or fewer pages, display links to every page.
        # Otherwise, do some fancy
        if paginator.pages <= 10:
            page_range = range(paginator.pages)
        else:
            # Insert "smart" pagination links, so that there are always ON_ENDS
            # links at either end of the list of pages, and there are always
            # ON_EACH_SIDE links at either end of the "current page" link.
            page_range = []
            if page_num > (ON_EACH_SIDE + ON_ENDS):
                page_range.extend(range(0, ON_EACH_SIDE - 1))
                page_range.append(DOT)
                page_range.extend(range(page_num - ON_EACH_SIDE, page_num + 1))
            else:
                page_range.extend(range(0, page_num + 1))
            if page_num < (paginator.pages - ON_EACH_SIDE - ON_ENDS - 1):
                page_range.extend(range(page_num + 1, page_num + ON_EACH_SIDE + 1))
                page_range.append(DOT)
                page_range.extend(range(paginator.pages - ON_ENDS, paginator.pages))
            else:
                page_range.extend(range(page_num + 1, paginator.pages))

    need_show_all_link = cl.can_show_all and not cl.show_all and cl.multi_page
    return {
        'cl': cl,
        'pagination_required': pagination_required,
        'show_all_url': need_show_all_link and cl.get_query_string({ALL_VAR: ''}),
        'page_range': page_range,
        'ALL_VAR': ALL_VAR,
        '1': 1,
    }
pagination = register.inclusion_tag('admin/pagination')(pagination)

def result_headers(cl):
    lookup_opts = cl.lookup_opts

    for i, field_name in enumerate(lookup_opts.admin.list_display):
        try:
            f = lookup_opts.get_field(field_name)
        except meta.FieldDoesNotExist:
            # For non-field list_display values, check for the function
            # attribute "short_description". If that doesn't exist, fall
            # back to the method name. And __repr__ is a special-case.
            if field_name == '__repr__':
                header = lookup_opts.verbose_name
            else:
                func = getattr(cl.mod.Klass, field_name) # Let AttributeErrors propogate.
                try:
                    header = func.short_description
                except AttributeError:
                    header = func.__name__.replace('_', ' ')
            # Non-field list_display values don't get ordering capability.
            yield {"text": header}
        else:
            if isinstance(f.rel, meta.ManyToOne) and f.null:
                yield {"text": f.verbose_name}
            else:
                th_classes = []
                new_order_type = 'asc'
                if field_name == cl.order_field:
                    th_classes.append('sorted %sending' % cl.order_type.lower())
                    new_order_type = {'asc': 'desc', 'desc': 'asc'}[cl.order_type.lower()]

                yield {"text": f.verbose_name,
                       "sortable": True,
                       "url": cl.get_query_string({ORDER_VAR: i, ORDER_TYPE_VAR: new_order_type}),
                       "class_attrib": (th_classes and ' class="%s"' % ' '.join(th_classes) or '')}

def items_for_result(cl, result):
    first = True
    pk = cl.lookup_opts.pk.attname
    for field_name in cl.lookup_opts.admin.list_display:
        row_class = ''
        try:
            f = cl.lookup_opts.get_field(field_name)
        except meta.FieldDoesNotExist:
            # For non-field list_display values, the value is a method
            # name. Execute the method.
            try:
                func = getattr(result, field_name)
                result_repr = str(func())
            except AttributeError, ObjectDoesNotExist:
                result_repr = EMPTY_CHANGELIST_VALUE
            else:
                # Strip HTML tags in the resulting text, except if the
                # function has an "allow_tags" attribute set to True.
                if not getattr(func, 'allow_tags', False):
                    result_repr = escape(result_repr)
        else:
            field_val = getattr(result, f.attname)

            if isinstance(f.rel, meta.ManyToOne):
                if field_val is not None:
                    result_repr = getattr(result, 'get_%s' % f.name)()
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
            # Dates and times are special: They're formatted in a certain way.
            elif isinstance(f, meta.DateField) or isinstance(f, meta.TimeField):
                if field_val:
                    (date_format, datetime_format, time_format) = get_date_formats()
                    if isinstance(f, meta.DateTimeField):
                        result_repr = capfirst(dateformat.format(field_val, datetime_format))
                    elif isinstance(f, meta.TimeField):
                        result_repr = capfirst(dateformat.time_format(field_val, time_format))
                    else:
                        result_repr = capfirst(dateformat.format(field_val, date_format))
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
                row_class = ' class="nowrap"'
            # Booleans are special: We use images.
            elif isinstance(f, meta.BooleanField) or isinstance(f, meta.NullBooleanField):
                BOOLEAN_MAPPING = {True: 'yes', False: 'no', None: 'unknown'}
                result_repr = '<img src="%simg/admin/icon-%s.gif" alt="%s" />' % (ADMIN_MEDIA_PREFIX, BOOLEAN_MAPPING[field_val], field_val)
            # ImageFields are special: Use a thumbnail.
            elif isinstance(f, meta.ImageField):
                from django.parts.media.photos import get_thumbnail_url
                result_repr = '<img src="%s" alt="%s" title="%s" />' % (get_thumbnail_url(getattr(result, 'get_%s_url' % f.name)(), '120'), field_val, field_val)
            # FloatFields are special: Zero-pad the decimals.
            elif isinstance(f, meta.FloatField):
                if field_val is not None:
                    result_repr = ('%%.%sf' % f.decimal_places) % field_val
                else:
                    result_repr = EMPTY_CHANGELIST_VALUE
            # Fields with choices are special: Use the representation
            # of the choice.
            elif f.choices:
                result_repr = dict(f.choices).get(field_val, EMPTY_CHANGELIST_VALUE)
            else:
                result_repr = escape(str(field_val))
        if result_repr == '':
                result_repr = '&nbsp;'
        if first: # First column is a special case
            first = False
            url = cl.url_for_result(result)
            result_id = getattr(result, pk)
            yield ('<th%s><a href="%s"%s>%s</a></th>' % \
                (row_class, url, (cl.is_popup and ' onclick="opener.dismissRelatedLookupPopup(window, %r); return false;"' % result_id or ''), result_repr))
        else:
            yield ('<td%s>%s</td>' % (row_class, result_repr))

def results(cl):
    for res in cl.result_list:
        yield list(items_for_result(cl,res))

def result_list(cl):
    res = list(results(cl))
    return {'cl': cl,
            'result_headers': list(result_headers(cl)),
            'results': list(results(cl))}
result_list = register.inclusion_tag("admin/change_list_results")(result_list)

def date_hierarchy(cl):
    lookup_opts, params, lookup_params, lookup_mod = \
      cl.lookup_opts, cl.params, cl.lookup_params, cl.lookup_mod

    if lookup_opts.admin.date_hierarchy:
        field_name = lookup_opts.admin.date_hierarchy

        year_field = '%s__year' % field_name
        month_field = '%s__month' % field_name
        day_field = '%s__day' % field_name
        field_generic = '%s__' % field_name
        year_lookup = params.get(year_field)
        month_lookup = params.get(month_field)
        day_lookup = params.get(day_field)

        def link(d):
            return cl.get_query_string(d, [field_generic])

        def get_dates(unit, params):
            return getattr(lookup_mod, 'get_%s_list' % field_name)(unit, **params)

        if year_lookup and month_lookup and day_lookup:
            month_name = MONTHS[int(month_lookup)]
            return {
                'show': True,
                'back': {
                    'link': link({year_field: year_lookup, month_field: month_lookup}),
                    'title': "%s %s" % (month_name, year_lookup)
                },
                'choices': [{'title': "%s %s" % (month_name, day_lookup)}]
            }
        elif year_lookup and month_lookup:
            date_lookup_params = lookup_params.copy()
            date_lookup_params.update({year_field: year_lookup, month_field: month_lookup})
            days = get_dates('day', date_lookup_params)
            return {
                'show': True,
                'back': {
                    'link': link({year_field: year_lookup}),
                    'title': year_lookup
                },
                'choices': [{
                    'link': link({year_field: year_lookup, month_field: month_lookup, day_field: day.day}),
                    'title': day.strftime('%B %d')
                } for day in days]
            }
        elif year_lookup:
            date_lookup_params = lookup_params.copy()
            date_lookup_params.update({year_field: year_lookup})
            months = get_dates('month', date_lookup_params)
            return {
                'show' : True,
                'back': {
                    'link' : link({}),
                    'title': _('All dates')
                },
                'choices': [{
                    'link': link( {year_field: year_lookup, month_field: month.month}),
                    'title': "%s %s" % (month.strftime('%B') ,  month.year)
                } for month in months]
            }
        else:
            years = get_dates('year', lookup_params)
            return {
                'show': True,
                'choices': [{
                    'link': link({year_field: year.year}),
                    'title': year.year
                } for year in years ]
            }
date_hierarchy = register.inclusion_tag('admin/date_hierarchy')(date_hierarchy)

def search_form(cl):
    return {
        'cl': cl,
        'show_result_count': cl.result_count != cl.full_result_count and not cl.opts.one_to_one_field,
        'search_var': SEARCH_VAR
    }
search_form = register.inclusion_tag('admin/search_form')(search_form)

def filter(cl, spec):
    return {'title': spec.title(), 'choices' : list(spec.choices(cl))}
filter = register.inclusion_tag('admin/filter')(filter)

def filters(cl):
    return {'cl': cl}
filters = register.inclusion_tag('admin/filters')(filters)
