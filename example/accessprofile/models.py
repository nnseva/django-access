from __future__ import unicode_literals

from django.db import models
from django.db.models.query import Q
from django.contrib.auth.models import User, Group, Permission

from access.plugins import CompoundPlugin, ApplyAblePlugin, CheckAblePlugin, DjangoAccessPlugin
from access.managers import AccessManager

from someapp.models import SomeObject, SomeChild


AccessManager.register_plugins({
    Permission:ApplyAblePlugin(visible=lambda queryset, request: queryset.filter(
            Q(user=request.user) |
            Q(group__in=request.user.groups.all())
        )),
    User:CompoundPlugin(
        CheckAblePlugin(
            appendable=lambda model, request: DjangoAccessPlugin().check_appendable(model, request),
#            deleteable=lambda model, request: DjangoAccessPlugin().check_deleteable(model, request),
        ),
        ApplyAblePlugin(
            changeable=lambda queryset, request:
                queryset.filter(Q(id=request.user.id))
                    if DjangoAccessPlugin().check_changeable(queryset.model, request) is False
                    else
                (
                    queryset.all()
                        if request.user.is_superuser
                        else
                    queryset.all().exclude(is_superuser=True)
                ),
            deleteable=lambda queryset, request:
                queryset.filter(Q(id=request.user.id))
                    if DjangoAccessPlugin().check_deleteable(queryset.model, request) is False
                    else
                (
                    queryset.all()
                        if request.user.is_superuser
                        else
                    queryset.all().exclude(is_superuser=True)
                ),
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

AccessManager.register_plugins({
    SomeObject: CompoundPlugin(
        DjangoAccessPlugin(),
        ApplyAblePlugin(
            visible=lambda queryset, request: queryset.filter(Q(editor_group__in=request.user.groups.all())|Q(viewer_groups__in=request.user.groups.all())),
            changeable=lambda queryset, request: queryset.filter(Q(editor_group__in=request.user.groups.all())),
            #deleteable=lambda queryset, request: queryset.filter(Q(editor_group__in=request.user.groups.all())).exclude(Q(children__is_archived=False)),
            deleteable=lambda queryset, request: queryset.filter(Q(editor_group__in=request.user.groups.all())),
        )
    ),
    SomeChild: CompoundPlugin(
        DjangoAccessPlugin(),
        ApplyAblePlugin(
            visible=lambda queryset, request: queryset.filter(Q(is_archived=False)&(Q(parent__editor_group__in=request.user.groups.all())|Q(parent__viewer_groups__in=request.user.groups.all()))),
            changeable=lambda queryset, request: queryset.filter(Q(parent__editor_group__in=request.user.groups.all())),
            deleteable=lambda queryset, request: queryset.filter(Q(is_archived=True) & Q(parent__editor_group__in=request.user.groups.all())),
        )
    )
})
