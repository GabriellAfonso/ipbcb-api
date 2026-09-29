import pytest

from core.domain.access import (
    DEFAULT_LEVEL_BY_METHOD,
    PERMISSION_BY_CODENAME,
    ROLE_DISPLAY_NAMES,
    Level,
    Role,
    Scope,
    codename,
    panel_scope_permissions,
    required_level,
    resolve_grants,
    validate_overrides,
)

LEADER_CODENAMES = [
    "members__manage",
    "schedule__manage",
    "songs__manage",
    "gallery__manage",
    "events__manage",
    "notices__manage",
    "reports_hymnal_history__view",
]
MEDIA_CODENAMES = [
    "gallery__manage",
    "events__manage",
    "notices__manage",
    "reports_hymnal_history__view",
]


class TestRequiredLevel:
    @pytest.mark.parametrize(("method", "level"), list(DEFAULT_LEVEL_BY_METHOD.items()))
    def test_default_by_method(self, method: str, level: Level) -> None:
        assert required_level(method, {}) is level

    def test_defaults_are_the_spec_table(self) -> None:
        assert required_level("GET", {}) is Level.VIEW
        assert required_level("POST", {}) is Level.MANAGE
        assert required_level("PUT", {}) is Level.MANAGE
        assert required_level("PATCH", {}) is Level.MANAGE
        assert required_level("DELETE", {}) is Level.OWNER

    def test_unknown_method_fails_closed(self) -> None:
        assert required_level("TRACE", {}) is Level.OWNER

    def test_override_applies_to_its_method_only(self) -> None:
        overrides = {"PATCH": Level.OWNER}
        assert required_level("PATCH", overrides) is Level.OWNER
        assert required_level("GET", overrides) is Level.VIEW

    def test_lowercase_method(self) -> None:
        assert required_level("delete", {}) is Level.OWNER


class TestValidateOverrides:
    @pytest.mark.parametrize(
        "overrides",
        [{}, {"PATCH": Level.MANAGE}, {"PATCH": Level.OWNER}, {"GET": Level.OWNER}],
    )
    def test_equal_or_higher_accepted(self, overrides: dict[str, Level]) -> None:
        validate_overrides(overrides)

    @pytest.mark.parametrize(
        ("overrides", "pattern"),
        [
            ({"PATCH": Level.VIEW}, "PATCH=VIEW .* default MANAGE"),
            ({"DELETE": Level.MANAGE}, "DELETE=MANAGE .* default OWNER"),
        ],
    )
    def test_lower_rejected(self, overrides: dict[str, Level], pattern: str) -> None:
        with pytest.raises(ValueError, match=pattern):
            validate_overrides(overrides)

    def test_unknown_method_rejected(self) -> None:
        with pytest.raises(ValueError, match="'FOO'"):
            validate_overrides({"FOO": Level.OWNER})


class TestCodenames:
    def test_members_manage(self) -> None:
        assert codename(Scope.MEMBERS, Level.MANAGE) == "members__manage"

    def test_report_scope_has_no_dot(self) -> None:
        assert codename(Scope.REPORTS_HYMNAL_HISTORY, Level.VIEW) == (
            "reports_hymnal_history__view"
        )

    def test_table_round_trips_every_pair(self) -> None:
        assert len(PERMISSION_BY_CODENAME) == 21
        for scope in Scope:
            for level in Level:
                assert PERMISSION_BY_CODENAME[codename(scope, level)] == (scope, level)

    def test_meta_permissions_cover_every_pair(self) -> None:
        names = [name for name, _ in panel_scope_permissions()]
        assert sorted(names) == sorted(PERMISSION_BY_CODENAME)


class TestResolveGrants:
    def test_admin_owns_every_scope_without_stored_permissions(self) -> None:
        assert resolve_grants([Role.ADMIN], []) == {scope: Level.OWNER for scope in Scope}

    def test_leader_column(self) -> None:
        assert resolve_grants([Role.LEADER], LEADER_CODENAMES) == {
            Scope.MEMBERS: Level.MANAGE,
            Scope.SCHEDULE: Level.MANAGE,
            Scope.SONGS: Level.MANAGE,
            Scope.GALLERY: Level.MANAGE,
            Scope.EVENTS: Level.MANAGE,
            Scope.NOTICES: Level.MANAGE,
            Scope.REPORTS_HYMNAL_HISTORY: Level.VIEW,
        }

    def test_no_role_grants_nothing(self) -> None:
        assert resolve_grants([], []) == {}

    def test_two_roles_give_the_union(self) -> None:
        levels = resolve_grants([Role.LEADER, Role.MEDIA], LEADER_CODENAMES + MEDIA_CODENAMES)
        assert levels[Scope.GALLERY] is Level.MANAGE
        assert levels[Scope.MEMBERS] is Level.MANAGE

    def test_highest_level_wins(self) -> None:
        levels = resolve_grants([Role.LEADER], ["members__view", "members__owner"])
        assert levels == {Scope.MEMBERS: Level.OWNER}

    def test_unknown_codename_ignored(self) -> None:
        assert resolve_grants([Role.MEDIA], ["view_member", "gallery__manage"]) == {
            Scope.GALLERY: Level.MANAGE
        }


def test_every_role_has_a_display_name() -> None:
    assert set(ROLE_DISPLAY_NAMES) == set(Role)
    assert ROLE_DISPLAY_NAMES[Role.LEADER] == "Liderança"
