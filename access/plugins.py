class AccessPluginBase(object):
    '''
    This base class is defined to be used as a base class for all
    access plugins. The plugin may contain two kinds of callbacks:

    - `apply_somethingable`
    - `check_somethingable`

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

    The `check_somethingable` is called every time when the system requests `somethingable`
    ability for a model as a whole. The return value of the `check_somethingable` should be
    a False value if the requested ability is not allowed to the requestor. Any other value
    including `None` means allowed control.

    The CompoundPlugin also assumes that the `check_somethingable` always returns either
    disctionary, or False values.

    Definition of the callback should look like:

    ```
    def check_somethingable(self, model, request)
    ```

    The `model` determines a model, while `request` is passed to make a decision
    about rights of the requestor.

    The following standard abilities are applied such a way:

    - visible
    - changeable
    - deleteable
    - appendable
    '''


class ApplyAblePlugin(AccessPluginBase):
    '''
    The ApplyAblePlugin determines instance-level access rights basing on abilities determined by later evaluated
    queries passed to the constructor.

    The well known and used in the admin queries:
        - visible
        - changeable
        - deleteable
    The superuser is having all abilities.

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


class CheckAblePlugin(AccessPluginBase):
    '''
    The CheckAblePlugin determines model-level access rights basing on abilities determined by later evaluated
    check functions passed to the constructor.

    The most important:
        - appendable
    The well known and used in the admin:
        - visible
        - changeable
        - deleteable
    The superuser is having all abilities.

    For example:
        CheckAblePlugin(
            appendable=lambda model, request:{'user':request.user}
        )
    '''

    def __init__(self, **kw):
        self._abilities = kw

    def __getattr__(self, name):
        prefix = 'check_'
        if name.startswith(prefix):
            ability = name[len(prefix):]
            check_method = self._abilities.get(ability, lambda model, request: {})

            def method(model, request):
                d = check_method(model, request)
                if d is False:
                    if request.user.is_superuser:
                        return {}
                    return False
                if not d:
                    return {}
                return d
            return method
        raise AttributeError(name)


class SimpleCheckPlugin(CheckAblePlugin):
    '''
    The SimpleCheckPlugin determines model-level access rights basing on abilities determined by later evaluated
    simple check functions passed to the constructor. The simple model-level access check function returns True
    (instead of dictionary when the check is more sophisticated) when the access is allowed.

    The most important:
        - appendable
    The well known and used in the admin:
        - visible
        - changeable
        - deleteable
    The superuser is having all abilities.

    For example:
        SimpleCheckPlugin(
            appendable=lambda model, request: model._meta.app_label == "custom"
        )
    '''

    def __init__(self, **kw):
        def get_check_able(ability, cb):
            def check(model, request):
                if cb(model, request):
                    return {}
                return False
            return check
        CheckAblePlugin.__init__(self, **{k: get_check_able(k, kw[k]) for k in kw})


class CompoundPlugin(AccessPluginBase):
    '''
    The CompoundPlugin combines access rights from several plugins
    passed to the constructor through the AND operator. If any of
    the plugins denies access to the object, the CompoundPlugin
    does the same.

    For the model-wide access, the returned values of combined
    plugins are united as dictionaries, if not a False.

    For example:
        CompoundPlugin(
            CheckAblePlugin(appendable=lambda {}),
            PureVisiblePlugin(
                Q(park__enterprise__in=lambda r:r.user.visible_enterprises())
            )
        )
    '''
    def __init__(self, *plugins):
        self.plugins = plugins

    def check_appendable(self, model, request):
        ret = {}
        for p in self.plugins:
            if hasattr(p, 'check_appendable'):
                r = p.check_appendable(model, request)
                if r is False:
                    return r
                ret.update(r)
        return ret

    def apply_able(self, ability, queryset, request):
        ret = queryset
        for p in self.plugins:
            if hasattr(p, 'apply_%s' % ability):
                method = getattr(p, 'apply_%s' % ability)
                ret = method(ret, request)
        return ret

    def check_able(self, ability, model, request):
        ret = {}
        for p in self.plugins:
            if hasattr(p, 'check_%s' % ability):
                method = getattr(p, 'check_%s' % ability)
                r = method(model, request)
                if r is False:
                    return False
                ret.update(r)
        return ret

    def __getattr__(self, name):
        method = None
        prefix = 'apply_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(queryset, request):
                return self.apply_able(ability, queryset, request)
            return method

        prefix = 'check_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(model, request):
                return self.check_able(ability, model, request)
            return method
        raise AttributeError(name)


class CheckApplyPlugin(CompoundPlugin):
    def __init__(self, check={}, apply={}):
        CompoundPlugin.__init__(self,
            CheckAblePlugin(**check),
            ApplyAblePlugin(**apply)
        )


class DjangoAccessPlugin(AccessPluginBase):
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

    def check_appendable(self, model, request):
        return {} if self._has_a('add_%s' % model._meta.model_name, model, request) else False

    def check_changeable(self, model, request):
        return {} if self._has_a('change_%s' % model._meta.model_name, model, request) else False

    def check_deleteable(self, model, request):
        return {} if self._has_a('delete_%s' % model._meta.model_name, model, request) else False

    def check_visible(self, model, request):
        return {} if self._visible(model, request) else False

    def apply_visible(self, queryset, request):
        return queryset.all()

    def apply_changeable(self, queryset, request):
        return queryset.all() if self._has_a('change_%s' % queryset.model._meta.model_name, queryset.model, request) else queryset.none()

    def apply_deleteable(self, queryset, request):
        return queryset.all() if self._has_a('delete_%s' % queryset.model._meta.model_name, queryset.model, request) else queryset.none()

    def __getattr__(self, name):
        prefix = 'apply_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(queryset, request):
                return queryset.all() if self._has_a(ability, queryset.model, request) else queryset.none()
            return method

        prefix = 'check_'
        if name.startswith(prefix):
            ability = name[len(prefix):]

            def method(model, request):
                return {} if self._has_a(ability, model, request) else False
            return method
        raise AttributeError(name)
