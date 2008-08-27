import copy
import types
import sys
import os
from itertools import izip
try:
    set
except NameError:
    from sets import Set as set     # Python 2.3 fallback.

import django.db.models.manager     # Imported to register signal handler.
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, FieldError
from django.db.models.fields import AutoField
from django.db.models.fields.related import OneToOneRel, ManyToOneRel, OneToOneField
from django.db.models.query import delete_objects, Q, CollectedObjects
from django.db.models.options import Options
from django.db import connection, transaction, DatabaseError
from django.db.models import signals
from django.db.models.loading import register_models, get_model
from django.utils.functional import curry
from django.utils.encoding import smart_str, force_unicode, smart_unicode
from django.core.files.move import file_move_safe
from django.core.files import locks
from django.conf import settings


class ModelBase(type):
    """
    Metaclass for all models.
    """
    def __new__(cls, name, bases, attrs):
        super_new = super(ModelBase, cls).__new__
        parents = [b for b in bases if isinstance(b, ModelBase)]
        if not parents:
            # If this isn't a subclass of Model, don't do anything special.
            return super_new(cls, name, bases, attrs)

        # Create the class.
        module = attrs.pop('__module__')
        new_class = super_new(cls, name, bases, {'__module__': module})
        attr_meta = attrs.pop('Meta', None)
        abstract = getattr(attr_meta, 'abstract', False)
        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta
        base_meta = getattr(new_class, '_meta', None)

        if getattr(meta, 'app_label', None) is None:
            # Figure out the app_label by looking one level up.
            # For 'django.contrib.sites.models', this would be 'sites'.
            model_module = sys.modules[new_class.__module__]
            kwargs = {"app_label": model_module.__name__.split('.')[-2]}
        else:
            kwargs = {}

        new_class.add_to_class('_meta', Options(meta, **kwargs))
        if not abstract:
            new_class.add_to_class('DoesNotExist',
                    subclass_exception('DoesNotExist', ObjectDoesNotExist, module))
            new_class.add_to_class('MultipleObjectsReturned',
                    subclass_exception('MultipleObjectsReturned', MultipleObjectsReturned, module))
            if base_meta and not base_meta.abstract:
                # Non-abstract child classes inherit some attributes from their
                # non-abstract parent (unless an ABC comes before it in the
                # method resolution order).
                if not hasattr(meta, 'ordering'):
                    new_class._meta.ordering = base_meta.ordering
                if not hasattr(meta, 'get_latest_by'):
                    new_class._meta.get_latest_by = base_meta.get_latest_by

        old_default_mgr = None
        if getattr(new_class, '_default_manager', None):
            # We have a parent who set the default manager.
            if new_class._default_manager.model._meta.abstract:
                old_default_mgr = new_class._default_manager
            new_class._default_manager = None

        # Bail out early if we have already created this class.
        m = get_model(new_class._meta.app_label, name, False)
        if m is not None:
            return m

        # Add all attributes to the class.
        for obj_name, obj in attrs.items():
            new_class.add_to_class(obj_name, obj)

        # Do the appropriate setup for any model parents.
        o2o_map = dict([(f.rel.to, f) for f in new_class._meta.local_fields
                if isinstance(f, OneToOneField)])
        for base in parents:
            if not hasattr(base, '_meta'):
                # Things without _meta aren't functional models, so they're
                # uninteresting parents.
                continue
            if not base._meta.abstract:
                if base in o2o_map:
                    field = o2o_map[base]
                    field.primary_key = True
                    new_class._meta.setup_pk(field)
                else:
                    attr_name = '%s_ptr' % base._meta.module_name
                    field = OneToOneField(base, name=attr_name,
                            auto_created=True, parent_link=True)
                    new_class.add_to_class(attr_name, field)
                new_class._meta.parents[base] = field
            else:
                # The abstract base class case.
                names = set([f.name for f in new_class._meta.local_fields + new_class._meta.many_to_many])
                for field in base._meta.local_fields + base._meta.local_many_to_many:
                    if field.name in names:
                        raise FieldError('Local field %r in class %r clashes with field of similar name from abstract base class %r'
                                % (field.name, name, base.__name__))
                    new_class.add_to_class(field.name, copy.deepcopy(field))

        if abstract:
            # Abstract base models can't be instantiated and don't appear in
            # the list of models for an app. We do the final setup for them a
            # little differently from normal models.
            attr_meta.abstract = False
            new_class.Meta = attr_meta
            return new_class

        if old_default_mgr and not new_class._default_manager:
            new_class._default_manager = old_default_mgr._copy_to_model(new_class)
        new_class._prepare()
        register_models(new_class._meta.app_label, new_class)

        # Because of the way imports happen (recursively), we may or may not be
        # the first time this model tries to register with the framework. There
        # should only be one class for each model, so we always return the
        # registered version.
        return get_model(new_class._meta.app_label, name, False)

    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)

    def _prepare(cls):
        """
        Creates some methods once self._meta has been populated.
        """
        opts = cls._meta
        opts._prepare(cls)

        if opts.order_with_respect_to:
            cls.get_next_in_order = curry(cls._get_next_or_previous_in_order, is_next=True)
            cls.get_previous_in_order = curry(cls._get_next_or_previous_in_order, is_next=False)
            setattr(opts.order_with_respect_to.rel.to, 'get_%s_order' % cls.__name__.lower(), curry(method_get_order, cls))
            setattr(opts.order_with_respect_to.rel.to, 'set_%s_order' % cls.__name__.lower(), curry(method_set_order, cls))

        # Give the class a docstring -- its definition.
        if cls.__doc__ is None:
            cls.__doc__ = "%s(%s)" % (cls.__name__, ", ".join([f.attname for f in opts.fields]))

        if hasattr(cls, 'get_absolute_url'):
            cls.get_absolute_url = curry(get_absolute_url, opts, cls.get_absolute_url)

        signals.class_prepared.send(sender=cls)


class Model(object):
    __metaclass__ = ModelBase

    def __init__(self, *args, **kwargs):
        signals.pre_init.send(sender=self.__class__, args=args, kwargs=kwargs)

        # There is a rather weird disparity here; if kwargs, it's set, then args
        # overrides it. It should be one or the other; don't duplicate the work
        # The reason for the kwargs check is that standard iterator passes in by
        # args, and instantiation for iteration is 33% faster.
        args_len = len(args)
        if args_len > len(self._meta.fields):
            # Daft, but matches old exception sans the err msg.
            raise IndexError("Number of args exceeds number of fields")

        fields_iter = iter(self._meta.fields)
        if not kwargs:
            # The ordering of the izip calls matter - izip throws StopIteration
            # when an iter throws it. So if the first iter throws it, the second
            # is *not* consumed. We rely on this, so don't change the order
            # without changing the logic.
            for val, field in izip(args, fields_iter):
                setattr(self, field.attname, val)
        else:
            # Slower, kwargs-ready version.
            for val, field in izip(args, fields_iter):
                setattr(self, field.attname, val)
                kwargs.pop(field.name, None)
                # Maintain compatibility with existing calls.
                if isinstance(field.rel, ManyToOneRel):
                    kwargs.pop(field.attname, None)

        # Now we're left with the unprocessed fields that *must* come from
        # keywords, or default.

        for field in fields_iter:
            rel_obj = None
            if kwargs:
                if isinstance(field.rel, ManyToOneRel):
                    try:
                        # Assume object instance was passed in.
                        rel_obj = kwargs.pop(field.name)
                    except KeyError:
                        try:
                            # Object instance wasn't passed in -- must be an ID.
                            val = kwargs.pop(field.attname)
                        except KeyError:
                            val = field.get_default()
                    else:
                        # Object instance was passed in. Special case: You can
                        # pass in "None" for related objects if it's allowed.
                        if rel_obj is None and field.null:
                            val = None
                else:
                    val = kwargs.pop(field.attname, field.get_default())
            else:
                val = field.get_default()
            # If we got passed a related instance, set it using the field.name
            # instead of field.attname (e.g. "user" instead of "user_id") so
            # that the object gets properly cached (and type checked) by the
            # RelatedObjectDescriptor.
            if rel_obj:
                setattr(self, field.name, rel_obj)
            else:
                setattr(self, field.attname, val)

        if kwargs:
            for prop in kwargs.keys():
                try:
                    if isinstance(getattr(self.__class__, prop), property):
                        setattr(self, prop, kwargs.pop(prop))
                except AttributeError:
                    pass
            if kwargs:
                raise TypeError, "'%s' is an invalid keyword argument for this function" % kwargs.keys()[0]
        signals.post_init.send(sender=self.__class__, instance=self)

    def __repr__(self):
        return smart_str(u'<%s: %s>' % (self.__class__.__name__, unicode(self)))

    def __str__(self):
        if hasattr(self, '__unicode__'):
            return force_unicode(self).encode('utf-8')
        return '%s object' % self.__class__.__name__

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._get_pk_val() == other._get_pk_val()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._get_pk_val())

    def _get_pk_val(self, meta=None):
        if not meta:
            meta = self._meta
        return getattr(self, meta.pk.attname)

    def _set_pk_val(self, value):
        return setattr(self, self._meta.pk.attname, value)

    pk = property(_get_pk_val, _set_pk_val)

    def save(self, force_insert=False, force_update=False):
        """
        Saves the current instance. Override this in a subclass if you want to
        control the saving process.

        The 'force_insert' and 'force_update' parameters can be used to insist
        that the "save" must be an SQL insert or update (or equivalent for
        non-SQL backends), respectively. Normally, they should not be set.
        """
        if force_insert and force_update:
            raise ValueError("Cannot force both insert and updating in "
                    "model saving.")
        self.save_base(force_insert=force_insert, force_update=force_update)

    save.alters_data = True

    def save_base(self, raw=False, cls=None, force_insert=False,
            force_update=False):
        """
        Does the heavy-lifting involved in saving. Subclasses shouldn't need to
        override this method. It's separate from save() in order to hide the
        need for overrides of save() to pass around internal-only parameters
        ('raw' and 'cls').
        """
        assert not (force_insert and force_update)
        if not cls:
            cls = self.__class__
            meta = self._meta
            signal = True
            signals.pre_save.send(sender=self.__class__, instance=self, raw=raw)
        else:
            meta = cls._meta
            signal = False

        # If we are in a raw save, save the object exactly as presented.
        # That means that we don't try to be smart about saving attributes
        # that might have come from the parent class - we just save the
        # attributes we have been given to the class we have been given.
        if not raw:
            for parent, field in meta.parents.items():
                # At this point, parent's primary key field may be unknown
                # (for example, from administration form which doesn't fill
                # this field). If so, fill it.
                if getattr(self, parent._meta.pk.attname) is None and getattr(self, field.attname) is not None:
                    setattr(self, parent._meta.pk.attname, getattr(self, field.attname))

                self.save_base(raw, parent)
                setattr(self, field.attname, self._get_pk_val(parent._meta))

        non_pks = [f for f in meta.local_fields if not f.primary_key]

        # First, try an UPDATE. If that doesn't update anything, do an INSERT.
        pk_val = self._get_pk_val(meta)
        pk_set = pk_val is not None
        record_exists = True
        manager = cls._default_manager
        if pk_set:
            # Determine whether a record with the primary key already exists.
            if (force_update or (not force_insert and
                    manager.filter(pk=pk_val).extra(select={'a': 1}).values('a').order_by())):
                # It does already exist, so do an UPDATE.
                if force_update or non_pks:
                    values = [(f, None, f.get_db_prep_save(raw and getattr(self, f.attname) or f.pre_save(self, False))) for f in non_pks]
                    rows = manager.filter(pk=pk_val)._update(values)
                    if force_update and not rows:
                        raise DatabaseError("Forced update did not affect any rows.")
            else:
                record_exists = False
        if not pk_set or not record_exists:
            if not pk_set:
                if force_update:
                    raise ValueError("Cannot force an update in save() with no primary key.")
                values = [(f, f.get_db_prep_save(raw and getattr(self, f.attname) or f.pre_save(self, True))) for f in meta.local_fields if not isinstance(f, AutoField)]
            else:
                values = [(f, f.get_db_prep_save(raw and getattr(self, f.attname) or f.pre_save(self, True))) for f in meta.local_fields]

            if meta.order_with_respect_to:
                field = meta.order_with_respect_to
                values.append((meta.get_field_by_name('_order')[0], manager.filter(**{field.name: getattr(self, field.attname)}).count()))
            record_exists = False

            update_pk = bool(meta.has_auto_field and not pk_set)
            if values:
                # Create a new record.
                result = manager._insert(values, return_id=update_pk)
            else:
                # Create a new record with defaults for everything.
                result = manager._insert([(meta.pk, connection.ops.pk_default_value())], return_id=update_pk, raw_values=True)

            if update_pk:
                setattr(self, meta.pk.attname, result)
        transaction.commit_unless_managed()

        if signal:
            signals.post_save.send(sender=self.__class__, instance=self,
                created=(not record_exists), raw=raw)

    save_base.alters_data = True

    def _collect_sub_objects(self, seen_objs, parent=None, nullable=False):
        """
        Recursively populates seen_objs with all objects related to this
        object.

        When done, seen_objs.items() will be in the format:
            [(model_class, {pk_val: obj, pk_val: obj, ...}),
             (model_class, {pk_val: obj, pk_val: obj, ...}), ...]
        """
        pk_val = self._get_pk_val()
        if seen_objs.add(self.__class__, pk_val, self, parent, nullable):
            return

        for related in self._meta.get_all_related_objects():
            rel_opts_name = related.get_accessor_name()
            if isinstance(related.field.rel, OneToOneRel):
                try:
                    sub_obj = getattr(self, rel_opts_name)
                except ObjectDoesNotExist:
                    pass
                else:
                    sub_obj._collect_sub_objects(seen_objs, self.__class__, related.field.null)
            else:
                for sub_obj in getattr(self, rel_opts_name).all():
                    sub_obj._collect_sub_objects(seen_objs, self.__class__, related.field.null)

        # Handle any ancestors (for the model-inheritance case). We do this by
        # traversing to the most remote parent classes -- those with no parents
        # themselves -- and then adding those instances to the collection. That
        # will include all the child instances down to "self".
        parent_stack = self._meta.parents.values()
        while parent_stack:
            link = parent_stack.pop()
            parent_obj = getattr(self, link.name)
            if parent_obj._meta.parents:
                parent_stack.extend(parent_obj._meta.parents.values())
                continue
            # At this point, parent_obj is base class (no ancestor models). So
            # delete it and all its descendents.
            parent_obj._collect_sub_objects(seen_objs)

    def delete(self):
        assert self._get_pk_val() is not None, "%s object can't be deleted because its %s attribute is set to None." % (self._meta.object_name, self._meta.pk.attname)

        # Find all the objects than need to be deleted.
        seen_objs = CollectedObjects()
        self._collect_sub_objects(seen_objs)

        # Actually delete the objects.
        delete_objects(seen_objs)

    delete.alters_data = True

    def _get_FIELD_display(self, field):
        value = getattr(self, field.attname)
        return force_unicode(dict(field.flatchoices).get(value, value), strings_only=True)

    def _get_next_or_previous_by_FIELD(self, field, is_next, **kwargs):
        op = is_next and 'gt' or 'lt'
        order = not is_next and '-' or ''
        param = smart_str(getattr(self, field.attname))
        q = Q(**{'%s__%s' % (field.name, op): param})
        q = q|Q(**{field.name: param, 'pk__%s' % op: self.pk})
        qs = self.__class__._default_manager.filter(**kwargs).filter(q).order_by('%s%s' % (order, field.name), '%spk' % order)
        try:
            return qs[0]
        except IndexError:
            raise self.DoesNotExist, "%s matching query does not exist." % self.__class__._meta.object_name

    def _get_next_or_previous_in_order(self, is_next):
        cachename = "__%s_order_cache" % is_next
        if not hasattr(self, cachename):
            qn = connection.ops.quote_name
            op = is_next and '>' or '<'
            order = not is_next and '-_order' or '_order'
            order_field = self._meta.order_with_respect_to
            # FIXME: When querysets support nested queries, this can be turned
            # into a pure queryset operation.
            where = ['%s %s (SELECT %s FROM %s WHERE %s=%%s)' % \
                (qn('_order'), op, qn('_order'),
                qn(self._meta.db_table), qn(self._meta.pk.column))]
            params = [self.pk]
            obj = self._default_manager.filter(**{order_field.name: getattr(self, order_field.attname)}).extra(where=where, params=params).order_by(order)[:1].get()
            setattr(self, cachename, obj)
        return getattr(self, cachename)



############################################
# HELPER FUNCTIONS (CURRIED MODEL METHODS) #
############################################

# ORDERING METHODS #########################

def method_set_order(ordered_obj, self, id_list):
    rel_val = getattr(self, ordered_obj._meta.order_with_respect_to.rel.field_name)
    order_name = ordered_obj._meta.order_with_respect_to.name
    # FIXME: It would be nice if there was an "update many" version of update
    # for situations like this.
    for i, j in enumerate(id_list):
        ordered_obj.objects.filter(**{'pk': j, order_name: rel_val}).update(_order=i)
    transaction.commit_unless_managed()


def method_get_order(ordered_obj, self):
    rel_val = getattr(self, ordered_obj._meta.order_with_respect_to.rel.field_name)
    order_name = ordered_obj._meta.order_with_respect_to.name
    pk_name = ordered_obj._meta.pk.name
    return [r[pk_name] for r in
            ordered_obj.objects.filter(**{order_name: rel_val}).values(pk_name)]


##############################################
# HELPER FUNCTIONS (CURRIED MODEL FUNCTIONS) #
##############################################

def get_absolute_url(opts, func, self, *args, **kwargs):
    return settings.ABSOLUTE_URL_OVERRIDES.get('%s.%s' % (opts.app_label, opts.module_name), func)(self, *args, **kwargs)


########
# MISC #
########

class Empty(object):
    pass

if sys.version_info < (2, 5):
    # Prior to Python 2.5, Exception was an old-style class
    def subclass_exception(name, parent, unused):
        return types.ClassType(name, (parent,), {})
else:
    def subclass_exception(name, parent, module):
        return type(name, (parent,), {'__module__': module})
