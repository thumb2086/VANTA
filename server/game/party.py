"""
server/game/party.py — Party System (create/invite/join/leave/ready/queue)
"""
from __future__ import annotations

import uuid
import time
import random
import string
from dataclasses import dataclass, field


def _generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


@dataclass
class PartyMember:
    slot: int
    name: str
    agent: str = ""
    ready: bool = False


@dataclass
class Party:
    id: str
    host_slot: int
    mode: str = "competitive"
    members: list[PartyMember] = field(default_factory=list)
    invite_code: str = ""
    created_at: float = 0.0


class PartyManager:
    def __init__(self):
        self.parties: dict[str, Party] = {}
        self.slot_to_party: dict[int, str] = {}

    def create(self, host_slot: int, host_name: str, mode: str = "competitive") -> Party:
        party_id = str(uuid.uuid4())
        invite_code = _generate_invite_code()
        party = Party(
            id=party_id,
            host_slot=host_slot,
            mode=mode,
            invite_code=invite_code,
            created_at=time.time(),
        )
        party.members.append(PartyMember(slot=host_slot, name=host_name))
        self.parties[party_id] = party
        self.slot_to_party[host_slot] = party_id
        return party

    def _find_by_invite(self, invite_code: str) -> Party | None:
        for party in self.parties.values():
            if party.invite_code == invite_code:
                return party
        return None

    def join(self, invite_code: str, slot: int, name: str) -> Party | None:
        party = self._find_by_invite(invite_code)
        if party is None:
            return None
        if len(party.members) >= 5:
            return None
        if slot in self.slot_to_party:
            return None
        party.members.append(PartyMember(slot=slot, name=name))
        self.slot_to_party[slot] = party.id
        return party

    def leave(self, slot: int) -> None:
        party_id = self.slot_to_party.pop(slot, None)
        if party_id is None:
            return
        party = self.parties.get(party_id)
        if party is None:
            return
        party.members = [m for m in party.members if m.slot != slot]
        if not party.members:
            del self.parties[party_id]
            return
        if party.host_slot == slot:
            party.host_slot = party.members[0].slot

    def ready(self, slot: int, is_ready: bool) -> None:
        party_id = self.slot_to_party.get(slot)
        if party_id is None:
            return
        party = self.parties.get(party_id)
        if party is None:
            return
        for m in party.members:
            if m.slot == slot:
                m.ready = is_ready
                break

    def get_party(self, slot: int) -> Party | None:
        party_id = self.slot_to_party.get(slot)
        if party_id is None:
            return None
        return self.parties.get(party_id)

    def all_ready(self, party_id: str) -> bool:
        party = self.parties.get(party_id)
        if party is None:
            return False
        return len(party.members) == 5 and all(m.ready for m in party.members)

    def queue(self, party_id: str) -> bool:
        party = self.parties.get(party_id)
        if party is None:
            return False
        expected = {"competitive": 5, "unrated": 5, "swiftplay": 5, "spike_rush": 3}
        needed = expected.get(party.mode, 5)
        if len(party.members) != needed:
            return False
        return True
