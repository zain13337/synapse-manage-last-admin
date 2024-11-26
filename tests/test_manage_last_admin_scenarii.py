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

from manage_last_admin import ACCESS_RULES_TYPE, _is_last_admin_leaving, _get_power_levels_content_from_state
from tests import create_module


CONFIG_DOMAINS_FORBIDDEN_WHEN_RESTRICTED=["externe.com"]

class ManageLastAdminTestScenarii:
    class BaseManageLastAdminTest(aiounittest.AsyncTestCase):
        @abstractmethod
        def create_event(self, content: JsonDict) -> EventBase:
            pass

        def setUp(self) -> None:
            self.admin_id = "@admin:example.com"
            self.admin2_id = "@admin2:example.com"
            self.left_user_id = "@nothere:example.com"
            self.mod_user_id = "@mod:example.com"
            self.mod2_user_id = "@mod2:example.com"
            self.regular_user_id = "@someuser:example.com"
            self.regular2_user_id = "@someuser2:example.com"
            self.external_user_id = "@ext:externe.com"
            self.external2_user_id = "@ext2:externe.com"
            self.room_id = "!someroom:example.com"
            self.state = self.get_empty_room()


        def get_empty_room(self) -> MutableStateMap[EventBase]:
            return {}
        
        def add_user_membership(self, state: MutableStateMap[EventBase], user_id: str, room_id: str
        ) -> None:
            """
            Add a 'm.room.member' event for the user, indicating they joined the room.

            Args:
                state_events: Dictionary storing room state events.
                user_id: The user to add as a room member (JOIN).
                room_id: Room info for the member event.
            """
            
            # Create m.room.member event to mark the user as joined (membership: JOIN)
            new_member_event = self.create_event({
                "type": EventTypes.Member,
                "state_key": user_id,
                "room_id": room_id,
                "sender": user_id,
                "content": {"membership": Membership.JOIN},
            })
            
            # Add the member event to state map
            state[(EventTypes.Member, user_id)] = new_member_event
            #print(f"User {user_id} added to the room with membership JOIN")
        
        def make_room_private(
            self, state: MutableStateMap[EventBase]
        ) -> MutableStateMap[EventBase]:
            state[(EventTypes.JoinRules, "")] = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": EventTypes.JoinRules,
                    "state_key": "",
                    "content": {"join_rule": "invite"},
                    "room_id": self.room_id,
                },
            )
            state[(ACCESS_RULES_TYPE, "")] = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": ACCESS_RULES_TYPE,
                    "state_key": "",
                    "content": {"rule": "restricted"},
                    "room_id": self.room_id,
                },
            )
            state[(EventTypes.RoomEncryption, "")] = self.create_event(
                {
                    "sender": self.admin_id,
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
                    "sender": self.admin_id,
                    "type": EventTypes.JoinRules,
                    "state_key": "",
                    "content": {"join_rule": "invite"},
                    "room_id": self.room_id,
                },
            )
            state[(ACCESS_RULES_TYPE, "")] = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": ACCESS_RULES_TYPE,
                    "state_key": "",
                    "content": {"rule": "unrestricted"},
                    "room_id": self.room_id,
                },
            )
            state[(EventTypes.RoomEncryption, "")] = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": EventTypes.RoomEncryption,
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                    "room_id": self.room_id,
                },
            )
            return state

        def add_users_in_room_with_pl(
            self, state: MutableStateMap[EventBase], users_power_level:Any
        ) -> None:
            state[(EventTypes.PowerLevels, "")] = self.create_event(
                    {
                        "sender": self.admin_id,
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
                            "users": users_power_level,
                            "users_default": 0,
                        },
                        "room_id": self.room_id,
                    },
                )
            # add users JOIN event
            for user_id in users_power_level:
                self.add_user_membership(self.state, user_id, self.room_id)

        async def admin_leaves(self) -> Any:
            module = create_module(config_override={
                "promote_moderators": True, 
                "domains_forbidden_when_restricted":CONFIG_DOMAINS_FORBIDDEN_WHEN_RESTRICTED}
                )
            leave_event = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.admin_id,
                },
            )
            #print(f"state {self.state}")

            allowed, replacement = await module.check_event_allowed(
                leave_event, self.state
            )
            self.assertTrue(allowed)
            self.assertEqual(replacement, None)
            return module

        async def checkAPIcalled(self, module:Any) -> Any:
            # Test that the leave triggered a freeze of the room.
            self.assertTrue(module._api.create_and_send_event_into_room.called) 
            args, _ = module._api.create_and_send_event_into_room.call_args
            self.assertEqual(len(args), 1)
            return args[0]

        async def checkApiNotcalled(self, module:Any) -> None:
            # Test that the leave triggered a freeze of the room.
            self.assertFalse(module._api.create_and_send_event_into_room.called)

        """
        Scenarii tests execution
        """
        
        async def test_last_admin_leaves_on_private(
            self,
        ) -> None:
            """
            Scenario 1 - Salon Privee - Pas de moderateur
            3 Participants : 1 admin - 2 par defaut
            Admin quitte le salon
            => action attendu : mise à jour du default power level à 100
            Note : tous les invites seront admin
            """
            users_pl = {
                self.admin_id : 100,
            }

            self.make_room_private(self.state)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_user_membership(self.state, self.regular2_user_id, self.room_id)
            self.add_users_in_room_with_pl(self.state, users_pl)

            module = await self.admin_leaves()
            pl_event_dict = await self.checkAPIcalled(module)
            self.assertEqual(pl_event_dict["content"]["users_default"], 100)

        async def test_last_admin_leaves_with_more_admins(
            self,
        ) -> None:
            """
            Scenario 2 - Salon Privee - Pas de moderateur - Multi Admin
            3 Participants : 2 admin - 1 par defaut
            1 Admin quitte le salon
            => action attendu : pas d'action
            """
            users_pl = {
                self.admin_id : 100,
                self.admin2_id : 100,
            }
            
            self.make_room_unknown(self.state)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_users_in_room_with_pl(self.state, users_pl)

            module = await self.admin_leaves()
            await self.checkApiNotcalled(module) # API is not called

        async def test_last_admin_leaves_with_mod_on_private_room(
            self,
        ) -> None:
            """
            Scenario 3 - Salon Privee - Moderateur
            3 Participants : 1 admin - 1 moderateur - 1 par defaut
            Admin quitte le salon
            => action attendue : nommer 1 moderateur en admin
            """
            users_pl = {
                self.admin_id : 100,
                self.mod_user_id : 50, # mod
            }
            self.make_room_unknown(self.state)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_users_in_room_with_pl(self.state, users_pl)

            module = await self.admin_leaves() #method to test

            pl_event_dict = await self.checkAPIcalled(module)
            self.assertDictEqual(pl_event_dict["content"]["users"], {
                self.admin_id: 100,
                self.mod_user_id : 100, # mod is promoted
            })

        async def test_last_admin_leaves_on_external_room(
            self,
        ) -> None:
            """
            Scenario 4 - Salon Externe - Pas de moderateur
            6 Participants : 1 admin - 2 par defaut - 2 externe
            Admin quitte le salon
            => resultat attendu : 2 par defaut non externe sont nommés admin
            """
            users_pl = {
                self.admin_id : 100,
            }
            
            self.make_room_unknown(self.state)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_user_membership(self.state, self.regular2_user_id, self.room_id)
            self.add_user_membership(self.state, self.external_user_id, self.room_id)
            self.add_user_membership(self.state, self.external2_user_id, self.room_id)
            self.add_users_in_room_with_pl(self.state, users_pl)

            module = await self.admin_leaves() #method to test

            pl_event_dict = await self.checkAPIcalled(module)
            self.assertDictEqual(pl_event_dict["content"]["users"], {
                self.admin_id : 100,
                self.regular_user_id : 100, # only internal is not promoted
                self.regular2_user_id : 100,# only internal is not promoted
            })

        async def test_last_admin_leaves_on_external_room_with_mod(
            self,
        ) -> None:
            """
            Scenario 5 - Salon Externe - Moderateur
            6 Participants : 1 admin - 2 moderateurs - 1 par defaut - 2 externe
            Admin quitte le salon
            => resultat attendu : 2 moderateurs sont promus
            """
            users_pl = {
                self.admin_id : 100,
                self.mod_user_id : 50, # mod
                self.mod2_user_id : 50, # mod
            }
            
            self.make_room_unknown(self.state)
            self.add_users_in_room_with_pl(self.state, users_pl)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_user_membership(self.state, self.external_user_id, self.room_id)

            module = await self.admin_leaves() #method to test

            pl_event_dict = await self.checkAPIcalled(module)
            self.assertDictEqual(pl_event_dict["content"]["users"], {
                self.admin_id : 100,
                self.mod_user_id : 100, #mod is promoted
                self.mod2_user_id : 100, #mod is promoted
            })
        
        async def test_last_admin_leaves_on_external_room_with_mod_external(
            self,
        ) -> None:
            """
            Scenario 6 - Salon Externe - Moderateur
            6 Participants : 1 admin - 1 moderateur - 1 par defaut - 1 moderateur externe
            Admin quitte le salon
            => résultat attendu : 1 modérateur -> admin
            """
            users_pl = {
                self.admin_id : 100,
                self.mod_user_id : 50, # mod
                self.external_user_id : 50, # mod external # this is not possible in real case
            }
            
            self.make_room_unknown(self.state)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)
            self.add_user_membership(self.state, self.external2_user_id, self.room_id)
            self.add_users_in_room_with_pl(self.state, users_pl)

            module = await self.admin_leaves() #method to test

            pl_event_dict = await self.checkAPIcalled(module)
            self.assertDictEqual(pl_event_dict["content"]["users"], {
                self.admin_id : 100,
                self.mod_user_id : 100, # only this mod is promoted
                self.external_user_id : 50,
            })

        async def test_is_last_admin_leaving_with_more_admins(
            self,
        ) -> None:
            
            users_pl = {
                self.admin_id : 100, 
                self.admin2_id : 100, #two admins in room
                self.regular_user_id : 0
            }
            
            self.make_room_unknown(self.state)
            self.add_users_in_room_with_pl(self.state, users_pl)
            self.add_user_membership(self.state, self.regular_user_id, self.room_id)

            leave_event = self.create_event(
                {
                    "sender": self.admin_id,
                    "type": EventTypes.Member,
                    "content": {"membership": Membership.LEAVE},
                    "room_id": self.room_id,
                    "state_key": self.admin_id,
                },
            )
            pl_content = _get_power_levels_content_from_state(self.state)
            
            #method to test
            last_admin_leaving = _is_last_admin_leaving(leave_event, pl_content, self.state) # type: ignore[arg-type]
            self.assertFalse(last_admin_leaving)

class ManageLastAdminTestRoomV9(ManageLastAdminTestScenarii.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict) -> EventBase:
        return make_event_from_dict(content, RoomVersions.V9)


class ManageLastAdminTestRoomV1(ManageLastAdminTestScenarii.BaseManageLastAdminTest):
    def create_event(self, content: JsonDict) -> EventBase:
        content["event_id"] = f"!{random_string(43)}:example.com"
        return make_event_from_dict(content, RoomVersions.V1)