from __future__ import unicode_literals

from django.db import models
from django.db.models import Model
from django.db.models.query import Q
from django.contrib.auth.models import Group

from django.utils.translation import ugettext_lazy as _

from access.plugins import CompoundPlugin, ApplyAblePlugin, CheckAblePlugin, DjangoAccessPlugin
from access.managers import AccessManager

# Create your models here.

class SomeObject(Model):
    editor_group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Editor Group"), related_name='changeable_objects')
    viewer_groups = models.ManyToManyField(Group, verbose_name=_("Viewer Groups"), blank=True, related_name='visible_objects')
    name = models.CharField(max_length=80, verbose_name=_("Name"))

    def __unicode__(self):
        return _("Object: %s") % self.name

    def __str__(self):
        return self.__unicode__()

    class Meta:
        verbose_name = _("Some Object")
        verbose_name_plural = _("Some Objects")
        permissions = (
            ('one','one'),
            ('two','two'),
            ('two_two','two two'),
            ('three_someobject','three'),
            ('four_some_object','four'),
        )


class SomeChild(Model):
    parent = models.ForeignKey(SomeObject, on_delete=models.CASCADE, verbose_name=_("Parent"), related_name='children')
    name = models.CharField(max_length=80, verbose_name=_("Name"))
    is_archived = models.BooleanField(verbose_name=_("Is Archived"), default=False)

    def __unicode__(self):
        if self.is_archived:
            return _("Child: %s (archived)") % self.name
        return _("Child: %s") % self.name

    def __str__(self):
        return self.__unicode__()

    class Meta:
        verbose_name = _("Some Child")
        verbose_name_plural = _("Some Childs")
