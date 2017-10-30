# Django-Access

## Introduction

### Inspiration

The standard Django access control system allows to control access "vertically", basing on the instance types only.

Sometimes the Django-controlled application may be big enough to spread the access to it among the several administrator staff. Every user then should have its own zone of control including some subset of instances of every model in the database. We can say, that in this case we need to have some kind of per-instance, row-level "horizontal" access control.

### Prototypes

We have some number of instance-level (row-level, row-based) access control systems for Django, such as [Django-Guardian](http://django-guardian.readthedocs.io/), or [Django-Authority](http://django-authority.readthedocs.io/en/latest/) which assume that the database always has an explicit, instantiated, sometimes direct link between user and accessing instance. The Guardian uses general-purpose relations, while Authority prefers some kind of common tags.

Such a way, in these packages, we should explicitly, or in the code, assign an access link for every pair of instance and user. It is a bit hardwork in case of multiple models and lots of users.

### The core package functions

The *Django-Access* package introduces a dynamic evaluation-based instance-level (row-level) access control model. It means, that you can define any custom dynamic, evaluated in the code, rules to control, whether the particular user can access to the particular instance. It is your choice, whether the rule is based on general-purpose relations, common tags, having a direct or indirect relation to some special objects in the database, field values, timing conditions, or anything else.

The plugin-based system allows to register any custom plugin assigning access control rules for any particular, or abstract model in your project.

The predefined set of plugin classes contains standard model-level *DjangoPlugin* taking in account the former Django permission system like the Django itself does it.

Any combination of plugins may be registeded together for one model using predefined *CompoundPlugin*, which checks the access rules per every plugin in the registered combination.

The standalone *AccessModelAdmin*, as well as inline *AccessTabularInline* and *AccessStackedInline* model admin classes, introduced by the package, are based on the standard Django admin classes and take in account the both, model-wide and instance-level access rules registered in your project.

You can create a custom Model Admin class basing on one of model admin classes introduced by the package, for your own model, or redefine any standard Django, or third-party Model Admin, or even your own former Model Admin class in the existent project, using a special *AccessControlMixin* introduced by the package.

Access control customization for tastypie and other packages coming soon.

## Using the *Django-Access* package in the admin

In order to use custom access rules in the admin view, you should tell admin classes to take custom access rules into account. You are doing it using modified admin classes.

For the backward compatibility purposes, if no any rules are customized, the modified admin classes use the default access rules near to former Django model-based access rules controlled by the Django *Permission* system.

### Creating your own admin classes

If you are creating a new project, you can use any of *AccessModelAdmin*, *AccessTabularInline*, and *AccessStackedInline* exactly as you was using *ModelAdmin*, *TabularInline*, and *StackedInline* standard Django model admins. For example:

```python
from django.contrib import admin
from access.admin import *

from someapp.models import *

class ChildAdmin(AccessTabularInline):
    model = SomeChild

# Register your models here.
class ObjectAdmin(AccessModelAdmin):
    inlines = [
        ChildAdmin,
    ]

admin.site.register(SomeObject,ObjectAdmin)
```

### Modifying existent admin classes

If you are using standard Django models with their admins, or third-party packages with their admins, you can modify existent Django admin classes using *AccessControlMixin*, and re-register the admin classes for the correspondent models. For example:

```python
from django.contrib import admin
from django.contrib.auth import models
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from access.admin import *

# Register your models here.
class AccessUserAdmin(AccessControlMixin,UserAdmin):
    pass

class AccessGroupAdmin(AccessControlMixin,GroupAdmin):
    pass

admin.site.unregister(models.User)
admin.site.register(models.User,AccessUserAdmin)
admin.site.unregister(models.Group)
admin.site.register(models.Group,AccessGroupAdmin)
```

Sometimes you need to tune external admin classes to restrict access to some fields etc. You always can do it using
such a technique. For example:

```python
from django.contrib import admin
from django.contrib.auth import models
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from access.admin import *

class AccessUserAdmin(AccessControlMixin,UserAdmin):
    list_editable = ['email']

    def get_list_display(self, request):
        fields = super(AccessUserAdmin, self).get_list_display(request) or []
        if request.user.is_superuser:
            return fields
        return list(set(fields).difference(['password','email']))

    def _fieldsets_exclude(self,fieldsets,exclude):
        ret = []
        for nm,params in fieldsets:
            if not 'fields' in params:
                ret.append((nm,params))
                continue
            fields = list(set(params['fields']).difference(exclude))
            pars = {}
            pars.update(params)
            pars['fields'] = fields
            ret.append((nm,pars))
        return ret

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super(AccessUserAdmin, self).get_fieldsets(request, obj)) or []
        if request.user.is_superuser:
            return fieldsets
        if not obj:
            return fieldsets
        if obj.pk != request.user.pk:
            return self._fieldsets_exclude(fieldsets,['password','email'])
        return fieldsets

class AccessGroupAdmin(AccessControlMixin,GroupAdmin):
    pass

# Register your models here.
admin.site.unregister(models.User)
admin.site.register(models.User,AccessUserAdmin)
admin.site.unregister(models.Group)
admin.site.register(models.Group,AccessGroupAdmin)
```

## Using the *Django-Access* package with third-party applications

You are free to check access to models and instances as the *Django-Access* application does it.

Use lightweight *AccessManager* object instances to control access to the particular model and proper call to the plugin registry.

For example:

```python
...
from access.managers import AccessManager
...

...
    def has_add_permission(self, request):
        r = AccessManager(self.model).appendable(request) != False
        return r

    def has_delete_permission(self, request, obj=None):
        manager = AccessManager(self.model)
        if manager.check_deleteable(self.model, request) == False:
            return False
        if obj:
            return bool(manager.apply_deleteable(obj.__class__.objects.filter(id=obj.id), request))
        return True

    def has_view_permission(self, request, obj=None):
        manager = AccessManager(self.model)
        if manager.check_visible(self.model, request) == False:
            return False
        if obj:
            return bool(manager.apply_visible(obj.__class__.objects.filter(id=obj.id), request))
        return True
```    

Don't forget to check return value of the `check_` method against False value explicitly:

```python
        if not manager.check_visible(self.model, request): # BAD
        if manager.check_visible(self.model, request) == False: # GOOD
```

## Customising access rules using plugins

When the admin is ready to use custom access rules, you can define your own access rules using predefined or your own plugins.

### Registering a plugin

The *Django-Access* package uses a global access control plugin registry. Every plugin instance is registered in the registry using model class where it should be applied as a registry key. Registering plugins can be made using `AccessManager.register_plugin`, or `AccessManager.register_plugins` static methods. The `AccessManager.register_plugin` method takes a model class, and plugin instance as two parameters, while `AccessManager.register_plugins` takes one dictionary parameter with model classes as keys, and plugin instances as values.

You can register plugins for any model classes, either standard, or from third-pary packages, or your own. *Note* that you can register the only one plugin instance for the model. Registering another plugin instance for the same model unregisters the previous one. In order to combine several plugins, you can use a provided *CompoundPlugin* as described below.

You can register a plugin for any `Model` class, even an *abstract*. This `Model` and *all its ancestors* (except those for which the own plugin is registered) will be controlled by this plugin instance.

We recommend register plugins in the models.py modules immediately after the model definitions.

For example:

```python
from django.db import models
from django.db.models.query import Q
from django.contrib.auth.models import Permission

from access.plugins import CompoundPlugin, ApplyAblePlugin
from access.managers import AccessManager

AccessManager.register_plugins({
    Permission:ApplyAblePlugin(visible=lambda queryset, request: queryset.filter(
            Q(user=request.user) |
            Q(group__in=request.user.groups.all())
        )),
    )
})
```

### Default plugin

When no any plugin is found for the model, the default plugin is used instead. The static method `AccessManager.get_default_plugin` returns a just constructed default plugin instance. The constructor takes no parameters.

The `ACCESS_DEFAULT_PLUGIN` settings value determines a ***string*** referring default plugin class appropriate to import using import_module standard python function.

### Plugin interface

Every plugin provides a set of methods controlling access to the model class as a whole, as well as to separate instances of the model. The *Django-Access* package controls, which methods are defined by the plugin instance and use it to check whether the particular user can have access to the particular instance by the particular way.

All plugin methods controlling the access are having names started from `check_` and `apply_` prefixes. Method whose name is starting from the `check_` prefix controls access to the model as a whole, while method whose name is staring from the `apply_` prefix controls access to separate instances of the model.

The second part of the access control method name defines a particular type of the access. The programmer is free to define any types of the access, but the Model Admin classes of the package itself use the only following access types:

- `appendable`
- `changeable`
- `deleteable`
- `visible`

The `appendable` access type is used only with `check_` prefix, while others - with the both prefixes.

### Check access to the model as a whole

Plugin method controlling access to the whole model is named using a `check_` prefix. The second part of the name determines access type to be checked.

Parameters of the method are the `model` - a Django Model class to be checked, and `request` - a Django Request object determinig an access context to be controlled. The plugin instance is free to verify, what parts of the request access context are important and should be verified against a model. Plugins provided by the *Django-Access* package assume that the request contains a `user` property referring a current user, and user instance has a `is_superuser` flag.

The return value of the `check_` access control method can be of two kinds. The False value forbids access, while a dictionary (even empty) means access allowed. Other value types mean access allowed and may be used also, but are not compatible with CompoundPlugin.

The non-empty dictionary returned from the `check_appendable` method of the plugin will be used to fill the initial values for fields when constructing a new instance of the model. The dictionary keys will be correspondent to instance property names. When the instance property refers to the instance set (reverse part of the foreign key) and value is iterable, values returned from the iterable will be `add`-ed to the property.

### Check access to model instances

Plugin method controlling access to separate model instances is named using an `apply_` prefix. The second part of the name determines access type to be checked.

Parameters of the method are the `queryset` - a Django QuerySet object to be filtered, and `request` - a Django Request object determinig an access context to be controlled. The plugin instance is free to verify, what parts of the request access context are important and should be verified against model instances in the passed QuerySet. Plugins provided by the *Django-Access* package assume that the request contains a `user` field referring a current user, and user instance has a `is_superuser` flag.

The return value of the `apply_` access control method is a QuerySet filtered to only allowed instances accordingly to the granted access.

### Base and extended access types

The Model Admin classes defined in the *Django-Access* package control the only four base access types:

- `appendable`
- `changeable`
- `deleteable`
- `visible`

The `appendable` access type is checked only against a model, using `chack_` prefix, because the instance-level access of such kind has no sence.

The programmer can use any other access type in the same manner as a base ones.

### Combinig access rules using the *CompoundPlugin*

The *CompoundPlugin* can be used to combine access rules determined by several plugins using `and` logic. Model or instance is accessible for the user *only* if all plugins allow such an access. Just pass plugin instances into *CompoundPlugin* instance constructor.

For example:
```python
AccessManager.register_plugins({
    User:CompoundPlugin(
        DjangoAccessPlugin(),
        ApplyAblePlugin(
            changeable=lambda queryset, request: queryset.filter(Q(id=request.user.id)),
            deleteable=lambda queryset, request: queryset.filter(Q(id=request.user.id)),
        )
    ),
})
```

Dictionaries returning by `check_` methods for the same access type of combined plugins are united and returned to the system by the *CompoundPlugin*.

If any of combined plugins `check_` method returns False, the correspondent *CompoundPlugin* method returns False, and other dictionaries returned by combined plugins `check_` method for the same access type are ignored.

`QuerySet` objects are filtered sequentially by all `apply_` methods of combined plugins for the same access type and the resulting filtered `QuerySet` object is returned by the correspondent method of the *CompoundPlugin*

### Creating dynamic access rules using the *CheckAblePlugin* or the *ApplyAblePlugin*

These plugins use keyword parameters of the constructor, correspondent to access types to take a callable determining the result of the correspondent access rule method. The *CheckAblePlugin* describes model-wide access rules, while *ApplyAblePlugin* determines instance-level access rules.

```python
    Group:CompoundPlugin(
        DjangoAccessPlugin(),
        CheckAblePlugin(
            appendable=lambda model, request: {'user_set':[request.user]}
        ),
        ApplyAblePlugin(
            visible=lambda queryset, request: queryset.filter(user=request.user),
            changeable=lambda queryset, request: queryset.filter(user=request.user),
            deleteable=lambda queryset, request: queryset.filter(user=request.user),
        ),
    )
```

### Simplified model-wide access rules using the *SimpleCheckPlugin*

This plugin simplifies checking for model-wide rules as in the *CheckAblePlugin* reducting it to return values of False and True instead of False and dictionary.

For example:

```python
        SimpleCheckPlugin(
            appendable=lambda model, request: model._meta.app_label == "custom"
        )
```

### Backward compatible access rules with *DjangoAccessPlugin*

This plugin defines access rules near to the former Django *Permission* access control system.

The `ACCESS_STRONG_DELETION_CONTROL` settings variable (default is False) controls, whether the restriction to delete is controlled for models not having a separate (not Inline) Admin. If yes, the forbidden instances are included into the set of protected instances when trying to delete.

For example:

```python
    Group:CompoundPlugin(
        DjangoAccessPlugin(),
        CheckAblePlugin(
            appendable=lambda model, request: {'user_set':[request.user]}
        ),
        ApplyAblePlugin(
            visible=lambda queryset, request: queryset.filter(user=request.user),
            changeable=lambda queryset, request: queryset.filter(user=request.user),
            deleteable=lambda queryset, request: queryset.filter(user=request.user),
        ),
    )
```

## Compatibility issues

The package has been developed and tested against Django v.1.10. Newer versions are coming.

## Examples

Just look into the *example* folder.
