import traceback

import logging
logger = logging.getLogger(__name__)


class AccessPluginBase(object):
    '''
    This base class is defined to be used as a base class for all
    access plugins. The plugin may contain two kinds of callbacks:

    - `apply_somethingable`
    - `verify_somethingable`
    - The `check_somethingable` is deprecated

    The `apply_somethingable` is called every time when the system requests `somethingable`
    ability for some subset of instances determined by the queryset. The return value of
    the `apply_somethingable` should be a queryset filtered to restrict only allowed instances.

    Definition of the callback should look like:

    ```
    def apply_somethingable(self, queryset, request)
    ```

    The passed `queryset` determines a requested instance subset, while `request` is passed
    to make a decision about rights of the requestor.

    The following standard abilities are applied such a way:

    - visible
    - changeable
    - deleteable

    The `verify_somethingable` is called every time when the system requests `somethingable`
    ability for a model as a whole. The return value of the `verify_somethingable` should be
    a False value if the requested ability is not allowed to the requestor, or True, which
    allows access.

    Definition of the callback should look like:

    ```
    def verify_somethingable(self, model, request, attributes={})
    ```

    The `model` determines a model, while `request` is passed to make a decision
    about rights of the requestor. The additional attributes parameter contains the
    set of new values of attributes for the model to be verified for the `somethingable` ability.

    The following standard abilities are applied such a way:

    - visible
    - changeable
    - deleteable
    - appendable
    '''


class ApplyAblePlugin(AccessPluginBase):
    '''
    The ApplyAblePlugin determines instance-level access rules basing on abilities determined
    by a dictionary passed to the constructor.

    The dictionary contains abilities as keys, and functional rules as values. The rule is
    evaluated against a QuerySet and a Request object containing a rule context.

    The passed functions evaluate access rules for abilities

    The well known and used in the admin queries:
        - visible
        - changeable
        - deleteable
    The superuser is always having all abilities.

    For example:
        ApplyAblePlugin(
            visible=lambda queryset, request: queryset.filter(Q(park__enterprise__in=r.user.visible_enterprises()))
        )
    '''
    def __init__(self, **kw):
        self._abilities = kw

    def __getattr__(self, name):
        prefix = 'apply_'
        if name.startswith(prefix):
            ability = name[len(prefix):]
            apply_method = self._abilities.get(ability, lambda queryset, request: queryset)

            def method(queryset, request):
                if request.user.is_superuser:
                    return queryset.all()
                return apply_method(queryset, request)
            return method
        raise AttributeError(name)


class VerifyAblePlugin(AccessPluginBase):
    '''
    The VerifyAblePlugin determines model-level preliminary access rules basing
    on abilities determined by a dictionary passed to the constructor.

    The dictionary contains abilities as keys, and functional rules as values. The rule is
    evaluated against a Model, a Request object containing a rule context, and attributes
    dictionary, which is filled by the new attributes values (if applicable).

    The passed functions evaluate access rules for abilities

    The well known and used in the admin:
        - visible
        - appendable
        - changeable
        - deleteable
    The superuser is having all abilities.

    For example:
        VerifyAblePlugin(
            appendable=lambda model, request, attributes={}: (attributes.update({'user':request.user}), True)
        )
    '''

    def __init__(self, **kw):
        self._abilities = kw

    def __getattr__(self, name):
        prefix = 'verify_'
        if name.startswith(prefix):
            ability = name[len(prefix):]
            verify_method = self._abilities.get(ability, lambda model, request, attributes={}: True)

            def method(model, request, attributes={}):
                if request.user.is_superuser:
                    return True
                return verify_method(model, request, attributes=attributes)
            return method
        raise AttributeError(name)


class CheckAblePlugin(VerifyAblePlugin):
    '''
    The CheckAblePlugin is deprecated and should be replaced by the VerifyAblePlugin
    '''

    def __init__(self, **kw):
        logger.warning("The `CheckAblePlugin` is deprecated, use `VerifyAblePlugin` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        abilities = dict((k, self._check_to_verify(v)) for k, v in kw.items())
        super(CheckAblePlugin, self).__init__(**abilities)

    def _check_to_verify(self, func):
        def verify_check_method(model, request, attributes={}):
            ret = func(model, request)
            if isinstance(ret, dict):
                attributes.update(ret)
            return ret is not False
        return verify_check_method


class SimpleCheckPlugin(CheckAblePlugin):
    '''
    The SimpleCheckPlugin does the same as a VerifyAblePlugin, not passing attributes to the underlining rule.

    It is deprecated.

    For example:
        SimpleCheckPlugin(
            appendable=lambda model, request: model._meta.app_label == "custom"
        )
    '''

    def __init__(self, **kw):
        logger.warning("The `SimpleCheckPlugin` is deprecated, use `VerifyAblePlugin` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        abilities = dict((k, self._check_to_verify(v)) for k, v in kw.items())
        super(CheckAblePlugin, self).__init__(**abilities)

    def _check_to_verify(self, func):
        def verify_check_method(model, request, attributes={}):
            return func(model, request)
        return verify_check_method


class CompoundPlugin(AccessPluginBase):
    '''
    The CompoundPlugin combines access rights from several plugins
    passed to the constructor through the AND operator. If any of
    the plugins denies access to the object, the CompoundPlugin
    does the same.


    For example:
        CompoundPlugin(
            VerifyAblePlugin(appendable=lambda *av, **kw: True),
            PureVisiblePlugin(
                Q(park__enterprise__in=lambda r:r.user.visible_enterprises())
            )
        )
    '''
    def __init__(self, *plugins):
        self.plugins = plugins

    def apply_able(self, ability, queryset, request):
        ret = queryset
        for p in self.plugins:
            if hasattr(p, 'apply_%s' % ability):
                method = getattr(p, 'apply_%s' % ability)
                ret = method(ret, request)
        return ret

    def verify_able(self, ability, model, request, attributes={}):
        ret = True
        for p in self.plugins:
            if hasattr(p, 'verify_%s' % ability):
                method = getattr(p, 'verify_%s' % ability)
                ret = method(model, request, attributes=attributes) and ret
                if not ret:
                    break
        return ret

    def __getattr__(self, name):
        method = None
        prefix = 'apply_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(queryset, request):
                return self.apply_able(ability, queryset, request)
            return method

        prefix = 'verify_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(model, request, attributes={}):
                return self.verify_able(ability, model, request, attributes=attributes)
            return method

        prefix = 'check_'
        if name.startswith(prefix):
            ability = name[len(prefix):]
            logger.warning("The `%s` is deprecated, use `verify_%s` instead", name, ability)
            logger.debug(">>> %s", ''.join(traceback.format_stack()))

            def method(model, request):
                attributes = {}
                ret = self.verify_able(ability, model, request, attributes=attributes)
                return attributes if ret else False
            return method
        raise AttributeError(name)


class DjangoChangeAccessPlugin(AccessPluginBase):
    def _has_a(self, a, model, request):
        if request.user.is_superuser:
            return True
        return bool(
            request.user.groups.filter(
                permissions__content_type__app_label=model._meta.app_label,
                permissions__content_type__model=model._meta.model_name,
                permissions__codename=a
            )
        ) or bool(
            request.user.user_permissions.filter(
                content_type__app_label=model._meta.app_label,
                content_type__model=model._meta.model_name,
                codename=a
            )
        )

    def verify_appendable(self, model, request, attributes={}):
        return self._has_a('add_%s' % model._meta.model_name, model, request)

    def verify_changeable(self, model, request, attributes={}):
        return self._has_a('change_%s' % model._meta.model_name, model, request)

    def verify_deleteable(self, model, request, attributes={}):
        return self._has_a('delete_%s' % model._meta.model_name, model, request)

    def verify_visible(self, model, request, attributes={}):
        return True

    def check_appendable(self, model, request):
        logger.warning("The `check_appendable` is deprecated, use `verify_appendable` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        return {} if self.verify_appendable(model, request) else False

    def check_changeable(self, model, request, attributes={}):
        logger.warning("The `check_changeable` is deprecated, use `verify_changeable` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        return {} if self.verify_changeable(model, request) else False

    def check_deleteable(self, model, request, attributes={}):
        logger.warning("The `check_deleteable` is deprecated, use `verify_deleteable` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        return {} if self.verify_deleteable(model, request) else False

    def check_visible(self, model, request, attributes={}):
        logger.warning("The `check_visible` is deprecated, use `verify_visible` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        return {} if self.verify_visible(model, request) else False

    def apply_visible(self, queryset, request):
        return queryset.all()

    def apply_changeable(self, queryset, request):
        return queryset.all() if self._has_a('change_%s' % queryset.model._meta.model_name, queryset.model, request) else queryset.none()

    def apply_deleteable(self, queryset, request):
        return queryset.all() if self._has_a('delete_%s' % queryset.model._meta.model_name, queryset.model, request) else queryset.none()

    def __getattr__(self, name):
        # Getting unusual rights
        prefix = 'apply_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(queryset, request):
                return queryset.all() if self._has_a(ability, queryset.model, request) else queryset.none()
            return method

        prefix = 'verify_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(model, request, attributes={}):
                return self._has_a(ability, model, request)
            return method

        prefix = 'check_'
        if name.startswith(prefix):
            ability = name[len(prefix):]
            logger.warning("The `%s` is deprecated, use `verify_%s` instead", name, ability)
            logger.debug(">>> %s", ''.join(traceback.format_stack()))
            verify = getattr(self, 'verify_%s' % ability)

            def method(model, request):
                ret = verify(model, request)
                return {} if ret else False
            return method
        raise AttributeError(name)


class DjangoAccessPlugin(DjangoChangeAccessPlugin):
    def _visible(self, model, request):
        if request.user.is_superuser:
            return True
        return bool(
            request.user.groups.filter(
                permissions__content_type__app_label=model._meta.app_label,
                permissions__content_type__model=model._meta.model_name,
            )
        ) or bool(
            request.user.user_permissions.filter(
                content_type__app_label=model._meta.app_label,
                content_type__model=model._meta.model_name,
            )
        )

    def verify_visible(self, model, request, attributes={}):
        return self._visible(model, request)
