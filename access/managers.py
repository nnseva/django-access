import traceback

from django.db.models import Model

import logging
logger = logging.getLogger(__name__)


class AccessManager(object):
    '''
    The AccessManager class is a lightweight class like django.db.Manager class.
    It can be constructed from the Model class at any time to create controlled
    querysets to the model, and contains access control methods for all kinds
    of operations.

    The static part of the class allows to register/unregister access plugins
    for the particular model classes.

    The verify_something and apply_something calls are passed to the registered or default
    plugin for the passed model or queryset correspondently.

    The model passed to the constructor is used as a parameter for check (and model.objects.all() as
    a parameter for apply) against correspondent abilities in visible, appendable, changeable,
    and deleteable calls.
    '''
    plugins = {}
    default_plugins = {}

    @classmethod
    def register_plugins(cls, plugins):
        '''
        Reguster plugins. The plugins parameter should be dict mapping model to plugin.

        Just calls a register_plugin for every such a pair.
        '''
        for model in plugins:
            cls.register_plugin(model, plugins[model])

    @classmethod
    def register_plugin(cls, model, plugin):
        '''
        Reguster a plugin for the model.

        The only one plugin can be registered. If you want to combine plugins, use CompoundPlugin.
        '''
        logger.info("Plugin registered for %s: %s", model, plugin)
        cls.plugins[model] = plugin

    @classmethod
    def unregister_plugins(cls, plugins):
        '''
        Unreguster plugins. The plugins parameter may be any iterable of models, or dict having models as keys,

        Just calls an unregister_plugin for every such a model.
        '''
        for model in plugins:
            cls.unregister_plugin(model)

    @classmethod
    def unregister_plugin(cls, model):
        '''
        Unreguster a plugin for the model.
        '''
        logger.info("Plugin unregistered for %s", model)
        del cls.plugins[model]

    @classmethod
    def get_default_plugin(cls):
        '''
        Return a default plugin.
        '''
        from importlib import import_module
        from django.conf import settings
        default_plugin = getattr(settings, 'ACCESS_DEFAULT_PLUGIN', "access.plugins.DjangoAccessPlugin")
        if default_plugin not in cls.default_plugins:
            logger.info("Creating a default plugin: %s", default_plugin)
            path = default_plugin.split('.')
            plugin_path = '.'.join(path[:-1])
            plugin_name = path[-1]
            DefaultPlugin = getattr(import_module(plugin_path), plugin_name)
            cls.default_plugins[default_plugin] = DefaultPlugin()
        return cls.default_plugins[default_plugin]

    @classmethod
    def plugin_for(cls, model):
        '''
        Find and return a plugin for this model. Uses inheritance to find a model where the plugin is registered.
        '''
        logger.debug("Getting a plugin for: %s", model)
        if not issubclass(model, Model):
            return
        if model in cls.plugins:
            return cls.plugins[model]
        for b in model.__bases__:
            p = cls.plugin_for(b)
            if p:
                return p

    def __init__(self, model):
        '''
        Create AccessManager object passing Model subclass (not instance!) to the constructor.
        '''
        self.model = model

    def get_queryset(self):
        '''
        Returns a queryset of all model instances
        '''
        return self.model.objects.all()

    # Queryset-related checks
    def apply_able(self, ability, queryset, request):
        '''
        The apply_able(ability, queryset, request) applies the ability
        to the instance set determined by the queryset for the user requesting the request.

        This call is passed to the resolved or default plugin if the plugin is
        found and the method named apply_<ability> is found in the plugin, and returns
        a value returned by the found plugin method.

        A queryset restricted by only allowed objects assumed to be returned by the plugin.

        Standard `visible`, `changeable`, and `deleteable` abilities are requested
        by the admin.
        '''
        p = self.plugin_for(queryset.model)
        if not hasattr(p, 'apply_%s' % ability):
            p = self.get_default_plugin()
        if not hasattr(p, 'apply_%s' % ability):
            logger.debug("Appy ability %s not found for %s", ability, queryset.model)
            return queryset
        logger.debug("Apply ability %s is checking for %s", ability, queryset.model)
        m = getattr(p, 'apply_%s' % ability)
        return m(queryset, request)

    # Model-related checks
    def check_able(self, ability, model, request):
        '''
        This call is deprecated now and is passed to the verify_able with the empty attribute dictionary.
        Remove it's direct call from your code.
        '''
        logger.warning("The `check_able` call is deprecated, use `verify_able` instead")
        logger.debug(">>> %s", ''.join(traceback.format_stack()))
        attributes = {}
        return attributes if self.verify_able(ability, model, attributes, request) else False

    # Model attributes verify
    def verify_able(self, ability, model, request, attributes={}):
        '''
        The `verify_able` applies the ability to the model for the user requesting the request.

        The attributes dictionary contains new attributes values for the creating or updating instance.

        This call is passed to the resolved or default plugin if the plugin is
        found and the method named verify_<ability> is found in the plugin, and returns
        a value returned by the found plugin method.

        A False (or equal) value assumed to be returned by the plugin if the user is not able
        to use this model with this attributes in requested manner. The True value will be returned
        to the caller and allows requested operation for the model.

        The attributes dictionary may be changed by the plugin to adopt attribute values for some reason.
        The caller should use the modified attributes dictionary to do the requested operation instead
        of the passed one.

        Standard `visible`, `changeable`, and `deleteable` abilities are requested
        by the admin.
        '''
        p = self.plugin_for(model)
        if not hasattr(p, 'verify_%s' % ability) and not hasattr(p, 'check_%s' % ability):
            p = self.get_default_plugin()
        if not hasattr(p, 'verify_%s' % ability):
            logger.debug("Verify ability %s not found for %s", ability, model)
            if not hasattr(p, 'check_%s' % ability):
                return True
            logger.warning("The `check_%s` is deprecated, use `verify_%s` instead: %s", ability, ability)
            logger.debug(">>> %s", ''.join(traceback.format_stack()))
            logger.debug("Check ability %s is checking for %s", ability, model)
            m = getattr(p, 'check_%s' % ability)
            ret = m(model, request)
            if ret and isinstance(ret, dict):
                attributes.update(ret)
            return ret is not False

        logger.debug("Verify ability %s is checking for %s", ability, model)
        m = getattr(p, 'verify_%s' % ability)
        return m(model, request, attributes=attributes)

    def visible(self, request, attributes={}):
        '''
        Checks the both, verify_visible and apply_visible, against the owned model and it's instance set
        '''
        return self.apply_visible(
            self.get_queryset(), request
        ) if self.verify_visible(
            self.model, request, attributes=attributes
        ) else self.get_queryset().none()

    def changeable(self, request, attributes={}):
        '''
        Checks the both, verify_changeable and apply_changeable, against the owned model and it's instance set
        '''
        return self.apply_changeable(
            self.get_queryset(), request
        ) if self.verify_changeable(
            self.model, request, attributes=attributes
        ) else self.get_queryset().none()

    def deleteable(self, request, attributes={}):
        '''
        Checks the both, verify_deleteable and apply_deleteable, against the owned model and it's instance set
        '''
        return self.apply_deleteable(
            self.get_queryset(), request
        ) if self.verify_deleteable(
            self.model, request, attributes=attributes
        ) else self.get_queryset().none()

    def appendable(self, request, attributes={}):
        '''
        Checks the verify_appendable against the owned model
        '''
        return self.verify_appendable(self.model, request, attributes=attributes)

    def __getattr__(self, name):
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
            logger.warning("The `%s` call is deprecated, use `verify_%s` instead", name, ability)
            logger.debug(">>> %s", ''.join(traceback.format_stack()))

            def method(model, request):
                attributes = {}
                ret = self.verify_able(ability, model, request, attributes=attributes)
                if not ret:
                    return ret
                return attributes
            return method

        raise AttributeError(name)
