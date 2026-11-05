"""Executable lifecycle conformance gate for any KCH_PSA engine adapter."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import importlib
import json
from pathlib import Path
from typing import Callable

from .canonical import canonical_json, digest, utc_now
from .contracts import EngineState, ExecutionReceipt, OperationStatus, SessionState, SideEffectState
from .engine import EngineAdapter, SessionCreateRequest
from .ledger import HashChainLedger


@dataclass(frozen=True, slots=True)
class ConformanceGate:
    gate: str
    passed: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    schema: str
    adapter: str
    mission_id: str
    started_at: str
    ended_at: str
    gates: tuple[ConformanceGate, ...]
    ledger_events: int
    ledger_head: str
    status: str
    error: str | None = None

    def to_json(self) -> str:
        return canonical_json(self)


def _receipt_gate(
    receipt: ExecutionReceipt,
    *,
    mission_id: str,
    engine_id: str,
    operation: str,
    request: object,
) -> tuple[bool, str]:
    mismatches: list[str] = []
    if receipt.mission_id != mission_id:
        mismatches.append("MISSION")
    if receipt.engine_id != engine_id:
        mismatches.append("ENGINE")
    if receipt.operation != operation:
        mismatches.append("OPERATION")
    if receipt.request_sha256 != digest(request):
        mismatches.append("REQUEST_DIGEST")
    if receipt.status is not OperationStatus.PASS:
        mismatches.append("STATUS")
    if receipt.side_effect is not SideEffectState.NONE:
        mismatches.append("SIDE_EFFECT")
    return not mismatches, "MATCH" if not mismatches else "MISMATCH:" + ",".join(mismatches)


async def run_lifecycle(
    adapter: EngineAdapter,
    *,
    mission_id: str,
    ledger: HashChainLedger,
) -> ConformanceResult:
    """Run probe -> create -> cancel -> close without model, tools or external effects."""

    started_at = utc_now()
    gates: list[ConformanceGate] = []
    adapter_name = f"{type(adapter).__module__}:{type(adapter).__qualname__}"
    error_text: str | None = None
    try:
        probe = await adapter.probe()
        ledger.append("ENGINE_PROBE", {"probe": asdict(probe), "sha256": probe.sha256})
        available = probe.state in {EngineState.AVAILABLE, EngineState.CONNECTED}
        gates.append(ConformanceGate("PROBE_AVAILABLE", available, probe.state.value))
        if not available:
            raise RuntimeError(f"ENGINE_NOT_AVAILABLE:{probe.state.value}")

        request = SessionCreateRequest(mission_id=mission_id)
        ledger.append("SESSION_CREATE_INTENT", {"request": asdict(request), "sha256": digest(request)})
        session, create_receipt = await adapter.create(request)
        ledger.append("SESSION_CREATE_RECEIPT", asdict(create_receipt))
        receipt_ok, receipt_evidence = _receipt_gate(
            create_receipt,
            mission_id=mission_id,
            engine_id=probe.engine_id,
            operation="session.create",
            request=request,
        )
        create_ok = (
            receipt_ok
            and session.state is SessionState.CREATED
            and session.mission_id == mission_id
            and session.engine_id == probe.engine_id
        )
        gates.append(
            ConformanceGate(
                "CREATE_NO_EFFECT",
                create_ok,
                f"session={session.state.value};receipt={receipt_evidence}",
            )
        )
        if not create_ok:
            raise RuntimeError("CREATE_CONTRACT_FAILED")

        cancel_request = {
            "session": session.engine_session_id,
            "reason": "KCH_PSA_CONFORMANCE",
        }
        cancel_receipt = await adapter.cancel(session, cancel_request["reason"])
        ledger.append("SESSION_CANCEL_RECEIPT", asdict(cancel_receipt))
        cancel_ok, cancel_evidence = _receipt_gate(
            cancel_receipt,
            mission_id=mission_id,
            engine_id=probe.engine_id,
            operation="session.cancel",
            request=cancel_request,
        )
        gates.append(ConformanceGate("CANCEL_NO_EFFECT", cancel_ok, cancel_evidence))
        if not cancel_ok:
            raise RuntimeError("CANCEL_CONTRACT_FAILED")

        close_receipt = await adapter.close()
        ledger.append("ENGINE_CLOSE_RECEIPT", asdict(close_receipt))
        close_ok, close_evidence = _receipt_gate(
            close_receipt,
            mission_id=mission_id,
            engine_id=probe.engine_id,
            operation="engine.close",
            request={},
        )
        gates.append(ConformanceGate("CLOSE_NO_EFFECT", close_ok, close_evidence))
        if not close_ok:
            raise RuntimeError("CLOSE_CONTRACT_FAILED")
    except Exception as error:
        error_text = f"{type(error).__name__}:{error}"
        ledger.append("CONFORMANCE_FAILED", {"error": error_text})
        try:
            await adapter.close()
        except Exception as close_error:
            ledger.append(
                "CONFORMANCE_EMERGENCY_CLOSE_FAILED",
                {"error": f"{type(close_error).__name__}:{close_error}"},
            )

    verification = ledger.verify()
    gates.append(
        ConformanceGate(
            "LEDGER_REPLAY",
            verification.valid,
            verification.reason or f"events={verification.event_count}",
        )
    )
    status = "PASS" if error_text is None and all(gate.passed for gate in gates) else "FAIL"
    return ConformanceResult(
        schema="kch-psa.engine-conformance.v0.1.0",
        adapter=adapter_name,
        mission_id=mission_id,
        started_at=started_at,
        ended_at=utc_now(),
        gates=tuple(gates),
        ledger_events=verification.event_count,
        ledger_head=verification.head,
        status=status,
        error=error_text,
    )


def _load_factory(spec: str) -> Callable[[], EngineAdapter]:
    if ":" not in spec:
        raise ValueError("ADAPTER_SPEC_MUST_BE_MODULE_COLON_FACTORY")
    module_name, factory_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise ValueError("ADAPTER_FACTORY_NOT_CALLABLE")
    return factory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, help="Python module:factory")
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    factory = _load_factory(args.adapter)
    with HashChainLedger(args.ledger) as ledger:
        result = asyncio.run(run_lifecycle(factory(), mission_id=args.mission_id, ledger=ledger))
    encoded = result.to_json()
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps(json.loads(encoded), ensure_ascii=False, indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
