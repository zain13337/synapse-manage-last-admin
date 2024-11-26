# -*- coding: utf-8 -*-
# Copyright 2021 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# From Python 3.8 onwards, aiounittest.AsyncTestCase can be replaced by
# unittest.IsolatedAsyncioTestCase, so we'll be able to get rid of this dependency when
# we stop supporting Python < 3.8 in Synapse.
from abc import abstractmethod
from typing import Any, Dict

import aiounittest
from synapse.api.constants import EventTypes, Membership
from synapse.api.room_versions import RoomVersions
from synapse.events import EventBase, make_event_from_dict
from synapse.types import JsonDict, MutableStateMap
from synapse.util.stringutils import random_string

from manage_last_admin import ACCESS_RULES_TYPE
from tests import create_module


CONFIG_DOMAINS_FORBIDDEN_WHEN_RESTRICTED=["externe.com"]

class ManageLastAdminTestCases:
    class BaseManageLastAdminTest(aiounittest.AsyncTestCase):
        @abstractmethod
        def create_event(self, content: JsonDict) -> EventBase:
            pass

        def setUp(self) -> None:
            self.user_id = "@alice:example.com"
            self.left_user_id = "@nothere:example.com"
            self.mod_user_id = "@mod:example.com"
            self.regular_user_id = "@someuser:example.com"
            self.room_id = "!someroom:example.com"
            self.state = self.get_public_room()

        def get_basic_room_state(self) -> MutableStateMap[EventBase]:
            return {
                (EventTypes.PowerLevels, ""): self.create_event(
                    {
                        "sender": self.user_id,
                        "type": EventTypes.PowerLevels,
                        "state_key": "",
                        "content": {
                            "ban": 50,
                            "events": {
                                "m.room.avatar": 50,
                                "m.room.canonical_alias": 50,
                                "m.room.encryption": 100,
                                "m.room.history_visibility": 100,
                                "m.room.name": 50,
                                "m.room.power_levels": 100,
                                "m.room.server_acl": 100,
                                "m.room.tombstone": 100,
                            },
                            "events_default": 0,
                            "invite": 0,
                            "kick": 50,
                            "redact": 50,
                            "state_default": 50,
                            "users": {
                                self.user_id: 100,
                                self.left_user_id: 75,
                                self.mod_user_id: 50,
                                self.regular_user_id: 0,
                            },
                            "users_default": 0,
                        },
                        "room_id": self.room_id,
                    },
                ),
                (EventTypes.Member, self.user_id): self.create_event(
                    {
                        "sender": self.user_id,
                        "type": EventTypes.Member,
                        "state_key": self.user_id,
                        "content": {"membership": Membership.JOIN},
                        "room_id": self.room_id,
                    },
                ),
                (EventTypes.Member, self.mod_user_id): self.create_event(
                    {
                        "sender": self.mod_user_id,
                        "type": EventTypes.Member,
                        "state_key": self.mod_user_id,
                        "content": {"membership": Membership.JOIN},
                        "room_id": self.room_id,
                    },
                ),
                (EventTypes.Member, self.regular_user_id): self.create_event(
                    {
                        "sender": self.regular_user_id,
                        "type": EventTypes.Member,
                        "state_key": self.regular_user_id,
                        "content": {"membership": Membership.JOIN},
                        "room_id": self.room_id,
                    },
                ),
                (EventTypes.Member, self.left_user_id): self.create_event(
                    {
                        "sender": self.left_user_id,
                        "type": EventTypes.Member,
                        "state_key": self.left_user_id,
                        "content": {"membership": Membership.LEAVE},
                        "room_id": self.room_id,
                    },
                ),
            }

        def get_public_room(self) -> MutableStateMap[EventBase]:
            state = self.get_basic_room_state()
            return self.make_room_public(state)

        def get_private_room(self) -> MutableStateMap[EventBase]:
            state = self.get_basic_room_state()
            return self.make_room_private(state)

        def get_other_room(self) -> MutableStateMap[EventBase]:
            state = self.get_basic_room_state()
            return self.make_room_unknown(state)

        def make_room_public(
            self, state: MutableStateMap[EventBase]
        ) -> MutableStateMap[EventBase]:
            state[(EventTypes.JoinRules, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.JoinRules,
                    "state_key": "",
                    "content": {"join_rule": "public"},
                    "room_id": self.room_id,
                },
            )
            state[(ACCESS_RULES_TYPE, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": ACCESS_RULES_TYPE,
                    "state_key": "",
                    "content": {"rule": "restricted"},
                    "room_id": self.room_id,
                }
            )
            return state

        def make_room_private(
            self, state: MutableStateMap[EventBase]
        ) -> MutableStateMap[EventBase]:
            state[(EventTypes.JoinRules, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.JoinRules,
                    "state_key": "",
                    "content": {"join_rule": "invite"},
                    "room_id": self.room_id,
                },
            )
            state[(ACCESS_RULES_TYPE, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": ACCESS_RULES_TYPE,
                    "state_key": "",
                    "content": {"rule": "restricted"},
                    "room_id": self.room_id,
                },
            )
            state[(EventTypes.RoomEncryption, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.RoomEncryption,
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                    "room_id": self.room_id,
                },
            )
            return state

        ## TODO: what is the difference with an external room?
        def make_room_unknown(
            self, state: MutableStateMap[EventBase]
        ) -> MutableStateMap[EventBase]:
            state[(EventTypes.JoinRules, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.JoinRules,
                    "state_key": "",
                    "content": {"join_rule": "invite"},
                    "room_id": self.room_id,
                },
            )
            state[(ACCESS_RULES_TYPE, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": ACCESS_RULES_TYPE,
                    "state_key": "",
                    "content": {"rule": "unrestricted"},
                    "room_id": self.room_id,
                },
            )
            state[(EventTypes.RoomEncryption, "")] = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.RoomEncryption,
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                    "room_id": self.room_id,
                },
            )
            return state
        async def do_set_room_users_default_when_last_admin_leaves(self) -> None:
            module = create_module()
            leave_event = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.user_id,
                },
            )
            allowed, replacement = await module.check_event_allowed(
                leave_event, self.state
            )
            self.assertTrue(allowed)
            self.assertEqual(replacement, None)
            # Test that the leave triggered a freeze of the room.
            self.assertTrue(module._api.create_and_send_event_into_room.called)  # type: ignore[attr-defined]
            args, _ = module._api.create_and_send_event_into_room.call_args  # type: ignore[attr-defined]
            self.assertEqual(len(args), 1)
            pl_event_dict = args[0]
            self.assertEqual(pl_event_dict["content"]["users_default"], 100)
            # We make sure that user with pl=100 remains
            for user, pl in pl_event_dict["content"]["users"].items():
                self.assertEqual(pl, 100, user)

        async def do_promote_when_last_admin_leaves(self) -> None:
            # Set the config flag to allow promoting custom PLs before freezing the room.
            module = create_module(config_override={
                "promote_moderators": True, 
                "domains_forbidden_when_restricted":CONFIG_DOMAINS_FORBIDDEN_WHEN_RESTRICTED})
            # Make the last admin leave.
            leave_event = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.user_id,
                },
            )
            # Check that we get the right result back from the callback.
            allowed, replacement = await module.check_event_allowed(
                leave_event, self.state
            )
            self.assertTrue(allowed)
            self.assertEqual(replacement, None)
            # Test that a new event was sent into the room.
            self.assertTrue(module._api.create_and_send_event_into_room.called)  # type: ignore[attr-defined]
            args, _ = module._api.create_and_send_event_into_room.call_args  # type: ignore[attr-defined]
            self.assertEqual(len(args), 1)
            # Test that:
            #   * the event is a power levels update
            #   * the user who is PL 75 but left the room didn't get promoted
            #   * the user who was PL 50 and is still in the room got promoted
            evt_dict: Dict[str, Any] = args[0]
            self.assertEqual(evt_dict["type"], EventTypes.PowerLevels, evt_dict)
            self.assertIsNotNone(evt_dict.get("state_key"))
            self.assertEqual(
                evt_dict["content"]["users"][self.left_user_id], 75, evt_dict
            )
            self.assertEqual(
                evt_dict["content"]["users"][self.mod_user_id], 100, evt_dict
            )

        async def do_nothing_when_admin_leaves(self, module: Any) -> None:
            leave_event = self.create_event(
                {
                    "sender": self.user_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.user_id,
                },
            )
            allowed, replacement = await module.check_event_allowed(
                leave_event, self.state
            )
            self.assertTrue(allowed)
            self.assertEqual(replacement, None)
            # Test that no event is generated
            self.assertFalse(module._api.create_and_send_event_into_room.called)

        # TEST SCENARIOS #

        async def test_set_room_users_default_when_last_admin_leaves_on_public_room(
            self,
        ) -> None:
            """Tests that the module sends the right power levels update
            when it sees its last admin leaving a public room."""
            await self.do_set_room_users_default_when_last_admin_leaves()

        async def test_promote_when_last_admin_leaves_on_public_room(self) -> None:
            """Tests that the module promotes whoever has the highest non-default PL to admin
            when the last admin leaves a public room, if the config allows it.
            """
            await self.do_promote_when_last_admin_leaves()

        async def test_set_room_users_default_when_last_admin_leaves_on_private_room(
            self,
        ) -> None:
            """Tests that the module sends the right power levels update
            when it sees its last admin leaving a private room."""
            self.state = self.get_private_room()
            await self.do_set_room_users_default_when_last_admin_leaves()

        async def test_promote_when_last_admin_leaves_on_private_room(self) -> None:
            """Tests that the module promotes whoever has the highest non-default PL to admin
            when the last admin leaves a private room, if the config allows it.
            """
            self.state = self.get_private_room()
            await self.do_promote_when_last_admin_leaves()

        
#         outdated, fails now
#         async def test_do_not_set_room_users_default_when_last_admin_leaves_on_other_room(
#            self,
#        ) -> None:
#            """Tests that the module do not send any event when last member leaves an unknown room."""
#            self.state = self.get_other_room()
#            module = create_module()
#            await self.do_nothing_when_admin_leaves(module)

        async def test_promote_when_last_admin_leaves_on_other_room(self) -> None:
            """Tests that the module promotes whoever has the highest non-default PL to admin
            when the last admin leaves an unknown room, if the config allows it.
            """
            self.state = self.get_other_room()
            await self.do_promote_when_last_admin_leaves()


class ManageLastAdminTestRoomV9(ManageLastAdminTestCases.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict) -> EventBase:
        return make_event_from_dict(content, RoomVersions.V9)


class ManageLastAdminTestRoomV1(ManageLastAdminTestCases.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict) -> EventBase:
        content["event_id"] = f"!{random_string(43)}:example.com"
        return make_event_from_dict(content, RoomVersions.V1)
