"""The worship ministry ("Louvor"), found by name.

Ministry ids change when ministries are recreated in the Django admin, so the setlist feature
identifies the worship ministry by its name instead (specs/017-sunday-setlist-push). Renaming it
disables setlists — logged as ``worship_ministry_missing`` — which is recorded in the members spec.
No Django import here.
"""

import re

# User-facing data, so in Portuguese: it is the ministry's name as typed in the admin.
WORSHIP_MINISTRY_NAME = "Louvor"


def worship_name_pattern() -> str:
    """Regex matching the worship ministry's name: whole name, any case, surrounding whitespace
    ignored. Meant for a case-insensitive lookup (``__iregex``), which ``__iexact`` cannot replace
    because it does not trim.

    >>> worship_name_pattern()
    '^\\\\s*louvor\\\\s*$'
    """
    return rf"^\s*{re.escape(WORSHIP_MINISTRY_NAME.lower())}\s*$"
