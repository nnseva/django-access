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

    The check_something and apply_something calls are passed to the registered or default
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
        The check_able(ability, model, request) applies the ability
        to the model for the user requesting the request.

        This call is passed to the resolved or default plugin if the plugin is
        found and the method named check_<ability> is found in the plugin, and returns
        a value returned by the found plugin method.

        A False (or equal) value assumed to be returned by the plugin if the user is not able
        to use this model in requested manner. Any other value (including None) will be returned
        to the caller and allows requested operation for the model.

        Standard `visible`, `changeable`, and `deleteable` abilities are requested
        by the admin.

        Checking the `appendable` ability returns a dictionary
        of default field values for the model when the user is requesting the instance creation.

        The default values are slightly different for simple and complex fields.

        If the default value is not iterable or is a string, it just assigns to the field
        if the field is empty yet.

        If the default value is iterable, the field assumed to be a RelatedManager
        having an `add` method. Iterated values then are passed to the `add` method.
        '''
        p = self.plugin_for(model)
        if not hasattr(p, 'check_%s' % ability):
            p = self.get_default_plugin()
        if not hasattr(p, 'check_%s' % ability):
            logger.debug("Check ability %s not found for %s", ability, model)
            return {}
        logger.debug("Check ability %s is checking for %s", ability, model)
        m = getattr(p, 'check_%s' % ability)
        return m(model, request)

    def visible(self, request):
        '''
        Checks the both, check_visible and apply_visible, against the owned model and it's instance set
        '''
        return self.apply_visible(self.get_queryset(), request) if self.check_visible(self.model, request) is not False else self.get_queryset().none()

    def changeable(self, request):
        '''
        Checks the both, check_changeable and apply_changeable, against the owned model and it's instance set
        '''
        return self.apply_changeable(self.get_queryset(), request) if self.check_changeable(self.model, request) is not False else self.get_queryset().none()

    def deleteable(self, request):
        '''
        Checks the both, check_deleteable and apply_deleteable, against the owned model and it's instance set
        '''
        return self.apply_deleteable(self.get_queryset(), request) if self.check_deleteable(self.model, request) is not False else self.get_queryset().none()

    def appendable(self, request):
        '''
        Checks the check_appendable against the owned model
        '''
        return self.check_appendable(self.model, request)

    def __getattr__(self, name):
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
