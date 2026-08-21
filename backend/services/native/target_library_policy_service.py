"""Target-only settings boundary with durable policy reconciliation state."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import msgspec

from api.v1.schemas.library_policies import (
    LibraryPolicyApplyPreviewResponse,
    LibraryPolicyApplyRequest,
    LibraryPolicyImpactRequest,
    LibraryPolicyImpactResponse,
    LibraryRestorableRoot,
    LibraryRestorableRootsResponse,
    LibraryRestoreRootsRequest,
    LibraryRootSettings,
    LibrarySettingsResponse,
    LibraryPolicyTreeResponse,
    TypedLibrarySettings,
)
from api.v1.schemas.library_scan_target import ScanRunRequestedResponse
from core.exceptions import TargetStartupInvariantError, ValidationError
from infrastructure.persistence.native_library_store import NativeLibraryStore
from services.native.library_policy_reconciliation_service import (
    LibraryPolicyReconciliationService,
)
from services.native.library_policy_service import LibraryPolicyService
from services.native.library_policy_resolver import LibraryPolicyResolver


class TargetLibraryPolicyService:
    def __init__(
        self,
        settings: LibraryPolicyService,
        reconciliation: LibraryPolicyReconciliationService,
        store: NativeLibraryStore,
        *,
        on_settings_saved: Callable[[], None] | None = None,
        transition_lock: asyncio.Lock | None = None,
    ) -> None:
        self._settings = settings
        self._reconciliation = reconciliation
        self._store = store
        self._on_settings_saved = on_settings_saved
        self._save_lock = transition_lock or asyncio.Lock()

    @staticmethod
    def _settings_json(settings: TypedLibrarySettings) -> str:
        payload = msgspec.to_builtins(settings)
        payload["acoustid_api_key"] = ""
        return msgspec.json.encode(payload).decode()

    async def recover_pending_transition(self) -> bool:
        async with self._save_lock:
            transition = await self._store.get_policy_transition()
            if transition is None or transition["state"] != "prepared":
                return False
            current_revision = LibraryPolicyResolver(
                self._settings.current_settings()
            ).policy_revision
            proposed_revision = transition["proposed_policy_revision"]
            if current_revision == transition["previous_policy_revision"]:
                await self._reconciliation.abort_boundary(
                    proposed_policy_revision=proposed_revision
                )
                return True
            if current_revision != proposed_revision:
                raise TargetStartupInvariantError(
                    "The library policy transition does not match the saved configuration."
                )
            if self._on_settings_saved is not None:
                self._on_settings_saved()
            await self._reconciliation.commit_boundary(
                proposed_policy_revision=proposed_revision
            )
            return True

    async def get_settings(self) -> LibrarySettingsResponse:
        response = self._settings.get_settings()
        pending = await self._store.get_pending_policy()
        if pending is None or not pending["pending_scope_ids"]:
            return response
        payload = msgspec.to_builtins(response)
        payload.update(
            {
                "reconciliation_required": True,
                "reconciliation_state": "awaiting_reconciliation",
                "pending_policy_revision": pending["desired_policy_revision"],
                "affected_scope_ids": pending["pending_scope_ids"],
            }
        )
        return LibrarySettingsResponse(**payload)

    async def save_settings(
        self,
        settings: TypedLibrarySettings,
        *,
        expected_policy_revision: str,
    ) -> LibrarySettingsResponse:
        async with self._save_lock:
            previous_settings = self._settings.current_settings()
            previous_settings_raw = self._settings.current_settings_raw()
            previous_revision = LibraryPolicyResolver(previous_settings).policy_revision
            proposed, changed_scopes = self._settings.prepare_change(
                settings,
                expected_policy_revision=expected_policy_revision,
            )
            if (
                not proposed.settings.library_roots
                and await self._store.catalog_has_tracks()
            ):
                raise ValidationError(
                    "Removing every library root would orphan the existing catalog. "
                    "Keep at least one root, or set its policy to Excluded instead."
                )
            previous_pending = await self._store.get_pending_policy()
            pending_scopes = (
                self._settings.rebase_scopes(
                    previous_pending["pending_scopes"], proposed
                )
                if previous_pending is not None
                else []
            )
            merged = {
                (scope.root_id, scope.relative_path): scope
                for scope in [*pending_scopes, *changed_scopes]
            }
            scopes = self._settings.collapse_scopes(list(merged.values()))
            prepare_task = asyncio.create_task(
                self._reconciliation.prepare_boundary(
                    previous_policy_revision=previous_revision,
                    proposed_policy_revision=proposed.policy_revision,
                    previous_settings_json=self._settings_json(previous_settings),
                    proposed_settings_json=self._settings_json(proposed.settings),
                    scopes=scopes,
                )
            )
            try:
                await asyncio.shield(prepare_task)
            except asyncio.CancelledError:
                await prepare_task
                await self._reconciliation.abort_boundary(
                    proposed_policy_revision=proposed.policy_revision
                )
                raise
            config_persisted = False
            try:
                self._settings.persist_settings(
                    proposed.settings,
                    expected_policy_revision=expected_policy_revision,
                )
                config_persisted = True
                if self._on_settings_saved is not None:
                    self._on_settings_saved()
            except Exception:
                if config_persisted:
                    self._settings.persist_settings(
                        previous_settings_raw,
                        expected_policy_revision=proposed.policy_revision,
                    )
                    if self._on_settings_saved is not None:
                        self._on_settings_saved()
                await self._reconciliation.abort_boundary(
                    proposed_policy_revision=proposed.policy_revision
                )
                raise
            commit_task = asyncio.create_task(
                self._reconciliation.commit_boundary(
                    proposed_policy_revision=proposed.policy_revision
                )
            )
            cancelled = False
            try:
                try:
                    immediate = await asyncio.shield(commit_task)
                except asyncio.CancelledError:
                    cancelled = True
                    immediate = await commit_task
            except Exception:
                self._settings.persist_settings(
                    previous_settings_raw,
                    expected_policy_revision=proposed.policy_revision,
                )
                if self._on_settings_saved is not None:
                    self._on_settings_saved()
                await self._reconciliation.abort_boundary(
                    proposed_policy_revision=proposed.policy_revision
                )
                raise
            if cancelled:
                raise asyncio.CancelledError
            current = await self.get_settings()
            payload = msgspec.to_builtins(current)
            payload["actions_applied"] = [
                "Settings saved. No library work was started.",
                (
                    f"{immediate['cancelled']} queued identification "
                    f"job{'s were' if immediate['cancelled'] != 1 else ' was'} stopped "
                    "because the new policy no longer allows the work."
                ),
            ]
            return LibrarySettingsResponse(**payload)

    @staticmethod
    def _restored_root_label(path: str, used: set[str]) -> str:
        base = Path(path).name or Path(path).anchor or "Library"
        label = base
        number = 2
        while label.casefold() in used:
            label = f"{base} ({number})"
            number += 1
        used.add(label.casefold())
        return label

    async def _known_root_paths(self) -> dict[str, str]:
        # pending scopes freeze the paths from before the wipe
        pending = await self._store.get_pending_policy()
        if pending is None:
            return {}
        return {
            str(scope.root_id): str(scope.root_path)
            for scope in pending["pending_scopes"]
            if scope.relative_path == "." and scope.root_path
        }

    async def _restorable_paths(
        self, missing: list[str]
    ) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        return (
            await self._known_root_paths(),
            await self._store.get_restorable_root_paths(missing),
        )

    @staticmethod
    def _restorable_entry(
        root_id: str,
        known: dict[str, str],
        derived: dict[str, dict[str, object]],
        override: str | None = None,
        *,
        require_catalog_files: bool = False,
    ) -> tuple[str, int] | None:
        """Path and catalog file count for a removed root, or None to skip it.

        `require_catalog_files` gates the *warning* only. A root the catalog
        holds no files from lost nothing when it was removed, so telling the
        operator it is "still used" is a false alarm - provenance rows are
        written for every configured root at migration time regardless of
        content and are never deleted, so otherwise the warning fires forever
        for a root that was only ever a typo. Restoring stays permissive: an
        operator naming a path explicitly may recreate a trackless root.
        """
        info = derived.get(root_id)
        count = int(info["indexed_file_count"]) if info is not None else 0
        if require_catalog_files and count == 0:
            return None
        derived_path = info.get("path") if info is not None else None
        path = override or known.get(root_id) or derived_path
        if path is None:
            return None
        return str(path), count

    async def restorable_roots(self) -> LibraryRestorableRootsResponse:
        migrated = await self._store.get_migrated_root_ids()
        configured = {
            root.id for root in self._settings.current_settings().library_roots
        }
        missing = sorted(migrated - configured)
        known, derived = await self._restorable_paths(missing)
        roots = []
        for root_id in missing:
            entry = self._restorable_entry(
                root_id, known, derived, require_catalog_files=True
            )
            if entry is None:
                continue
            path, count = entry
            roots.append(
                LibraryRestorableRoot(
                    root_id=root_id,
                    path=path,
                    indexed_file_count=count,
                )
            )
        return LibraryRestorableRootsResponse(
            policy_revision=LibraryPolicyResolver(
                self._settings.current_settings()
            ).policy_revision,
            restorable_roots=roots,
        )

    async def restore_roots(
        self, request: LibraryRestoreRootsRequest
    ) -> LibrarySettingsResponse:
        current = self._settings.current_settings()
        migrated = await self._store.get_migrated_root_ids()
        configured = {root.id for root in current.library_roots}
        missing = sorted(migrated - configured)
        if not missing:
            raise ValidationError("There are no removed library roots to restore.")
        overrides = request.paths or {}
        known, derived = await self._restorable_paths(missing)
        used_labels = {root.label.casefold() for root in current.library_roots}
        roots = list(current.library_roots)
        for root_id in missing:
            entry = self._restorable_entry(
                root_id, known, derived, overrides.get(root_id)
            )
            if entry is None:
                continue
            path, _ = entry
            roots.append(
                LibraryRootSettings(
                    id=root_id,
                    path=path,
                    label=self._restored_root_label(path, used_labels),
                    policy="automatic",
                    rules=[],
                )
            )
        if len(roots) == len(current.library_roots):
            raise ValidationError(
                "The removed library roots have no catalog files to recover "
                "their path from."
            )
        return await self.save_settings(
            TypedLibrarySettings(
                library_roots=roots,
                staging_path=current.staging_path,
                naming_template=current.naming_template,
                acoustid_api_key=current.acoustid_api_key,
                enabled=current.enabled,
            ),
            expected_policy_revision=request.expected_policy_revision,
        )

    async def policy_tree(self) -> LibraryPolicyTreeResponse:
        tree = self._settings.policy_tree()
        scopes = [
            (root.id, "." if node.kind == "root" else node.path)
            for root in tree.roots
            for node in [root, *root.children]
        ]
        counts = await self._store.get_policy_scope_counts(scopes)
        payload = msgspec.to_builtins(tree)
        for root in payload["roots"]:
            indexed, on_disk = counts[(root["id"], ".")]
            root["indexed_file_count"] = indexed
            root["on_disk_file_count"] = on_disk
            for child in root["children"]:
                indexed, on_disk = counts[(root["id"], child["path"])]
                child["indexed_file_count"] = indexed
                child["on_disk_file_count"] = on_disk
        return msgspec.convert(payload, type=LibraryPolicyTreeResponse)

    async def preview_impact(
        self, request: LibraryPolicyImpactRequest
    ) -> LibraryPolicyImpactResponse:
        response = self._settings.preview_impact(request)
        scopes = self._settings.preview_scopes(request.settings)
        indexed, on_disk = await self._store.get_policy_scope_total_counts(scopes)
        payload = msgspec.to_builtins(response)
        payload["indexed_file_count"] = indexed
        payload["on_disk_file_count"] = on_disk
        return LibraryPolicyImpactResponse(**payload)

    async def preview_apply(
        self, request: LibraryPolicyApplyRequest
    ) -> LibraryPolicyApplyPreviewResponse:
        preview = await self._reconciliation.preview_apply(
            request.scope_ids,
            expected_policy_revision=request.expected_policy_revision,
        )
        pending = await self._store.get_pending_policy()
        return LibraryPolicyApplyPreviewResponse(
            policy_revision=str(preview["policy_revision"]),
            scope_ids=[str(value) for value in preview["scope_ids"]],
            estimated_file_count=int(preview["estimated_file_count"]),
            content_will_become_unavailable=any(
                scope.effective_policy == "excluded" for scope in preview["scopes"]
            ),
            queued_work_was_cancelled_on_save=bool(
                pending and pending["cancelled_work_count"]
            ),
        )

    async def apply(
        self, request: LibraryPolicyApplyRequest, *, requested_by_user_id: str
    ) -> ScanRunRequestedResponse:
        """Queue the reconcile scan for a saved policy change.

        Unlike ``/library/scan-runs``, this validates scope_ids against the
        *pending* scopes (what the operator is actually reconciling, including a
        removed root) rather than the current settings - a removed root's scope_id
        cannot appear in the current settings by definition, so routing this
        through the generic scan-runs validation always rejected it.
        """
        result = await self._reconciliation.apply(
            request.scope_ids,
            expected_policy_revision=request.expected_policy_revision,
            requested_by_user_id=requested_by_user_id,
        )
        return ScanRunRequestedResponse(
            run_id=result.run_id,
            disposition=result.disposition,
            state=result.state,
            row_revision=result.row_revision,
            queued_reason=result.queued_reason,
            conflicting_kind=result.conflicting_kind,
        )
