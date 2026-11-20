# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""MergeBounty — trustless bounty escrow settled by live evidence.

A client locks GEN in escrow with a task (title + acceptance criteria).
A worker submits evidence as a URL (typically a GitHub pull request).
GenLayer validators fetch the live page and an LLM judges whether the
evidence meets the criteria. On consensus:
  - criteria met   -> the escrowed GEN is released to the worker
  - criteria unmet -> the escrowed GEN is refunded to the client
No human judge, no oracle, no intermediary.

Trust model (v1):
  - resolve() may be called repeatedly while evidence is submitted; each
    attempt is a fresh fetch + fresh LLM judgement.
  - The client can only cancel BEFORE evidence is submitted. Once evidence
    is in, only a consensus verdict settles the bounty.
  - Known limitation: evidence so ambiguous that validators never agree
    on `met` leaves the bounty unresolved (each resolve attempt simply
    fails consensus and the bounty stays open for a later attempt).
"""

import json

from genlayer import *


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")
MAX_TITLE_LEN = 120
MAX_CRITERIA_LEN = 2000
MAX_URL_LEN = 500
EVIDENCE_MAX_CHARS = 6000
MIN_CONFIDENCE = 50

STATUS_FUNDED = "FUNDED"
STATUS_EVIDENCE = "EVIDENCE"
STATUS_RELEASED = "RELEASED"
STATUS_REFUNDED = "REFUNDED"
STATUS_CANCELLED = "CANCELLED"


def _coerce_verdict(result) -> dict:
    """Validate an LLM verdict dict; raise on malformed output.

    The leader raises so the transaction fails cleanly and stays
    retryable; the validator treats malformed output as disagreement.
    """
    if not isinstance(result, dict):
        raise gl.vm.UserError("LLM verdict is not a JSON object")
    met = result.get("met")
    reason = result.get("reason")
    confidence = result.get("confidence")
    if not isinstance(met, bool):
        raise gl.vm.UserError("LLM verdict 'met' must be a boolean")
    if not isinstance(reason, str) or len(reason) == 0:
        raise gl.vm.UserError("LLM verdict 'reason' must be a non-empty string")
    if not isinstance(confidence, int) or confidence < 0 or confidence > 100:
        raise gl.vm.UserError("LLM verdict 'confidence' must be an integer 0-100")
    return {"met": met, "reason": reason, "confidence": confidence}


def _fetch_and_judge(url: str, criteria: str) -> dict:
    """Fetch the evidence URL live, then ask the LLM to judge it.

    Must only be called inside a nondet block (leader_fn / validator_fn).
    A URL that cannot be fetched is judged as 'not met' with high
    confidence — the worker submitted unusable evidence.
    """
    evidence_text = ""
    try:
        response = gl.nondet.web.get(url)
        if response.status == 200:
            evidence_text = response.body.decode("utf-8", errors="ignore")[
                :EVIDENCE_MAX_CHARS
            ]
    except Exception:
        evidence_text = ""
    if len(evidence_text) == 0:
        return {
            "met": False,
            "reason": "Evidence URL could not be fetched or returned no readable content.",
            "confidence": 95,
        }
    prompt = (
        "You are an impartial bounty judge. A client posted a bounty with "
        "acceptance criteria. A worker submitted evidence (a web page) "
        "claiming the work is done. Decide ONLY from the evidence text "
        "whether the criteria are met.\n"
        "ACCEPTANCE CRITERIA:\n" + criteria + "\n"
        "EVIDENCE (fetched live from " + url + "):\n" + evidence_text + "\n"
        'Return a JSON object with exactly these keys: {"met": true/false, '
        '"reason": "one or two sentences citing specific evidence", '
        '"confidence": 0-100}.\n'
        "Rules: met=true ONLY if the evidence clearly shows every part of "
        "the criteria is satisfied. If the evidence is missing, unrelated, "
        "or ambiguous, met=false. Do not guess beyond the evidence."
    )
    result = gl.nondet.exec_prompt(prompt, response_format="json")
    return _coerce_verdict(result)


class BountyEscrow(gl.Contract):
    next_id: u256
    bounty_client: TreeMap[u256, Address]
    bounty_worker: TreeMap[u256, Address]
    bounty_amount: TreeMap[u256, u256]
    bounty_title: TreeMap[u256, str]
    bounty_criteria: TreeMap[u256, str]
    bounty_evidence_url: TreeMap[u256, str]
    bounty_status: TreeMap[u256, str]
    bounty_verdict: TreeMap[u256, str]

    def __init__(self):
        # NOTE: TreeMap fields are NOT assigned here. In the current GenVM
        # runner, storage props are lazily materialised by the property
        # getter bound to the contract's storage slot (see the official
        # boilerplate football_bets.py, whose __init__ is just `pass`).
        # Assigning TreeMap() in __init__ fails validation: the bare
        # instance's type desc does not equal the parameterised field desc.
        self.next_id = u256(1)

    def _require_bounty(self, bounty_id: u256) -> None:
        if bounty_id < u256(1) or bounty_id >= self.next_id:
            raise gl.vm.UserError("bounty not found")

    @gl.public.write.payable
    def create_bounty(self, title: str, criteria: str) -> u256:
        value = gl.message.value
        if value == u256(0):
            raise gl.vm.UserError("bounty must lock a non-zero GEN amount")
        if len(title) == 0 or len(title) > MAX_TITLE_LEN:
            raise gl.vm.UserError("title must be 1-120 chars")
        if len(criteria) == 0 or len(criteria) > MAX_CRITERIA_LEN:
            raise gl.vm.UserError("criteria must be 1-2000 chars")
        bounty_id = self.next_id
        self.next_id = self.next_id + u256(1)
        self.bounty_client[bounty_id] = gl.message.sender_address
        self.bounty_worker[bounty_id] = ZERO_ADDRESS
        self.bounty_amount[bounty_id] = value
        self.bounty_title[bounty_id] = title
        self.bounty_criteria[bounty_id] = criteria
        self.bounty_evidence_url[bounty_id] = ""
        self.bounty_status[bounty_id] = STATUS_FUNDED
        self.bounty_verdict[bounty_id] = ""
        return bounty_id

    @gl.public.write
    def submit_evidence(self, bounty_id: u256, evidence_url: str) -> None:
        self._require_bounty(bounty_id)
        if self.bounty_status[bounty_id] != STATUS_FUNDED:
            raise gl.vm.UserError("bounty is not open for evidence")
        if len(evidence_url) == 0 or len(evidence_url) > MAX_URL_LEN:
            raise gl.vm.UserError("evidence_url must be 1-500 chars")
        if not evidence_url.startswith("https://"):
            raise gl.vm.UserError("evidence_url must start with https://")
        self.bounty_evidence_url[bounty_id] = evidence_url
        self.bounty_worker[bounty_id] = gl.message.sender_address
        self.bounty_status[bounty_id] = STATUS_EVIDENCE

    @gl.public.write
    def resolve_bounty(self, bounty_id: u256) -> None:
        self._require_bounty(bounty_id)
        if self.bounty_status[bounty_id] != STATUS_EVIDENCE:
            raise gl.vm.UserError("bounty has no submitted evidence to resolve")
        url = self.bounty_evidence_url[bounty_id]
        criteria = self.bounty_criteria[bounty_id]

        def leader_fn():
            return _fetch_and_judge(url, criteria)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader = leader_result.calldata
            if not isinstance(leader, dict):
                return False
            try:
                mine = _fetch_and_judge(url, criteria)
            except Exception:
                return False
            if mine.get("met") != leader.get("met"):
                return False
            try:
                if int(mine.get("confidence", 0)) < MIN_CONFIDENCE:
                    return False
                if int(leader.get("confidence", 0)) < MIN_CONFIDENCE:
                    return False
            except Exception:
                return False
            return True

        verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self.bounty_verdict[bounty_id] = json.dumps(verdict)
        amount = self.bounty_amount[bounty_id]
        if verdict.get("met") is True:
            self.bounty_status[bounty_id] = STATUS_RELEASED
            _Recipient(self.bounty_worker[bounty_id]).emit_transfer(value=amount)
        else:
            self.bounty_status[bounty_id] = STATUS_REFUNDED
            _Recipient(self.bounty_client[bounty_id]).emit_transfer(value=amount)

    @gl.public.write
    def cancel_bounty(self, bounty_id: u256) -> None:
        self._require_bounty(bounty_id)
        if self.bounty_status[bounty_id] != STATUS_FUNDED:
            raise gl.vm.UserError("only a funded bounty with no evidence can be cancelled")
        if gl.message.sender_address != self.bounty_client[bounty_id]:
            raise gl.vm.UserError("only the bounty client can cancel it")
        self.bounty_status[bounty_id] = STATUS_CANCELLED
        _Recipient(self.bounty_client[bounty_id]).emit_transfer(
            value=self.bounty_amount[bounty_id]
        )

    @gl.public.view
    def get_bounty(self, bounty_id: u256) -> str:
        if bounty_id < u256(1) or bounty_id >= self.next_id:
            return '{"exists": false}'
        return json.dumps(
            {
                "exists": True,
                "id": int(bounty_id),
                "client": str(self.bounty_client[bounty_id]),
                "worker": str(self.bounty_worker[bounty_id]),
                "amount_wei": int(self.bounty_amount[bounty_id]),
                "title": self.bounty_title[bounty_id],
                "criteria": self.bounty_criteria[bounty_id],
                "evidence_url": self.bounty_evidence_url[bounty_id],
                "status": self.bounty_status[bounty_id],
                "verdict": self.bounty_verdict[bounty_id],
            }
        )

    @gl.public.view
    def get_bounty_count(self) -> u256:
        return self.next_id - u256(1)

    @gl.public.view
    def get_status(self, bounty_id: u256) -> str:
        if bounty_id < u256(1) or bounty_id >= self.next_id:
            return "NONE"
        return self.bounty_status[bounty_id]
