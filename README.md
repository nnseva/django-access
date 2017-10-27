# Django-Access

## Inspiration

The standard Django access control system allows to control access "vertically", basing on the instance types only.

Sometimes the Django-controlled application may be big enough to spread the access to it through the several administrator staff. Every user then should have its own zone of control including some subset of instances of every model in the database. We can say, that in this case we need to have some kind of per-instance, row-level "horizontal" access control.

## Prototypes

We have some number of instance-level (row-level, row-based) access control systems for Django, such as [Django-Guardian](http://django-guardian.readthedocs.io/), or [Django-Authority](http://django-authority.readthedocs.io/en/latest/) which assume that the database always has an instantiated, direct link between user and accessing instance. The Guardian uses general-purpose relations, while Authority prefers some kind of common tags.

Such a way, in these packages, we should explicitly, or in the code, assign an access link for every pair of instance and user. It is a bit hardwork in case of multiple models and lots of users.

## The core functions

The *Django-Access* package introduces a dynamic evaluation-based instance-level (row-level) access control model. It means, that you can define any custom dynamic, evaluated in the code, rules to control, whether the particular user can access to the particular instance. It is your choice, whether the rule is based on general-purpose relations, common tags, having a direct or indirect relation to some special objects in the database, field values, timing conditions, or anything else.

The plugin-based system allows to register any custom plugin assigning access control rules for any particular, or abstract model in your project.

The predefined set of plugin classes contains standard model-level plugin taking in account the former Django permission system like the Django itself does it.

Any combination of plugins may be registeded together for one model using predefined Compound plugin, which checks the access rules per every plugin in the registered combination.

The Model Admin classes introduced by the package are based on the standard Django admin classes and take in account the both, model-wide and instance-level access rules registered in your project.

You can create a Model Admin for your own model, or redefine any standard Django or even third-party Model Admin using a special Admin Mixin introduced by the package.

Access control customization for tastypie and other packages coming soon.
