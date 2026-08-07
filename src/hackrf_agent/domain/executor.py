"""The chokepoint. Wires every step. ``execute()`` is the only public entry point.

Zero LLM involvement — testable end-to-end with hand-crafted
``ExecuteCommand`` objects.
"""

from __future__ import annotations

import time
from typing import Any

from hackrf_agent.domain.approval import ApprovalPort
from hackrf_agent.domain.audit_service import (
    AuditService,
    make_event,
    new_trace_id,
)
from hackrf_agent.domain.capture_budget import CaptureBudget
from hackrf_agent.domain.handlers import HANDLERS, DriverProtocol, HandlerContext
from hackrf_agent.domain.models import (
    AuditEventType,
    CommandAction,
    CommandResult,
    ExecuteCommand,
    RiskLevel,
)
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import SessionPaths
from hackrf_agent.hw.exceptions import HackrfError


class CommandExecutor:
    """The single funnel every ExecuteCommand passes through.

    Steps, in order:

      1. Mint trace_id; log COMMAND_RECEIVED.
      2. Assess risk (against active grants); log RISK_ASSESSED.
      3. If BLOCKED: log BLOCKED; return refusal.
      4. If requires_confirmation: log APPROVAL_REQUESTED;
         await approval.request(); log APPROVAL_GRANTED or APPROVAL_DENIED.
      5. Dispatch to handler; log EXECUTED on entry.
      6. Format result; log RESULT (with duration_ms and success flag).
    """

    def __init__(
        self,
        *,
        session_id: str,
        risk_assessor: RiskAssessor,
        permissions: PermissionService,
        audit: AuditService,
        driver: DriverProtocol,
        formatter: ResultFormatter,
        approval: ApprovalPort,
        session_paths: SessionPaths,
        capture_budget: CaptureBudget | None = None,
    ) -> None:
        self._session_id = session_id
        self._risk = risk_assessor
        self._permissions = permissions
        self._audit = audit
        self._formatter = formatter
        self._approval = approval
        self._session_paths = session_paths
        # Read the MAX_CAPTURE_MINUTES budget from the env by default.
        # Callers can inject a preset budget for tests.
        self._capture_budget = capture_budget or CaptureBudget.from_env()
        self._handler_ctx = HandlerContext(
            driver=driver,
            permissions=permissions,
            audit=audit,
            session_paths=session_paths,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self, command: ExecuteCommand) -> CommandResult:
        # play_sequence is a composition verb — it drives sub-executes
        # through the same funnel rather than dispatching a handler.
        # Each sub-action gets its own trace_id, risk assessment,
        # permission check, approval flow, and audit trail. play_sequence
        # itself is hardcoded LOW; there is no batching bypass.
        if command.action == CommandAction.PLAY_SEQUENCE:
            return await self._execute_play_sequence(command)

        trace_id = new_trace_id()
        t0 = time.perf_counter()

        # 1. COMMAND_RECEIVED
        await self._audit.log(
            make_event(
                trace_id=trace_id,
                session_id=self._session_id,
                event=AuditEventType.COMMAND_RECEIVED,
                action=command.action,
                payload={
                    "args": command.args,
                    "justification": command.justification,
                    "expected_effect": command.expected_effect,
                },
            )
        )

        # 2. RISK_ASSESSED
        active_grants = await self._permissions.list_active()
        risk = self._risk.assess(command, active_grants)
        await self._audit.log(
            make_event(
                trace_id=trace_id,
                session_id=self._session_id,
                event=AuditEventType.RISK_ASSESSED,
                action=command.action,
                risk_level=risk.level,
                payload={"reason": risk.reason},
                blocked_reason=risk.blocked_reason,
            )
        )

        # 2b. Session-level capture budget (MAX_CAPTURE_MINUTES).
        # Applies to capture_iq only. A capture that would push the
        # cumulative session duration past the cap is refused before any
        # RF activity — even if the per-command duration is inside the
        # normal LOW/MEDIUM tier limits. Belt-and-suspenders.
        if command.action == CommandAction.CAPTURE_IQ:
            duration_s = command.args.get("duration_s")
            if isinstance(duration_s, (int, float)):
                if self._capture_budget.would_exceed(float(duration_s)):
                    reason = (
                        f"session capture budget exhausted: requested "
                        f"{duration_s}s, {self._capture_budget.remaining_seconds():.1f}s "
                        f"remaining"
                    )
                    await self._audit.log(
                        make_event(
                            trace_id=trace_id,
                            session_id=self._session_id,
                            event=AuditEventType.BLOCKED,
                            action=command.action,
                            risk_level=RiskLevel.BLOCKED,
                            blocked_reason=reason,
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                        )
                    )
                    return CommandResult(
                        success=False,
                        action=command.action,
                        message=f"Action blocked by capture budget: {reason}",
                        error=reason,
                    )

        # 3. BLOCKED short-circuit
        if risk.level == RiskLevel.BLOCKED:
            await self._audit.log(
                make_event(
                    trace_id=trace_id,
                    session_id=self._session_id,
                    event=AuditEventType.BLOCKED,
                    action=command.action,
                    risk_level=RiskLevel.BLOCKED,
                    blocked_reason=risk.blocked_reason,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            )
            return CommandResult(
                success=False,
                action=command.action,
                message=f"Action blocked by safety gate: {risk.blocked_reason or risk.reason}",
                error=risk.blocked_reason or risk.reason,
            )

        # 4. Approval (only if required)
        if risk.requires_confirmation:
            await self._audit.log(
                make_event(
                    trace_id=trace_id,
                    session_id=self._session_id,
                    event=AuditEventType.APPROVAL_REQUESTED,
                    action=command.action,
                    risk_level=risk.level,
                )
            )
            approved = await self._approval.request(command, risk)
            if not approved:
                await self._audit.log(
                    make_event(
                        trace_id=trace_id,
                        session_id=self._session_id,
                        event=AuditEventType.APPROVAL_DENIED,
                        action=command.action,
                        risk_level=risk.level,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                )
                return CommandResult(
                    success=False,
                    action=command.action,
                    message="User denied approval.",
                    error="approval_denied",
                )
            await self._audit.log(
                make_event(
                    trace_id=trace_id,
                    session_id=self._session_id,
                    event=AuditEventType.APPROVAL_GRANTED,
                    action=command.action,
                    risk_level=risk.level,
                )
            )

        # 5. EXECUTED + dispatch
        handler = HANDLERS.get(command.action)
        if handler is None:
            # Should be unreachable — the risk assessor blocks unknown actions.
            await self._audit.log(
                make_event(
                    trace_id=trace_id,
                    session_id=self._session_id,
                    event=AuditEventType.RESULT,
                    action=command.action,
                    risk_level=risk.level,
                    blocked_reason="no handler",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            )
            return CommandResult(
                success=False,
                action=command.action,
                message="Internal error: no handler registered for this action.",
                error="no_handler",
            )

        await self._audit.log(
            make_event(
                trace_id=trace_id,
                session_id=self._session_id,
                event=AuditEventType.EXECUTED,
                action=command.action,
                risk_level=risk.level,
            )
        )

        try:
            raw = await handler(self._handler_ctx, command.args)
            data = self._format(command.action, raw)
            success = True
            error: str | None = None
            message = f"Completed {command.action.value}."
            # Charge the capture budget on successful capture_iq only.
            if command.action == CommandAction.CAPTURE_IQ:
                duration_s = command.args.get("duration_s")
                if isinstance(duration_s, (int, float)):
                    self._capture_budget.charge(float(duration_s))
        except HackrfError as e:
            data = {}
            success = False
            error = f"{type(e).__name__}: {e}"
            message = f"Hardware error during {command.action.value}."
        except ValueError as e:
            # Handler validated a path or arg and rejected it.
            data = {}
            success = False
            error = f"ValueError: {e}"
            message = f"Argument error during {command.action.value}."

        duration_ms = int((time.perf_counter() - t0) * 1000)

        # 6. RESULT
        await self._audit.log(
            make_event(
                trace_id=trace_id,
                session_id=self._session_id,
                event=AuditEventType.RESULT,
                action=command.action,
                risk_level=risk.level,
                payload={"success": success, "data": data, "error": error},
                duration_ms=duration_ms,
            )
        )

        return CommandResult(
            success=success,
            action=command.action,
            message=message,
            data=data,
            error=error,
        )

    # ------------------------------------------------------------------
    # play_sequence
    # ------------------------------------------------------------------

    async def _execute_play_sequence(
        self, command: ExecuteCommand
    ) -> CommandResult:
        """Run each sub-action through the full funnel, in order.

        No batching bypass — each step re-enters execute() with its own
        trace_id, risk assessment, permission check, approval flow, and
        audit trail. play_sequence itself is hardcoded LOW.
        """
        from hackrf_agent.domain.args import PlaySequenceArgs

        try:
            parsed = PlaySequenceArgs(**command.args)
        except Exception as e:  # noqa: BLE001 — surface pydantic errors as failures
            return CommandResult(
                success=False,
                action=command.action,
                message="play_sequence args failed validation.",
                error=f"{type(e).__name__}: {e}",
            )

        results: list[dict[str, Any]] = []
        overall_success = True

        for i, step in enumerate(parsed.steps):
            try:
                sub_action = CommandAction(step.action)
            except ValueError:
                results.append(
                    {
                        "step": i,
                        "action": step.action,
                        "success": False,
                        "message": f"unknown action: {step.action}",
                        "error": "unknown_action",
                    }
                )
                overall_success = False
                if parsed.stop_on_error:
                    break
                continue

            sub_command = ExecuteCommand(
                action=sub_action,
                args=step.args,
                justification=(
                    f"play_sequence step {i + 1}/{len(parsed.steps)}: "
                    f"{command.justification}"
                ),
                expected_effect=command.expected_effect,
            )
            sub_result = await self.execute(sub_command)
            results.append(
                {
                    "step": i,
                    "action": step.action,
                    "success": sub_result.success,
                    "message": sub_result.message,
                    "data": sub_result.data,
                    "error": sub_result.error,
                }
            )
            if not sub_result.success:
                overall_success = False
                if parsed.stop_on_error:
                    break

        return CommandResult(
            success=overall_success,
            action=command.action,
            message=(
                f"play_sequence completed {len(results)}/{len(parsed.steps)} steps."
            ),
            data={
                "risk_tier": RiskLevel.LOW.value,
                "steps": results,
                "num_completed": len(results),
                "num_total": len(parsed.steps),
                "stopped_on_error": parsed.stop_on_error and not overall_success,
            },
        )

    # ------------------------------------------------------------------
    # Formatter dispatch
    # ------------------------------------------------------------------

    def _format(self, action: CommandAction, raw: dict[str, Any]) -> dict[str, Any]:
        f = self._formatter
        kind = raw["kind"]
        if kind == "device_info":
            return f.format_device_info(raw["info"])
        if kind == "sweep":
            return f.format_sweep(
                magnitude_db=raw["magnitude_db"],
                freqs_hz=raw["freqs_hz"],
                start_hz=raw["start_hz"],
                stop_hz=raw["stop_hz"],
                sample_rate_hz=raw.get("sample_rate_hz", 2_000_000),
                fft_size=raw.get("fft_size", 4096),
            )
        if kind == "sweep_bulk":
            sample_rate_hz = raw.get("sample_rate_hz", 2_000_000)
            fft_size = raw.get("fft_size", 4096)
            per_range = [
                f.format_sweep(
                    magnitude_db=s["magnitude_db"],
                    freqs_hz=s["freqs_hz"],
                    start_hz=s["start_hz"],
                    stop_hz=s["stop_hz"],
                    sample_rate_hz=sample_rate_hz,
                    fft_size=fft_size,
                )
                for s in raw["sweeps"]
            ]
            return {
                "num_ranges": len(per_range),
                "sweeps": per_range,
            }
        if kind == "capture":
            return f.format_capture(
                iq_path=raw["iq_path"],
                center_hz=raw["center_hz"],
                sample_rate_hz=raw["sample_rate_hz"],
                num_samples=raw["num_samples"],
                session_paths=self._session_paths,
            )
        if kind == "transmit":
            return f.format_transmit(
                center_hz=raw["center_hz"],
                sample_rate_hz=raw["sample_rate_hz"],
                iq_path=raw["iq_path"],
                txvga_gain_db=raw["txvga_gain_db"],
                duration_s=raw["duration_s"],
            )
        if kind == "read_iq_summary":
            return f.format_read_iq_summary(
                iq_path=raw["iq_path"],
                center_hz=raw["center_hz"],
                sample_rate_hz=raw["sample_rate_hz"],
                session_paths=self._session_paths,
            )
        if kind == "decode_ook":
            return f.format_decode_ook(iq_path=raw["iq_path"])
        if kind == "grant_list":
            return f.format_grant_list(raw["grants"])
        if kind == "audit_query":
            return f.format_audit_query(raw["rows"])
        if kind in (
            "knowledge_list_topics",
            "knowledge_read",
            "knowledge_search",
            "knowledge_lookup_band",
            "knowledge_lookup_modulation",
            "knowledge_lookup_protocol",
            "knowledge_lookup_keyfob",
            "knowledge_lookup_decoder",
            "knowledge_bibliography",
            "knowledge_random",
            "knowledge_explain_signal",
            "knowledge_cross_reference",
            "knowledge_verify_claim",
            "analyze_iq_modulation",
            "analyze_iq_symbols",
            "analyze_iq_spectrogram",
            "analyze_iq_carrier_frequency",
            "decode_manchester",
            "decode_pwm",
            "decode_ppm",
            "decode_nrz",
            "decode_pocsag",
            "decode_ads_b",
            "decode_rtty",
            "decode_ax25",
            "decode_aprs",
        ):
            # Knowledge + analysis handlers return JSON-primitive payloads
            # directly. Strip the internal "kind" marker before returning.
            out = dict(raw)
            out.pop("kind", None)
            out["risk_tier"] = RiskLevel.LOW.value
            return out
        raise ValueError(f"unknown formatter kind: {kind!r}")
