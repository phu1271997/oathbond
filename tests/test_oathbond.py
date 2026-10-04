"""
test_oathbond.py — gltest suite for OathBond.

Covers the happy path (promise KEPT → pot refunded to maker + backers) and the
edge cases (BROKEN → slashed to the named beneficiary, INCONCLUSIVE → escalate,
bad input, backing a closed oath) PLUS the accountability guardrails:

  * an on-chain due date / settlement window that must pass before `resolve`,
  * a challenge-window delay before an INCONCLUSIVE ruling may be escalated
    (and potentially hardened into a BROKEN ruling + slash),
  * a mandatory, explicit, non-maker beneficiary for broken-oath payouts.

Runtime rules followed:
  R16 — write calls use the fluent client API:
        contract.connect(acct).method(args=[...]).transact(value=X)
  R17 — non-deterministic txs need mocks installed FIRST via sim_installMocks,
        with params passed as a BARE DICT (not wrapped in a list).
  R18 — the consensus clock is driven per-transaction with
        transaction_context={"genvm_datetime": <ISO>} so the contract's
        datetime.now() reads a controlled instant.

Run with:  gltest        (needs a local GenLayer network, e.g. `glsim`)
"""

import json
import pytest
from gltest import get_contract_factory, get_accounts
from gltest.clients import get_gl_provider
from gltest.assertions import tx_execution_failed


# ── clock + mock + balance helpers ──────────────────────────────────────────

# A promise opened "now", due later, resolved after it comes due.
OPEN_AT = "2030-01-01T00:00:00Z"
DUE_AT = "2030-01-10T00:00:00Z"
AFTER_DUE = "2030-01-11T00:00:00Z"
BEFORE_DUE = "2030-01-05T00:00:00Z"
# Challenge window is 24h; these bracket it around an inconclusive-at of AFTER_DUE.
WITHIN_WINDOW = "2030-01-11T06:00:00Z"   # +6h  → escalation still locked
AFTER_WINDOW = "2030-01-12T00:00:01Z"    # +24h01s → escalation allowed


def _at(iso):
    return {"genvm_datetime": iso}


def _install_mocks(verdict: str, rationale: str = "Mock ruling.",
                   body: str = "Mock proof page: release shipped as promised."):
    provider = get_gl_provider()
    provider.make_request(
        method="sim_installMocks",
        params={
            "llm_mocks": {".*": json.dumps({"verdict": verdict, "rationale": rationale})},
            "web_mocks": {".*": {"status": 200, "body": body}},
        },
    )


def _total_locked(contract) -> int:
    return int(contract.get_total_locked(args=[]).call())


@pytest.fixture
def deployed():
    accounts = get_accounts()
    maker, backer, beneficiary = accounts[0], accounts[1], accounts[2]
    factory = get_contract_factory("Contract")
    contract = factory.deploy(args=[])
    return contract, maker, backer, beneficiary


# ── happy path: KEPT → maker + backer refunded ──────────────────────────────

def test_kept_refunds_contributors(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Ship v1.0 of the app to the public release page by Friday",
        "https://example.org/releases/v1.0",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=10_000, transaction_context=_at(OPEN_AT))

    contract.connect(backer).back_oath(args=[0]).transact(value=5_000, transaction_context=_at(OPEN_AT))

    _install_mocks(verdict="KEPT", rationale="Release page shows v1.0 published.")
    contract.connect(backer).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["verdict"] == "KEPT"
    assert oath["status"] == "SETTLED_KEPT"
    assert oath["pot"] == "15000"


# ── BROKEN → whole pot slashed to the named beneficiary ─────────────────────

def test_broken_slashes_to_beneficiary(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Publish the Q3 transparency report at the docs page",
        "https://example.org/reports/q3",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=7_000, transaction_context=_at(OPEN_AT))

    contract.connect(backer).back_oath(args=[0]).transact(value=3_000, transaction_context=_at(OPEN_AT))
    assert _total_locked(contract) == 10_000

    _install_mocks(verdict="BROKEN", rationale="No Q3 report present on the page.")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["verdict"] == "BROKEN"
    assert oath["status"] == "SETTLED_BROKEN"
    assert oath["pot"] == "10000"

    # The whole pot is slashed OUT of escrow to the named, non-maker beneficiary.
    assert oath["beneficiary"].lower() == beneficiary.address.lower()
    assert oath["beneficiary"].lower() != maker.address.lower()
    assert _total_locked(contract) == 0


# ── INCONCLUSIVE → stays open, then escalate (after the window) resolves it ──

def test_inconclusive_then_escalate(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Merge the accessibility PR into the main branch",
        "https://example.org/pr/42",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=3_000, transaction_context=_at(OPEN_AT))

    _install_mocks(verdict="INCONCLUSIVE", rationale="Page could not be read.")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))
    assert json.loads(contract.get_oath(args=[0]).call())["status"] == "INCONCLUSIVE"

    # Once the challenge window has elapsed, a stricter re-check finds it kept.
    _install_mocks(verdict="KEPT", rationale="PR #42 shows merged on re-check.")
    contract.connect(maker).escalate(args=[0]).transact(transaction_context=_at(AFTER_WINDOW))

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["status"] == "SETTLED_KEPT"
    assert oath["escalated"] is True


# ── guardrail: premature resolution is rejected ─────────────────────────────

def test_premature_resolution_rejected(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Ship v2.0 to the public release page",
        "https://example.org/releases/v2.0",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=5_000, transaction_context=_at(OPEN_AT))

    _install_mocks(verdict="KEPT")
    # Before the due date → resolution must be refused.
    receipt = contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(BEFORE_DUE))
    assert tx_execution_failed(receipt)
    assert json.loads(contract.get_oath(args=[0]).call())["status"] == "OPEN"


# ── guardrail: premature escalation (inside the challenge window) is rejected ─

def test_premature_escalation_rejected(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Publish the postmortem at the status page",
        "https://example.org/postmortem",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=4_000, transaction_context=_at(OPEN_AT))

    _install_mocks(verdict="INCONCLUSIVE", rationale="Page could not be read.")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))
    assert json.loads(contract.get_oath(args=[0]).call())["status"] == "INCONCLUSIVE"

    # Still inside the 24h challenge window → escalation must be refused, so the
    # pot cannot be slashed on a merely-unverifiable first read.
    _install_mocks(verdict="INCONCLUSIVE")
    receipt = contract.connect(maker).escalate(args=[0]).transact(transaction_context=_at(WITHIN_WINDOW))
    assert tx_execution_failed(receipt)
    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["status"] == "INCONCLUSIVE"
    assert oath["escalated"] is False


# ── guardrail: an inconclusive oath hardens to BROKEN only after the window ──

def test_escalation_after_window_can_break_and_pays_beneficiary(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Deliver the audited financials to the investors page",
        "https://example.org/financials",
        beneficiary.address,
        "",
        DUE_AT,
    ]).transact(value=9_000, transaction_context=_at(OPEN_AT))
    assert _total_locked(contract) == 9_000

    _install_mocks(verdict="INCONCLUSIVE", rationale="Page could not be read.")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))

    # After the window a still-unverifiable re-check is treated as BROKEN and the
    # pot is slashed to the named beneficiary.
    _install_mocks(verdict="INCONCLUSIVE")
    contract.connect(maker).escalate(args=[0]).transact(transaction_context=_at(AFTER_WINDOW))

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["status"] == "SETTLED_BROKEN"
    assert oath["escalated"] is True
    assert oath["beneficiary"].lower() == beneficiary.address.lower()
    assert oath["beneficiary"].lower() != maker.address.lower()
    assert _total_locked(contract) == 0


# ── guardrail: a broken-oath payout requires an explicit non-maker beneficiary ─

def test_beneficiary_required(deployed):
    contract, maker, _, _ = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", "", "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    assert tx_execution_failed(receipt)


def test_maker_cannot_be_beneficiary(deployed):
    contract, maker, _, _ = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", maker.address, "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    assert tx_execution_failed(receipt)


# ── guardrail: the due date must be in the future ───────────────────────────

def test_past_due_date_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "", BEFORE_DUE,
    ]).transact(value=1_000, transaction_context=_at(AFTER_DUE))
    assert tx_execution_failed(receipt)


# ── edge cases ──────────────────────────────────────────────────────────────

def test_zero_stake_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "", DUE_AT,
    ]).transact(value=0, transaction_context=_at(OPEN_AT))
    assert tx_execution_failed(receipt)


def test_short_statement_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "too short", "https://example.org/x", beneficiary.address, "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    assert tx_execution_failed(receipt)


def test_non_url_proof_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "not-a-url", beneficiary.address, "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    assert tx_execution_failed(receipt)


def test_cannot_back_after_resolution(deployed):
    contract, maker, backer, beneficiary = deployed
    contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    _install_mocks(verdict="KEPT")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))
    receipt = contract.connect(backer).back_oath(args=[0]).transact(value=1_000, transaction_context=_at(AFTER_DUE))
    assert tx_execution_failed(receipt)


def test_cannot_resolve_twice(deployed):
    contract, maker, _, beneficiary = deployed
    contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "", DUE_AT,
    ]).transact(value=1_000, transaction_context=_at(OPEN_AT))
    _install_mocks(verdict="KEPT")
    contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))
    receipt = contract.connect(maker).resolve(args=[0]).transact(transaction_context=_at(AFTER_DUE))
    assert tx_execution_failed(receipt)
