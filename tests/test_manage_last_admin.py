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

import aiounittest
from synapse.api.room_versions import RoomVersions
from synapse.events import EventBase, make_event_from_dict
from synapse.types import JsonDict
from synapse.util.stringutils import random_string

from manage_last_admin import EventTypes, Membership
from tests import create_module


class ManageLastAdminTestCases:
    class BaseManageLastAdminTest(aiounittest.AsyncTestCase):
        @abstractmethod
        def create_event(self, content: JsonDict) -> EventBase:
            pass

        def setUp(self) -> None:
            self.user_id = "@alice:example.com"
            self.left_user_id = "@nothere:example.com"
            self.mod_user_id = "@mod:example.com"
            self.room_id = "!someroom:example.com"
            self.state = {
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
                            },
                            "users_default": 0,
                        },
                        "room_id": self.room_id,
                    },
                ),
                (EventTypes.JoinRules, ""): self.create_event(
                    {
                        "sender": self.user_id,
                        "type": EventTypes.JoinRules,
                        "state_key": "",
                        "content": {"join_rule": "public"},
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

        async def test_power_levels_sent_when_last_admin_leaves(self) -> None:
            """Tests that the module sends the right power levels update when it sees its last admin leave."""
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
            self.assertTrue(module._api.create_and_send_event_into_room.called)
            args, _ = module._api.create_and_send_event_into_room.call_args
            self.assertEqual(len(args), 1)

            pl_event_dict = args[0]

            self.assertEqual(pl_event_dict["content"]["users_default"], 100)
            for user, pl in pl_event_dict["content"]["users"].items():
                self.assertEqual(pl, 100, user)

        async def test_promote_when_last_admin_leaves(self) -> None:
            """Tests that the module promotes whoever has the highest non-default PL to admin
            when the last admin leaves, if the config allows it.
            """
            # Set the config flag to allow promoting custom PLs before freezing the room.
            module = create_module(config_override={"promote_moderators": True})

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
            self.assertTrue(module._api.create_and_send_event_into_room.called)
            args, _ = module._api.create_and_send_event_into_room.call_args
            self.assertEqual(len(args), 1)

            # Test that:
            #   * the event is a power levels update
            #   * the user who is PL 75 but left the room didn't get promoted
            #   * the user who was PL 50 and is still in the room got promoted
            evt_dict: dict = args[0]
            self.assertEqual(evt_dict["type"], EventTypes.PowerLevels, evt_dict)
            self.assertIsNotNone(evt_dict.get("state_key"))
            self.assertEqual(
                evt_dict["content"]["users"][self.left_user_id], 75, evt_dict
            )
            self.assertEqual(
                evt_dict["content"]["users"][self.mod_user_id], 100, evt_dict
            )

            # Now we push both the leave event and the power levels update into the state of
            # the room.
            self.state[(EventTypes.Member, self.user_id)] = leave_event
            self.state[(EventTypes.PowerLevels, "")] = self.create_event(evt_dict)

            # Make the mod (newly admin) leave the room.
            new_leave_event = self.create_event(
                {
                    "sender": self.mod_user_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.mod_user_id,
                },
            )

            # Check that we get the right result back from the callback.
            allowed, replacement = await module.check_event_allowed(
                new_leave_event,
                self.state,
            )
            self.assertTrue(allowed)
            self.assertEqual(replacement, None)

            # Test that a new event was sent into the room.
            self.assertTrue(module._api.create_and_send_event_into_room.called)
            args, _ = module._api.create_and_send_event_into_room.call_args
            self.assertEqual(len(args), 1)

            # Test that now that there's no user to promote anymore, the room default user level is 100.
            pl_event_dict = args[0]

            self.assertEqual(pl_event_dict["content"]["users_default"], 100)
            for user, pl in pl_event_dict["content"]["users"].items():
                self.assertEqual(pl, 100, user)


class ManageLastAdminTestRoomV9(ManageLastAdminTestCases.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict):
        return make_event_from_dict(content, RoomVersions.V9)


class ManageLastAdminTestRoomV1(ManageLastAdminTestCases.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict):
        content["event_id"] = f"!{random_string(43)}:example.com"
        return make_event_from_dict(content, RoomVersions.V1)
