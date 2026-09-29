"""Table-less anchor for the panel's scope permissions (specs/012-feature-role-permissions).

A ``Permission`` row needs a content type, so it has to hang off a model. The scopes cross
features, so none of the features' models is their owner. This model has no table and never has
rows: never query it. ``default_permissions = ()`` drops Django's automatic add/change/delete/view
permissions — a scope is not a model.
"""

from django.db import models

from core.domain.access import panel_scope_permissions


class PanelScope(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = panel_scope_permissions()
        verbose_name = "Panel scope"
        verbose_name_plural = "Panel scopes"
        ordering = ["id"]

    def __str__(self) -> str:
        return "Panel scope"
