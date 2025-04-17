# -*- coding: utf-8 -*-
# REMOVE these lines:
# from .constants import USER, ADMIN # Add any other role constants used
# # Add other status constants if needed, e.g.:
# # from .constants import USER, ADMIN, ACTIVE, INACTIVE

# User role
ADMIN = 0
USER = 1
USER_ROLE = {
    ADMIN: "admin",
    USER: "user",
}

# User status
INACTIVE = 0
NEW = 1
ACTIVE = 2
USER_STATUS = {
    INACTIVE: "inactive",
    NEW: "new",
    ACTIVE: "active",
}

DEFAULT_USER_AVATAR = "default.jpg"
