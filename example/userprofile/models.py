from __future__ import unicode_literals

from django.db import models
from django.db.models.query import Q
from django.contrib.auth.models import User, Group, Permission

from access.plugins import CompoundPlugin, ApplyAblePlugin, CheckAblePlugin, DjangoAccessPlugin
from access.managers import AccessManager

AccessManager.register_plugins({
    Permission:ApplyAblePlugin(visible=lambda queryset, request: queryset.filter(
            Q(user=request.user) |
            Q(group__in=request.user.groups.all())
        )),
    User:CompoundPlugin(
        DjangoAccessPlugin(),
        ApplyAblePlugin(
            changeable=lambda queryset, request: queryset.filter(Q(id=request.user.id)),
            deleteable=lambda queryset, request: queryset.filter(Q(id=request.user.id)),
        )
    ),
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
})

# Create your models here.
