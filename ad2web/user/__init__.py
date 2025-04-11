# -*- coding: utf-8 -*-
# In ad2web/user/__init__.py

# Import models first
from .models import UserDetail, UserHistory, FailedLogin
from .constants import USER_ROLE, USER_STATUS, ADMIN, USER, ACTIVE, NEW
from .models import User  # Import User after constants are defined
from .views import user