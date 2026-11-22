"""Direct-mode tests for MergeBounty (BountyEscrow).

Runs the contract in-memory with the GenVM runner — no server, no
network. Web pages and LLM answers are mocked.

Notes on direct-mode semantics (see GenLayer docs, "Testing Strategy"):
- The contract call runs the LEADER side; state changes apply in the
  call. Consensus is checked separately with direct_vm.run_validator(),
  which re-runs the validator against the (possibly swapped) mocks.
  On the real network, consensus gates the state change itself.
- GEN movement via emit_transfer is the official Faucet pattern from
  the docs; the direct VM has no public balance accessor, so the actual
  transfer is verified on testnet after deploy (explorer balance check),
  not here. These tests assert status transitions + stored verdicts.
"""

import json

import pytest

ONE_GEN = 10**18
PR_URL = "https://github.com/mekii69/mergebounty/pull/1"
PR_PAGE = (
    "Pull request #1: Add MergeBounty escrow contract. "
    "Status: Merged into main. Files changed: contracts/bounty_escrow.py. "
    "Checks: all passing. Reviewers: 2 approvals."
)
CRITERIA = (
    "The pull request must be merged into main, add contracts/bounty_escrow.py, "
    "and pass all checks."
)


def _addr_hex(raw: bytes) -> str:
    """Test addresses are raw 20-byte values; the contract stores them as
    checksummed 0x-hex Addresses. Compare case-insensitively."""
    return ("0x" + raw.hex()).lower()


def _create(direct_vm, contract, sender, worker, value=ONE_GEN):
    direct_vm.sender = sender
    direct_vm.value = value
    bounty_id = contract.create_bounty("Add escrow contract", CRITERIA, worker)
    direct_vm.value = 0
    return bounty_id


def _submit(direct_vm, contract, sender, bounty_id, url=PR_URL):
    direct_vm.sender = sender
    contract.submit_evidence(bounty_id, url)


def _mock_merged_pr(direct_vm, met, confidence=90):
    direct_vm.mock_web(
        r".*github\.com.*pull/1.*",
        {"status": 200, "body": PR_PAGE},
    )
    direct_vm.mock_llm(
        r".*impartial bounty judge.*",
        json.dumps(
            {
                "met": met,
                "reason": "The PR is merged into main and adds the contract file."
                if met
                else "The PR is still open and not merged.",
                "confidence": confidence,
            }
        ),
    )


def test_create_bounty(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob, value=2 * ONE_GEN)
    assert int(bounty_id) == 1
    assert int(contract.get_bounty_count()) == 1
    bounty = json.loads(contract.get_bounty(1))
    assert bounty["exists"] is True
    assert bounty["status"] == "FUNDED"
    assert bounty["amount_wei"] == 2 * ONE_GEN
    assert bounty["title"] == "Add escrow contract"
    assert bounty["criteria"] == CRITERIA
    assert bounty["client"].lower() == _addr_hex(direct_alice)
    assert bounty["worker"].lower() == _addr_hex(direct_bob)
    assert bounty["evidence_url"] == ""
    assert contract.get_status(1) == "FUNDED"


def test_create_bounty_zero_worker_reverts(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    direct_vm.sender = direct_alice
    direct_vm.value = ONE_GEN
    zero = type(direct_alice)(b"\x00" * 20)
    with direct_vm.expect_revert("authorized worker"):
        contract.create_bounty("Add escrow contract", CRITERIA, zero)


def test_create_bounty_zero_value_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    with direct_vm.expect_revert("non-zero"):
        contract.create_bounty("Add escrow contract", CRITERIA, direct_bob)


def test_create_bounty_validation(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    direct_vm.sender = direct_alice
    direct_vm.value = ONE_GEN
    with direct_vm.expect_revert("title"):
        contract.create_bounty("", CRITERIA, direct_bob)
    with direct_vm.expect_revert("criteria"):
        contract.create_bounty("Title", "x" * 2001, direct_bob)


def test_submit_evidence(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "EVIDENCE"
    assert bounty["evidence_url"] == PR_URL
    assert bounty["worker"].lower() == _addr_hex(direct_bob)
    # Second submission is rejected: one evidence round in v1.
    with direct_vm.expect_revert("not open for evidence"):
        _submit(direct_vm, contract, direct_bob, bounty_id)


def test_submit_evidence_non_worker_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    # Only the bound worker may submit evidence. A rejected attempt must
    # not consume the slot: the bounty stays FUNDED and the bound worker
    # can still submit afterwards.
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    with direct_vm.expect_revert("only the authorized worker"):
        _submit(direct_vm, contract, direct_charlie, bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "FUNDED"
    assert bounty["evidence_url"] == ""
    assert bounty["worker"].lower() == _addr_hex(direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    assert contract.get_status(bounty_id) == "EVIDENCE"


def test_first_caller_cannot_steal_payout(
    direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie
):
    # Regression test for the steward's finding: before the fix, the first
    # caller of submit_evidence became the payout recipient. Now the
    # front-runner reverts, the bound worker submits, and the payout
    # recipient recorded on the bounty is the bound worker.
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    with direct_vm.expect_revert("only the authorized worker"):
        _submit(direct_vm, contract, direct_charlie, bounty_id)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    _mock_merged_pr(direct_vm, met=True)
    direct_vm.sender = direct_alice
    contract.resolve_bounty(bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "RELEASED"
    assert bounty["worker"].lower() == _addr_hex(direct_bob)


def test_submit_evidence_validation(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    with direct_vm.expect_revert("https://"):
        _submit(direct_vm, contract, direct_bob, bounty_id, "http://example.com/pr/1")
    with direct_vm.expect_revert("bounty not found"):
        _submit(direct_vm, contract, direct_bob, 99)


def test_resolve_releases_on_met(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    _mock_merged_pr(direct_vm, met=True)
    direct_vm.sender = direct_alice
    contract.resolve_bounty(bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "RELEASED"
    verdict = json.loads(bounty["verdict"])
    assert verdict["met"] is True
    assert verdict["confidence"] == 90
    # Validator independently agrees with the leader on the same mocks.
    assert direct_vm.run_validator() is True


def test_resolve_refunds_on_unmet(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    _mock_merged_pr(direct_vm, met=False)
    direct_vm.sender = direct_alice
    contract.resolve_bounty(bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "REFUNDED"
    verdict = json.loads(bounty["verdict"])
    assert verdict["met"] is False
    assert direct_vm.run_validator() is True


def test_resolve_unfetchable_evidence_refunds(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    direct_vm.mock_web(r".*github\.com.*pull/1.*", {"status": 404, "body": "Not Found"})
    direct_vm.sender = direct_alice
    contract.resolve_bounty(bounty_id)
    bounty = json.loads(contract.get_bounty(bounty_id))
    assert bounty["status"] == "REFUNDED"
    verdict = json.loads(bounty["verdict"])
    assert verdict["met"] is False
    assert "could not be fetched" in verdict["reason"]
    assert direct_vm.run_validator() is True


def test_resolve_validator_disagreement(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    _mock_merged_pr(direct_vm, met=True)
    direct_vm.sender = direct_alice
    contract.resolve_bounty(bounty_id)
    # The validator now sees different evidence: the LLM says "not met".
    direct_vm.clear_mocks()
    _mock_merged_pr(direct_vm, met=False)
    assert direct_vm.run_validator() is False


def test_resolve_without_evidence_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("no submitted evidence"):
        contract.resolve_bounty(bounty_id)


def test_cancel_bounty(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    # Only the client can cancel.
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only the bounty client"):
        contract.cancel_bounty(bounty_id)
    direct_vm.sender = direct_alice
    contract.cancel_bounty(bounty_id)
    assert contract.get_status(bounty_id) == "CANCELLED"
    with direct_vm.expect_revert("only a funded bounty"):
        contract.cancel_bounty(bounty_id)


def test_cancel_after_evidence_reverts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/bounty_escrow.py")
    bounty_id = _create(direct_vm, contract, direct_alice, direct_bob)
    _submit(direct_vm, contract, direct_bob, bounty_id)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only a funded bounty"):
        contract.cancel_bounty(bounty_id)


def test_get_missing_bounty(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/bounty_escrow.py")
    assert json.loads(contract.get_bounty(99)) == {"exists": False}
    assert contract.get_status(99) == "NONE"
    assert int(contract.get_bounty_count()) == 0
