from django.test import TestCase
from django.test import Client

import unittest
import mock

import re
import json

import os

from django.core.exceptions import ValidationError

import logging

class TestBase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User, Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Model
        self.user = User.objects.create(username="test",is_active=True,is_staff=True)
        self.user.set_password("test")
        self.user.save()
        #for cn in dir(transport_models):
        #    c = getattr(transport_models,cn)
        #    if isinstance(c,type) and issubclass(c,Model) and not c._meta.abstract and c._meta.app_label == 'transport':
        #        for cc in ['add','change','delete']:
        #            self.user.user_permissions.add(
        #                Permission.objects.get(
        #                    content_type=ContentType.objects.get(app_label=c._meta.app_label,model=c._meta.model_name),
        #                    codename='%s_%s' % (cc,c._meta.model_name),
        #                )
        #            )

    def tearDown(self):
        from django.contrib.auth.models import User, Group, Permission
        User.objects.all().delete()
        Group.objects.all().delete()

class FirstTest(TestBase):
    def test_1_login(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/')
        self.assertEqual(response.status_code,200)
