"""
test_oathbond.py — gltest suite for OathBond.

Covers the happy path (promise KEPT → pot refunded to maker + backers) and the
edge cases (BROKEN → slashed to beneficiary, INCONCLUSIVE → escalate, bad input,
backing a closed oath).

Runtime rules followed:
  R16 — write calls use the fluent client API:
        contract.connect(acct).method(args=[...]).transact(value=X)
  R17 — non-deterministic txs need mocks installed FIRST via sim_installMocks,
        with params passed as a BARE DICT (not wrapped in a list).

Run with:  gltest
"""

import json
import pytest
from gltest import get_contract_factory, get_accounts
from gltest.clients import get_gl_provider
from gltest.assertions import tx_execution_failed


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
    ]).transact(value=10_000)

    contract.connect(backer).back_oath(args=[0]).transact(value=5_000)

    _install_mocks(verdict="KEPT", rationale="Release page shows v1.0 published.")
    contract.connect(backer).resolve(args=[0]).transact()

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["verdict"] == "KEPT"
    assert oath["status"] == "SETTLED_KEPT"
    assert oath["pot"] == "15000"


# ── BROKEN → whole pot slashed to the beneficiary ───────────────────────────

def test_broken_slashes_to_beneficiary(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Publish the Q3 transparency report at the docs page",
        "https://example.org/reports/q3",
        beneficiary.address,
        "",
    ]).transact(value=7_000)

    _install_mocks(verdict="BROKEN", rationale="No Q3 report present on the page.")
    contract.connect(maker).resolve(args=[0]).transact()

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["verdict"] == "BROKEN"
    assert oath["status"] == "SETTLED_BROKEN"


# ── INCONCLUSIVE → stays open, then escalate resolves it ────────────────────

def test_inconclusive_then_escalate(deployed):
    contract, maker, backer, beneficiary = deployed

    contract.connect(maker).open_oath(args=[
        "Merge the accessibility PR into the main branch",
        "https://example.org/pr/42",
        beneficiary.address,
        "",
    ]).transact(value=3_000)

    _install_mocks(verdict="INCONCLUSIVE", rationale="Page could not be read.")
    contract.connect(maker).resolve(args=[0]).transact()
    assert json.loads(contract.get_oath(args=[0]).call())["status"] == "INCONCLUSIVE"

    # Stricter re-check now finds the promise kept.
    _install_mocks(verdict="KEPT", rationale="PR #42 shows merged on re-check.")
    contract.connect(maker).escalate(args=[0]).transact()

    oath = json.loads(contract.get_oath(args=[0]).call())
    assert oath["status"] == "SETTLED_KEPT"
    assert oath["escalated"] is True


# ── edge cases ──────────────────────────────────────────────────────────────

def test_zero_stake_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "",
    ]).transact(value=0)
    assert tx_execution_failed(receipt)


def test_short_statement_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "too short", "https://example.org/x", beneficiary.address, "",
    ]).transact(value=1_000)
    assert tx_execution_failed(receipt)


def test_non_url_proof_rejected(deployed):
    contract, maker, _, beneficiary = deployed
    receipt = contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "not-a-url", beneficiary.address, "",
    ]).transact(value=1_000)
    assert tx_execution_failed(receipt)


def test_cannot_back_after_resolution(deployed):
    contract, maker, backer, beneficiary = deployed
    contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "",
    ]).transact(value=1_000)
    _install_mocks(verdict="KEPT")
    contract.connect(maker).resolve(args=[0]).transact()
    receipt = contract.connect(backer).back_oath(args=[0]).transact(value=1_000)
    assert tx_execution_failed(receipt)


def test_cannot_resolve_twice(deployed):
    contract, maker, _, beneficiary = deployed
    contract.connect(maker).open_oath(args=[
        "A sufficiently long promise statement to judge",
        "https://example.org/x", beneficiary.address, "",
    ]).transact(value=1_000)
    _install_mocks(verdict="KEPT")
    contract.connect(maker).resolve(args=[0]).transact()
    receipt = contract.connect(maker).resolve(args=[0]).transact()
    assert tx_execution_failed(receipt)
