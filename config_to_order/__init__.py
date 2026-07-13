# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.1'

# hooks.py monkey-patches erpnext's BOM/Work Order controllers at import time.
# frappe.get_hooks() (without app_name) serves a Redis-cached hook dict once warm and
# won't re-import hooks.py in a fresh worker process, so import it explicitly here to
# guarantee the patches are applied in every process that touches this app.
from . import hooks  # noqa: F401
