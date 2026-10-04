# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
OathBond - conviction-staked accountability bonds on GenLayer.

WHY GENLAYER (dies-without-it):
    The core action is a SUBJECTIVE verification with real money on the line:
    "Did the person actually keep the public promise they bonded?"
    A maker locks GEN behind a dated, verifiable commitment and names a URL that
    will PROVE it was kept (a shipped release page, a published report, a merged
    PR, an on-air correction...). At resolution the contract itself opens that
    live page on-chain (gl.nondet.web.render) and a validator jury reasons about
    whether the evidence genuinely satisfies the promise (gl.nondet.exec_prompt),
    then returns the pot to the maker + backers or slashes it to the named
    beneficiary. No oracle, no human referee - a plain Solidity contract could
    never read an arbitrary web page and judge "was this promise kept".

CONVICTION STAKING (what makes this different from a simple escrow):
    Besides the maker, anyone who believes the promise WILL be kept can `back`
    it, adding to the pot. If the oath is KEPT, every contributor is refunded
    their exact contribution. If it is BROKEN, the whole pot (maker + backers)
    is slashed to the beneficiary. Backers therefore put skin in the game behind
    someone else's credibility - a reputation market, not a work escrow.

CONSENSUS DESIGN (Axis 2 - the critical part):
    Validators do NOT agree on byte-identical JSON. Each validator INDEPENDENTLY
    fetches proof_url, runs its own LLM, and agrees only if its OWN verdict
    (KEPT / BROKEN / INCONCLUSIVE) matches the leader's. Differently-worded
    rationales still reach consensus; a genuine KEPT-vs-BROKEN split does not.

STORAGE NOTE:
    Backings are kept in a FLAT TreeMap keyed by an auto-incrementing id (each
    record carries its oath_id), rather than a TreeMap of nested dynamic arrays.
    GenVM storage does not support nested dynamic collections, so the flat layout
    is both correct and portable.
"""

from genlayer import *
import json
import typing
import datetime
from dataclasses import dataclass


ZERO_ADDR = Address(b"\x00" * 20)

# A first pass that comes back INCONCLUSIVE must sit for this long before anyone
# can escalate it into a stricter re-check that may harden into a BROKEN ruling.
# The maker (or a backer) gets a real window to supply/replace evidence before
# the pot can be slashed on a merely-unverifiable first read.
CHALLENGE_WINDOW_SECONDS = 86400   # 24 hours


@allow_storage
@dataclass
class Backing:
    oath_id: u256
    backer: Address
    amount: bigint


@allow_storage
@dataclass
class Oath:
    maker: Address
    beneficiary: Address        # receives the pot if the oath is BROKEN (required, non-maker)
    statement: str              # the promise, phrased as a checkable claim
    proof_url: str              # live page that should prove it was kept
    criteria: str               # optional extra judging rules from the maker
    due_date: str               # ISO-8601 UTC; resolution is rejected before this
    maker_stake: bigint         # maker's own contribution, in wei
    pot: bigint                 # maker_stake + every backing, in wei
    status: str                 # OPEN | INCONCLUSIVE | SETTLED_KEPT | SETTLED_BROKEN
    verdict: str                # KEPT | BROKEN | INCONCLUSIVE | "" (not judged)
    rationale: str              # AI explanation of the ruling
    escalated: bool             # has the single stricter re-check been used
    inconclusive_since: str     # ISO-8601 UTC when first ruled INCONCLUSIVE ("" otherwise)


class Contract(gl.Contract):
    oaths: TreeMap[u256, Oath]
    backings: TreeMap[u256, Backing]   # backing_id -> Backing (carries oath_id)
    next_id: bigint
    next_backing_id: bigint
    total_locked: bigint

    def __init__(self):
        self.next_id = bigint(0)
        self.next_backing_id = bigint(0)
        self.total_locked = bigint(0)

    # -- helpers --------------------------------------------------------------

    def _require_oath(self, oath_id: u256) -> Oath:
        if oath_id not in self.oaths:
            raise Exception("Oath does not exist")
        return self.oaths[oath_id]

    def _addr_str(self, addr: Address) -> str:
        try:
            return addr.as_hex
        except Exception:
            return str(addr)

    # Consensus clock. On GenLayer `datetime.now()` returns the deterministic
    # block/consensus time, so every validator reads the same instant.
    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def _parse_dt(self, s: str) -> datetime.datetime:
        t = s.strip()
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        d = datetime.datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d

    def _record_backing(self, oath_id: u256, backer: Address, amount: int) -> None:
        bid = u256(self.next_backing_id)
        self.backings[bid] = Backing(oath_id=oath_id, backer=backer, amount=bigint(amount))
        self.next_backing_id = self.next_backing_id + bigint(1)

    # -- maker opens a bonded oath --------------------------------------------

    @gl.public.write.payable
    def open_oath(
        self,
        statement: str,
        proof_url: str,
        beneficiary: str,
        criteria: str,
        due_date: str,
    ) -> u256:
        amount = gl.message.value
        if amount == 0:
            raise Exception("Bond stake must be > 0")
        if len(statement.strip()) < 12:
            raise Exception("Statement too short to verify against")
        if len(proof_url.strip()) == 0:
            raise Exception("A proof URL is required")
        if not proof_url.strip().lower().startswith(("http://", "https://")):
            raise Exception("proof_url must be an http(s) URL")

        # A broken-oath payout must have an explicit, independent recipient: the
        # maker cannot stake against themselves, so the beneficiary is required
        # and must be a real, non-maker, non-zero address.
        if len(beneficiary.strip()) == 0:
            raise Exception("A beneficiary address is required for broken-oath payouts")
        bene = Address(beneficiary.strip())
        if bene == ZERO_ADDR:
            raise Exception("Beneficiary cannot be the zero address")
        if bene == gl.message.sender_address:
            raise Exception("Beneficiary cannot be the maker")

        # Enforce an on-chain settlement window: the promise cannot be judged
        # until its stated due date has passed.
        if len(due_date.strip()) == 0:
            raise Exception("A due date is required")
        due = self._parse_dt(due_date)
        if due <= self._now():
            raise Exception("Due date must be in the future")

        oath_id = u256(self.next_id)
        self.oaths[oath_id] = Oath(
            maker=gl.message.sender_address,
            beneficiary=bene,
            statement=statement,
            proof_url=proof_url.strip(),
            criteria=criteria,
            due_date=due_date.strip(),
            maker_stake=bigint(amount),
            pot=bigint(amount),
            status="OPEN",
            verdict="",
            rationale="",
            escalated=False,
            inconclusive_since="",
        )
        self._record_backing(oath_id, gl.message.sender_address, amount)
        self.next_id = self.next_id + bigint(1)
        self.total_locked = self.total_locked + bigint(amount)
        return oath_id

    # -- a supporter co-stakes on the promise being kept ----------------------

    @gl.public.write.payable
    def back_oath(self, oath_id: u256) -> None:
        oath = self._require_oath(oath_id)
        if oath.status != "OPEN":
            raise Exception("Oath is not open for backing")
        amount = gl.message.value
        if amount == 0:
            raise Exception("Backing amount must be > 0")
        if gl.message.sender_address == oath.beneficiary:
            raise Exception("Beneficiary cannot back the oath")

        self._record_backing(oath_id, gl.message.sender_address, amount)
        oath.pot = oath.pot + bigint(amount)
        self.total_locked = self.total_locked + bigint(amount)

    # -- permissionless resolution: read proof + AI verdict -------------------

    @gl.public.write
    def resolve(self, oath_id: u256) -> str:
        oath = self._require_oath(oath_id)
        if oath.status != "OPEN":
            raise Exception("Oath is not awaiting resolution")
        # Settlement window: refuse to judge the promise before its due date.
        if self._now() < self._parse_dt(oath.due_date):
            raise Exception("Settlement window not reached; resolve only on or after the due date")

        statement = oath.statement
        proof_url = oath.proof_url
        criteria = oath.criteria

        verdict, rationale = self._judge(statement, proof_url, criteria, strict=False)
        oath.verdict = verdict
        oath.rationale = rationale
        return self._apply_verdict(oath_id, oath, verdict)

    # -- one stricter re-check when a first pass was INCONCLUSIVE --------------

    @gl.public.write
    def escalate(self, oath_id: u256) -> str:
        oath = self._require_oath(oath_id)
        if oath.status != "INCONCLUSIVE":
            raise Exception("Only an inconclusive oath can be escalated")
        if oath.escalated:
            raise Exception("This oath has already used its single re-check")
        # Challenge window: an inconclusive first read cannot be hardened into a
        # broken ruling (and its slash) until the delay has elapsed, giving the
        # maker/backers time to fix or supply evidence first.
        unlock = self._parse_dt(oath.inconclusive_since) + datetime.timedelta(seconds=CHALLENGE_WINDOW_SECONDS)
        if self._now() < unlock:
            raise Exception("Challenge window still open; escalation is not yet allowed")

        statement = oath.statement
        proof_url = oath.proof_url
        criteria = oath.criteria

        oath.escalated = True
        verdict, rationale = self._judge(statement, proof_url, criteria, strict=True)
        oath.verdict = verdict
        oath.rationale = "RE-CHECK: " + rationale
        if verdict == "INCONCLUSIVE":
            verdict = "BROKEN"
            oath.verdict = "BROKEN"
            oath.rationale = "RE-CHECK still unverifiable; promise treated as BROKEN. " + rationale
        return self._apply_verdict(oath_id, oath, verdict)

    # -- turn a verdict into money movement -----------------------------------

    def _apply_verdict(self, oath_id: u256, oath: Oath, verdict: str) -> str:
        if verdict == "KEPT":
            oath.status = "SETTLED_KEPT"
            self._refund_contributors(oath_id, oath)
        elif verdict == "BROKEN":
            oath.status = "SETTLED_BROKEN"
            self._slash_to_beneficiary(oath_id, oath)
        else:
            oath.status = "INCONCLUSIVE"
            # Start the challenge clock the first time it lands inconclusive.
            if oath.inconclusive_since == "":
                oath.inconclusive_since = self._now().isoformat()
        return oath.status

    def _refund_contributors(self, oath_id: u256, oath: Oath) -> None:
        # terminal status already set by caller (re-entrancy safety, R15)
        moved = bigint(0)
        for bid in self.backings:
            b = self.backings[bid]
            if b.oath_id == oath_id:
                moved = moved + b.amount
                gl.get_contract_at(b.backer).emit_transfer(value=u256(b.amount))
        self.total_locked = self.total_locked - moved

    def _slash_to_beneficiary(self, oath_id: u256, oath: Oath) -> None:
        # The beneficiary is guaranteed non-zero and non-maker at open time, so
        # a broken oath always pays the explicit, independent recipient.
        amount = oath.pot
        self.total_locked = self.total_locked - amount
        gl.get_contract_at(oath.beneficiary).emit_transfer(value=u256(amount))

    # -------------------------------------------------------------------------
    # THE NON-DETERMINISTIC HEART - read the proof page + LLM judgement.
    # -------------------------------------------------------------------------

    def _judge(
        self,
        statement: str,
        proof_url: str,
        criteria: str,
        strict: bool,
    ) -> tuple[str, str]:

        def leader_fn():
            try:
                page = gl.nondet.web.render(proof_url, mode="text")
            except Exception as e:
                page = f"__FETCH_FAILED__: {e}"
            excerpt = page[:6000] if isinstance(page, str) else str(page)

            rigor = (
                "This is a STRICT re-check. Only answer KEPT if the page "
                "unambiguously and completely proves the promise. Any doubt, "
                "partial fulfilment, or missing proof is BROKEN."
                if strict else
                "Judge fairly on the balance of the evidence shown."
            )
            extra = f"\nMAKER'S EXTRA CRITERIA:\n{criteria}\n" if criteria.strip() else ""

            prompt = f"""You are an impartial accountability referee for a bonded public promise.
Someone staked money on this promise and named a page that should PROVE they kept it.

THE PROMISE (must be satisfied):
{statement}
{extra}
PROOF URL: {proof_url}
FETCHED PAGE (text extract, may be truncated):
{excerpt}

{rigor}

Decide, using ONLY the evidence above:
- KEPT         : the page clearly shows the promise was fulfilled.
- BROKEN       : the page shows it was NOT fulfilled (wrong, missing, contradicted).
- INCONCLUSIVE : the page could not be fetched (look for __FETCH_FAILED__), is
                 empty, or is irrelevant so fulfilment cannot be judged.

Respond with ONLY a JSON object, no prose, no markdown:
{{"verdict": "KEPT" | "BROKEN" | "INCONCLUSIVE", "rationale": "<one or two sentences>"}}"""

            return gl.nondet.exec_prompt(prompt, response_format="json")

        def _extract(payload) -> str:
            try:
                data = json.loads(payload) if isinstance(payload, str) else payload
                v = str(data.get("verdict", "")).upper().strip()
                return v if v in ("KEPT", "BROKEN", "INCONCLUSIVE") else ""
            except Exception:
                return ""

        def validator_fn(leader_res: typing.Any) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader_verdict = _extract(leader_res.calldata)
            if leader_verdict == "":
                return False
            try:
                mine = leader_fn()
            except Exception:
                return False
            my_verdict = _extract(mine)
            return my_verdict != "" and my_verdict == leader_verdict

        runner = getattr(gl.vm, "run_nondet", None) or gl.vm.run_nondet_unsafe
        result = runner(leader_fn, validator_fn)

        try:
            payload = result.calldata if isinstance(result, gl.vm.Return) else result
            data = json.loads(payload) if isinstance(payload, str) else payload
            verdict = str(data.get("verdict", "INCONCLUSIVE")).upper().strip()
            if verdict not in ("KEPT", "BROKEN", "INCONCLUSIVE"):
                verdict = "INCONCLUSIVE"
            rationale = str(data.get("rationale", ""))[:500]
        except Exception:
            verdict = "INCONCLUSIVE"
            rationale = "Could not parse a verdict; left inconclusive."
        return verdict, rationale

    # -- read-only views (for the frontend) -----------------------------------

    @gl.public.view
    def get_oath(self, oath_id: u256) -> str:
        oath = self._require_oath(oath_id)
        backers = []
        for bid in self.backings:
            b = self.backings[bid]
            if b.oath_id == oath_id:
                backers.append({"backer": self._addr_str(b.backer), "amount": str(int(b.amount))})
        return json.dumps(self._oath_dict(oath_id, oath, backers))

    @gl.public.view
    def list_oaths(self) -> str:
        out = []
        for oid in self.oaths:
            out.append(self._oath_dict(oid, self.oaths[oid], None))
        return json.dumps(out)

    @gl.public.view
    def get_oath_count(self) -> int:
        return int(self.next_id)

    @gl.public.view
    def get_total_locked(self) -> str:
        return str(int(self.total_locked))

    def _oath_dict(self, oath_id: u256, oath: Oath, backers) -> dict:
        d = {
            "id": int(oath_id),
            "maker": self._addr_str(oath.maker),
            "beneficiary": self._addr_str(oath.beneficiary),
            "statement": oath.statement,
            "proof_url": oath.proof_url,
            "criteria": oath.criteria,
            "due_date": oath.due_date,
            "inconclusive_since": oath.inconclusive_since,
            "maker_stake": str(int(oath.maker_stake)),
            "pot": str(int(oath.pot)),
            "status": oath.status,
            "verdict": oath.verdict,
            "rationale": oath.rationale,
            "escalated": oath.escalated,
        }
        if backers is not None:
            d["backers"] = backers
        return d
