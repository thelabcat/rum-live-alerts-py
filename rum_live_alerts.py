#!/usr/bin/env python3
"""Rumble Live Alerts OBS script

Live alerts for your Rumble livestream.

This file is part of Rumble Live Alerts .PY.

Rumble Live Alerts .PY is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Rumble Live Alerts .PY is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Foobar. If not, see <https://www.gnu.org/licenses/>.
S.D.G."""

from __future__ import annotations

from collections import namedtuple
from queue import Queue
import threading
from typing import NamedTuple
from typing import Sequence
from warnings import warn
try:
    import obspython as obs
except ModuleNotFoundError:
    print("""
---ERROR---

This script is meant to be run by OBS Studio, not by itself.
To add it, in the OBS Studio menu bar (at the top of the window), choose the
"Tools" menu, and click on "Scripts". When the Scripts dialog opens, click the
"+" button in the bottom left-hand corner of it. A file dialog should appear,
where you can browse to this script and load it. Then, select it in the list of
loaded scripts (the big box on the left-hand side of the Scripts dialog), and
you should see all of its settings on the right-hand side.

If you are on Windows or MacOS, you must have a Python install path set under
the Python Settings tab of the Scripts dialog.
"""
          )
    input("Goodbye! Press enter to exit.")
    quit()

try:
    import cocorum
    print("Cocorum successfully imported.")
    COCORUM_IMPORTED = True
except ModuleNotFoundError as e:
    print("ERROR: You must install the Python library 'cocorum' to use this script.")
    print(e)
    COCORUM_IMPORTED = False

SCRIPT_DESCRIPTION = """
<center>
<h1>Rumble Live Alerts PY</h1>
<p>Emulate the behavior of RumBot 4.5 and under, without WebSocket</p>
</center>
"""

MAX_ALERT_TIME = 6000  # Maximum for how long an alert can be displayed

# Minimum and maximum refresh rates to check the API again
REFRESH_RATE_MIN = cocorum.static.Delays.api_refresh_minimum if COCORUM_IMPORTED else 10

REFRESH_RATE_MAX = 300

# First entry of the Alert host scene selector. Preserves the old behavior of
# toggling alert sub-scenes inside whatever scene is current.
DYNAMIC_CURRENT_SCENE = "<dynamic: current scene>"

# Short line in the script settings. The long form is the log message and the README.
STUDIO_MODE_WARNING_UI = (
    "Studio Mode is on. Current-scene alerts can stay off-stream until the next transition."
)
STUDIO_MODE_WARNING_LOG = (
    "WARNING: Studio Mode is on and Alert host scene is '<dynamic: current scene>'. "
    "Alerts are toggled inside the current scene, but Studio Mode's program output "
    "uses a duplicate of that scene, so alerts may not appear on stream until the "
    "next transition. Pick a fixed Alert host scene (a master alerts scene nested "
    "into each program scene) to show alerts during Studio Mode."
)


def host_scene_is_dynamic(host_scene: str) -> bool:
    """True when alert sub-scenes should be looked up in the current scene"""
    return (not host_scene) or host_scene == DYNAMIC_CURRENT_SCENE


TextSettingsDefaults = namedtuple("TextSettingsDefaults", ["source", "text"])


class TextSettings:
    """Stored settings for a single alert text source"""

    def __init__(self, desc: str, source: str, text: str):
        """Stored settings for a single alert text source"""
        self.desc, self.source, self.text = desc, source, text
        self.defaults = TextSettingsDefaults(self.source, self.text)

    @property
    def slug(self):
        """Slug-ified name of description"""
        return self.desc.lower().replace(" ", "_")

    def set_obs_defaults(self, settings):
        """Set the OBS settings data defaults"""
        obs.obs_data_set_default_string(
            settings, self.slug + "_source", self.defaults.source)
        obs.obs_data_set_default_string(
            settings, self.slug + "_text", self.defaults.text)

    def add_properties(self, properties):
        """Add these text settings to OBS properties"""
        obs.obs_properties_add_list(properties, self.slug + "_source", self.desc +
                                    " text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_properties_add_text(
            properties, self.slug + "_text", self.desc + " format", obs.OBS_TEXT_DEFAULT)

    def get_from_obs(self, settings):
        """Extract our settings from OBS settings data"""
        self.source = obs.obs_data_get_string(settings, self.slug + "_source")
        self.text = obs.obs_data_get_string(settings, self.slug + "_text")


class AlertSettingsDefaults(NamedTuple):
    """Immutable default value storage for AlertSettings"""
    scene_source: str
    use: bool = True
    time: float = 10


class AlertSettings:
    """Stored settings for a whole alert type"""

    def __init__(
        self,
        orla: OBSRumLiveAlerts,
        desc: str,
        scene_source: str,
        texts: Sequence[TextSettings],
        use: bool = True,
        time: float = 10,
    ):
        """Stored settings for a whole alert type"""

        self.orla, self.desc, self.scene_source, self.texts, self.use, self.time = \
            orla, desc, scene_source, texts, use, time
        self.defaults = AlertSettingsDefaults(
            self.scene_source, self.use, self.time)

    @property
    def slug(self):
        """Slug-ified name of description"""
        return self.desc.lower().replace(" ", "_")

    def set_obs_defaults(self, settings):
        """Set the OBS settings data defaults"""
        obs.obs_data_set_default_bool(
            settings, self.slug + "_use", self.defaults.use)
        obs.obs_data_set_default_string(
            settings, self.slug + "_scene_source", self.defaults.scene_source)
        obs.obs_data_set_default_double(
            settings, self.slug + "_time", self.defaults.time)
        for text in self.texts:
            text.set_obs_defaults(settings)

    def add_properties(self, properties=None):
        """Add these alert settings to OBS properties"""
        properties = properties or self.orla.props
        obs.obs_properties_add_bool(
            properties, self.slug + "_use", "Use alert")
        scene_prop = obs.obs_properties_add_list(
            properties, self.slug + "_scene_source", "Sub-scene to flash", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        # Add all subscenes to the subscene source selector now
        for subscene_name in sorted(self.orla.subscene_names):
            obs.obs_property_list_add_string(
                scene_prop, subscene_name, subscene_name)

        obs.obs_properties_add_float(
            properties, self.slug + "_time", "Alert time", 1, MAX_ALERT_TIME, 1)
        for text in self.texts:
            text.add_properties(properties)

        return scene_prop

    def get_from_obs(self, settings):
        """Extract our settings from OBS settings data"""
        self.use = obs.obs_data_get_bool(settings, self.slug + "_use")
        self.scene_source = obs.obs_data_get_string(
            settings, self.slug + "_scene_source")
        self.time = obs.obs_data_get_double(settings, self.slug + "_time")
        for text in self.texts:
            text.get_from_obs(settings)

    def update_alert_source_lists(self, settings=None, selected_scene: str = None):
        """Filter available sources for named alert displays"""
        print(f"Updating {self.desc} source lists")
        assert selected_scene or settings, "Must be able to know selected scene source"

        selected_scene = selected_scene or obs.obs_data_get_string(
            settings, self.slug + "_scene_source")

        if selected_scene not in self.orla.scene_names_and_items:
            print(
                f"ERROR: Have no record of selected {self.desc} scene '{selected_scene}'")
            return False

        for text in self.texts:
            prop = obs.obs_properties_get(
                self.orla.props, text.slug + "_source")

            obs.obs_property_list_clear(prop)
            for text_name in self.orla.get_text_items(selected_scene):
                print(f"\t-{text_name}")
                obs.obs_property_list_add_string(prop, text_name, text_name)

        return True


class LocalSettings:
    """Storage for the settings that OBS can modify, with default values"""

    def __init__(self, orla: OBSRumLiveAlerts, api_url: str = "", api_refresh_rate: float = cocorum.static.Delays.api_refresh_default if COCORUM_IMPORTED else 10):
        """Storage for the settings that OBS can modify, with default values"""
        self.orla, self.api_url, self.api_refresh_rate = \
            orla, api_url, api_refresh_rate
        # Blank saved settings also select the dynamic option
        self.alert_host_scene = DYNAMIC_CURRENT_SCENE

        self.follower = AlertSettings(
            orla=self.orla,
            desc="Follower alert",
            scene_source="Follower Scene",
            texts=[
                TextSettings(
                    desc="Follower username",
                    source="Follower Username",
                    text="{username} just followed!",
                ),
            ],
        )

        self.subscriber = AlertSettings(
            orla=self.orla,
            desc="Subscriber alert",
            scene_source="Subscriber Scene",
            texts=[
                TextSettings(
                    desc="Subscriber username",
                    source="Subscriber Username",
                    text="{username} just subscribed!",
                ),
                TextSettings(
                    desc="Subscriber amount dollars",
                    source="Subscriber Amount Dollars",
                    text="For ${dollars}.{cents}",
                ),
            ],
        )

        self.rant = AlertSettings(
            orla=self.orla,
            desc="Rant alert",
            scene_source="Rant Scene",
            texts=[
                TextSettings(
                    desc="Rant username",
                    source="Rant Username",
                    text="{username} said:",
                ),
                TextSettings(
                    desc="Rant message",
                    source="Rant Message",
                    text="\"{message}\"",
                ),
                TextSettings(
                    desc="Rant amount dollars",
                    source="Rant Amount Dollars",
                    text="For ${dollars}.{cents}",
                ),
            ],
        )

        self.raid = AlertSettings(
            orla=self.orla,
            desc="Raid alert",
            scene_source="Raid Scene",
            texts=[
                TextSettings(
                    desc="Raid username",
                    source="Raid Username",
                    text="{username} raided!",
                ),
            ],
        )

        self.gift = AlertSettings(
            orla=self.orla,
            desc="Gift alert",
            scene_source="Gift Scene",
            texts=[
                TextSettings(
                    desc="Gift info",
                    source="Gift Info",
                    text="{username} gifted {gift_count} subs!",
                ),
            ],
        )

    def set_obs_defaults(self, settings):
        """Set the OBS settings data defaults"""
        obs.obs_data_set_default_string(settings, "api_url", "")
        obs.obs_data_set_default_string(
            settings, "alert_host_scene", DYNAMIC_CURRENT_SCENE)
        obs.obs_data_set_default_double(
            settings, "api_refresh_rate", cocorum.static.Delays.api_refresh_default if COCORUM_IMPORTED else 10)
        for attr in (
            self.follower,
            self.subscriber,
            self.rant,
            self.raid,
            self.gift,
        ):
            attr.set_obs_defaults(settings)

    def add_master_properties(self, properties=None):
        """Add the toplevel settings to OBS properties"""
        properties = properties or self.orla.props

        # Which scene holds the alert sub-scenes. Dynamic keeps today's lookup.
        host_prop = obs.obs_properties_add_list(
            properties,
            "alert_host_scene",
            "Alert host scene",
            obs.OBS_COMBO_TYPE_LIST,
            obs.OBS_COMBO_FORMAT_STRING,
        )
        self.orla.fill_alert_host_scene_list(host_prop)
        obs.obs_property_set_modified_callback(
            host_prop, update_studio_mode_warning_disp)

        warning_prop = obs.obs_properties_add_text(
            properties,
            "studio_mode_warning",
            "You should not see this text.",
            obs.OBS_TEXT_INFO,
        )
        obs.obs_property_text_set_info_type(
            warning_prop, obs.OBS_TEXT_INFO_WARNING)
        obs.obs_property_set_visible(warning_prop, False)

        api_url_prop = obs.obs_properties_add_text(
            properties, "api_url", "API URL (with key)", obs.OBS_TEXT_PASSWORD)
        obs.obs_property_set_modified_callback(api_url_prop, update_api_url_err_disp)
        obs.obs_properties_add_text(
            properties, "api_obtain_link", "<a href='https://rumble.com/account/livestream-api'>Click here to get a URL with key from Rumble.</a>", obs.OBS_TEXT_INFO)

        obs.obs_properties_add_float(
            properties, "api_refresh_rate", "Refresh Rate (seconds)", REFRESH_RATE_MIN, REFRESH_RATE_MAX, 1)

        error_prop = obs.obs_properties_add_text(
            properties, "api_url_error", "You should not see this text.", obs.OBS_TEXT_INFO)
        obs.obs_property_text_set_info_type(error_prop, obs.OBS_TEXT_INFO_WARNING)
        obs.obs_property_set_visible(error_prop, False)

    def get_from_obs(self, settings):
        """Extract settings from OBS settings data"""
        self.api_url = obs.obs_data_get_string(settings, "api_url")
        self.alert_host_scene = obs.obs_data_get_string(
            settings, "alert_host_scene") or DYNAMIC_CURRENT_SCENE
        self.api_refresh_rate = obs.obs_data_get_double(
            settings, "api_refresh_rate")
        for attr in (
            self.follower,
            self.subscriber,
            self.rant,
            self.raid,
            self.gift,
        ):
            attr.get_from_obs(settings)

    def update_all_source_lists(self):
        """Update the available text sources to select"""
        return sum(
            (
                attr.update_alert_source_lists(
                    selected_scene=attr.defaults.scene_source)
                for attr in (
                    self.follower,
                    self.subscriber,
                    self.rant,
                    self.raid,
                    self.gift,
                )
            )
        ) > 0


class TestAlert:
    """Alert object dummy with the same attributes as any real one"""
    # Main RLS API alert: follower, subscriber
    username = "NOBODY"
    amount_cents = 316

    # ChatAPI alert: rant, raid, gift
    class user:
        """User dummy subclass"""
        username = "NOBODY"
    rant_price_cents = 316
    text = "Soli Deo gloria."

    class gift_purchase_notification:
        """Gift purchase notification data dummy subclass"""
        total_gifts = 37


class ChatAlertReceiver(threading.Thread):
    """Connect to a Rumble chat, and push message alerts from it to queues"""

    def __init__(
        self,
        stream_id: int | str,
        rant_queue: Queue,
        raid_queue: Queue,
        gift_queue: Queue,
    ):
        """
        Connect to a Rumble chat, and push alerts from it to queues

        Args:
            stream_id (int | str): The numeric ID of the stream to connect to.
            raid_queue (Queue): The queue to push raid alerts to."""

        super().__init__(daemon=True)

        self.stream_id = stream_id
        self.chat = None
        self.rant_queue = rant_queue
        self.raid_queue = raid_queue
        self.gift_queue = gift_queue

        # Thread-safe killswitch
        self.running = False

    def run(self):
        """The threaded code"""
        with cocorum.chatapi.ChatAPI(self.stream_id) as self.chat:
            self.chat.clear_mailbox()
            self.running = True
            while self.running:
                # The chat closed, gracefully exit
                message = self.chat.get_message()
                if not message:
                    print("Chat", self.chat.stream_id_b10, "closed.")
                    self.running = False
                    continue

                # The message is a rant
                if message.is_rant:
                    self.rant_queue.put(message)
                    continue

                # The message is a raid
                if message.raid_notification:
                    self.raid_queue.put(message)
                    continue

                # The message is a gift purchase
                if message.gift_purchase_notification:
                    self.gift_queue.put(message)
                    continue


class OBSRumLiveAlerts():
    """OBS Rumble live alerts system"""

    def __init__(self):
        """Instanced once within script as a reliable memory system"""
        print("Initializing OBSRumLiveAlerts object")
        self.__obs_timers_set = False
        self.__frontend_event_callback_set = False
        # True while the dynamic-host + Studio Mode warning is already showing
        self.__studio_mode_warning_active = False
        self.alerts_mutex = threading.Lock()
        self.api = None
        self.api_url_error = None
        self.livestream = None
        self.chat_alert_receiver = None

        self.props = None
        self.scene_names_and_items = {}
        self.subscene_names = set()
        self.source_names_to_types = {}

        # Inboxes of things waiting to be alerted for
        self.follower_inbox = Queue()
        self.subscriber_inbox = Queue()
        self.rant_inbox = Queue()
        self.raid_inbox = Queue()
        self.gift_inbox = Queue()

        # The main settings storage
        self.settings = LocalSettings(orla=self)

    def script_defaults(self, settings):
        """Set OBS setting defaults"""
        self.settings.set_obs_defaults(settings)
        print("Set script defaults")

    def script_properties(self):
        """Set up the configuration properties for this script"""
        print("Setting up script properties")
        self.props = obs.obs_properties_create()
        self.get_scenes_and_sources()

        # Base settings
        obs.obs_properties_add_text(
            self.props, "base_settings_header", "<h2>Base Settings</h2>", obs.OBS_TEXT_INFO)
        self.settings.add_master_properties(self.props)

        # Settings for the follower alert
        obs.obs_properties_add_text(
            self.props, "follower_alert_header", "<hr><h2>Follower Alert</h2>", obs.OBS_TEXT_INFO)
        follower_scene_prop = self.settings.follower.add_properties(self.props)
        # We have to bind the test button to a global callback instead of an instance method
        obs.obs_property_set_modified_callback(
            follower_scene_prop, update_follower_source_lists)
        obs.obs_properties_add_button(
            self.props, "follower_alert_test", "Queue a follower test", test_follower_alert)

        # Settings for the subscriber alert
        obs.obs_properties_add_text(
            self.props, "subscriber_alert_header", "<hr><h2>Subscriber Alert</h2>", obs.OBS_TEXT_INFO)
        subscriber_scene_prop = self.settings.subscriber.add_properties(
            self.props)
        # We have to bind the test button to a global callback instead of an instance method
        obs.obs_property_set_modified_callback(
            subscriber_scene_prop, update_subscriber_source_lists)
        obs.obs_properties_add_button(
            self.props, "subscriber_alert_test", "Queue a subscriber test", test_subscriber_alert)

        # Settings for the rant alert
        obs.obs_properties_add_text(
            self.props, "rant_alert_header", "<hr><h2>Rant Alert</h2>", obs.OBS_TEXT_INFO)
        rant_scene_prop = self.settings.rant.add_properties(self.props)
        # We have to bind the test button to a global callback instead of an instance method
        obs.obs_property_set_modified_callback(
            rant_scene_prop, update_rant_source_lists)
        obs.obs_properties_add_button(
            self.props, "rant_alert_test", "Queue a rant test", test_rant_alert)

        # Settings for the raid alert
        obs.obs_properties_add_text(
            self.props, "raid_alert_header", "<hr><h2>Raid Alert</h2>", obs.OBS_TEXT_INFO)
        raid_scene_prop = self.settings.raid.add_properties(self.props)
        # We have to bind the test button to a global callback instead of an instance method
        obs.obs_property_set_modified_callback(
            raid_scene_prop, update_raid_source_lists)
        obs.obs_properties_add_button(
            self.props, "raid_alert_test", "Queue a raid test", test_raid_alert)

        # Settings for the gift alert
        obs.obs_properties_add_text(
            self.props, "gift_alert_header", "<hr><h2>Gift Alert</h2>", obs.OBS_TEXT_INFO)
        gift_scene_prop = self.settings.gift.add_properties(self.props)
        # We have to bind the test button to a global callback instead of an instance method
        obs.obs_property_set_modified_callback(
            gift_scene_prop, update_gift_source_lists)
        obs.obs_properties_add_button(
            self.props, "gift_alert_test", "Queue a gift test", test_gift_alert)

        print("Updating text display selectors")
        self.settings.update_all_source_lists()

        # Checked when the properties widgets are built, not on later Studio Mode toggles
        self.update_studio_mode_warning()

        print("Properties initialized.")
        return self.props

    def script_update(self, settings):
        """Update the script settings"""
        print("Updating with settings")
        self.settings.get_from_obs(settings)

        # Deactivate timers and remove old livestream reference
        self.remove_obs_timers()
        self.livestream = None
        self.abandon_chat_alert_receiver()

        # We have an API URL
        if self.settings.api_url:
            try:
                # We had no API before
                if not self.api:
                    print("Creating new Cocorum API object")
                    self.api = cocorum.RumbleAPI(
                        self.settings.api_url, refresh_rate=self.settings.api_refresh_rate)

                # We do have an API but the URL is outdated
                elif self.api.api_url != self.settings.api_url or self.api.refresh_rate != self.settings.api_refresh_rate:
                    print("Updating Cocorum API URL and refresh rate")
                    self.api.api_url = self.settings.api_url
                    self.api.refresh_rate = self.settings.api_refresh_rate

            # The API URL was invalid
            except (AssertionError, cocorum.requests.exceptions.RequestException) as e:
                print(f"ERROR: API connection failed: {e}")
                self.settings.api_url = ""
                self.api_url_error = e

            # The API URL succeeded
            else:
                self.api_url_error = None

            # Make sure the error label updates in the UI
            if self.props:
                obs.obs_properties_apply_settings(self.props, settings)

            # Reset livestream reference
            self.livestream = None
            self.abandon_chat_alert_receiver()

            if not self.api_url_error:
                # Clear these mailboxes
                print("Stale new followers: ", self.api.new_followers)
                print("Stale new subscribers: ", self.api.new_subscribers)

        # Always run alert timers so queued test alerts still display without an API key
        self.set_obs_timers()

        print("Script settings updated.")

    def get_text_items(self, scene_name: str) -> list[str]:
        """Pull up the records of all text type sources within a scene"""
        return sorted(
            item_name
            for item_name in self.scene_names_and_items.get(scene_name, set())
            if self.source_names_to_types.get(item_name, "NULL_RECORD") in ("text_gdiplus", "text_ft2_source")
        )

    def set_obs_timers(self):
        """Set all the timers we need in OBS"""
        print("Activating timers")
        if self.__obs_timers_set:
            print("ERROR: Timers already set.")
            return
        self.__obs_timers_set = True
        obs.timer_add(check_main_rls_api, int(
            self.settings.api_refresh_rate * 1000))
        obs.timer_add(next_follower_alert, int(
            self.settings.follower.time * 1000))
        obs.timer_add(next_subscriber_alert, int(
            self.settings.subscriber.time * 1000))
        obs.timer_add(next_rant_alert, int(self.settings.rant.time * 1000))
        obs.timer_add(next_raid_alert, int(self.settings.raid.time * 1000))
        obs.timer_add(next_gift_alert, int(self.settings.gift.time * 1000))

    def remove_obs_timers(self):
        """Remove all the timers we would set for OBS"""
        print("Removing timers")
        if not self.__obs_timers_set:
            print("ERROR: Timers were not set.")
            return
        self.__obs_timers_set = False
        obs.timer_remove(check_main_rls_api)
        obs.timer_remove(next_follower_alert)
        obs.timer_remove(next_subscriber_alert)
        obs.timer_remove(next_rant_alert)
        obs.timer_remove(next_raid_alert)
        obs.timer_remove(next_gift_alert)

    def remove_frontend_event_callback(self):
        """Drop the frontend event callback registered in script_load"""
        if not self.__frontend_event_callback_set:
            print("ERROR: Frontend event callback was not set.")
            return
        print("Removing frontend event callback")
        obs.obs_frontend_remove_event_callback(on_frontend_event)
        self.__frontend_event_callback_set = False

    def abandon_chat_alert_receiver(self):
        """If we have a chat alert receiver, tell it to stop, and remove its reference"""
        if self.chat_alert_receiver:
            self.chat_alert_receiver.chat.close()  # It should automatically do this, but doing it again shouldn't cause problems and this will make it exit faster
            self.chat_alert_receiver.running = False
            self.chat_alert_receiver = None

    def script_load(self, settings):
        """Register frontend callbacks once OBS has finished loading the script"""
        print("Registering frontend event callback")
        if self.__frontend_event_callback_set:
            print("ERROR: Frontend event callback already set.")
            return
        # Python wrapper takes only the function. private_data stays inside OBS.
        # The callback must be a module-level function, not a bound method.
        obs.obs_frontend_add_event_callback(on_frontend_event)
        self.__frontend_event_callback_set = True

        # script_update has not run yet, and Studio Mode may already be on.
        # The enable event will not be replayed for us.
        host_scene = obs.obs_data_get_string(settings, "alert_host_scene")
        self.update_studio_mode_warning(host_scene=host_scene)

    def script_unload(self):
        """Perform script cleanup"""
        print("Unload triggered. Cleaning up")

        self.remove_frontend_event_callback()

        # Deactivate timers and remove old livestream reference
        self.remove_obs_timers()
        self.livestream = None
        self.abandon_chat_alert_receiver()
        if self.alerts_mutex.locked():
            print("WARNING: Releasing alerts mutex.")
            self.alerts_mutex.release()

        print("Unloaded.")

    def get_scenes_and_sources(self):
        """Get listing of OBS scenes and scene item sources"""
        print("Getting scenes and sources...")

        print("Enumerating non-subscene sources")
        # Sources that are not subscenes
        sources = obs.obs_enum_sources()
        if sources:
            print("Getting non-subscene source names")
            self.source_names_to_types = {obs.obs_source_get_name(
                s): obs.obs_source_get_unversioned_id(s) for s in sources}
            print("Releasing source list")
            obs.source_list_release(sources)
        else:
            print("No sources found.")

        print("Getting all scenes (as sources for some reason)")
        scene_sources = obs.obs_frontend_get_scenes()
        if scene_sources:
            print("Getting scene names")
            self.scene_names_and_items = {
                obs.obs_source_get_name(s): set() for s in scene_sources}
            print("Releasing scene sources list")
            obs.source_list_release(scene_sources)
        else:
            print("No scenes found.")

        print("Evaluating which scenes are subscenes")
        self.subscene_names = set()
        for scene_name, item_names in self.scene_names_and_items.items():
            print(scene_name + ":")
            # print("\t(getting scene items)")
            scene = obs.obs_get_scene_by_name(scene_name)
            scene_items = obs.obs_scene_enum_items(scene)
            if scene_items:
                for item in scene_items:
                    # Get scene item as source and name
                    # print("\t(getting source of scene item)")
                    # Does not increment the reference, do not independently release
                    source = obs.obs_sceneitem_get_source(item)
                    # print("\t(getting source name)")
                    name = obs.obs_source_get_name(source)

                    # Make record that the item is in this scene (same name = same linked source)
                    item_names.add(name)

                    # Is this item a subscene source?
                    # print("\t(identifying source type)")
                    # If this is not a subscene source, we will have a record of it already
                    unversioned_id = self.source_names_to_types.get(
                        name) or obs.obs_source_get_unversioned_id(source)
                    if unversioned_id == "scene":
                        print(f"\t{unversioned_id}: {name} <--")
                        self.subscene_names.add(name)
                    else:
                        print(f"\t{unversioned_id}: {name}")
                    # print("\t(releasing that source)\n")
                    # obs.obs_source_release(source)

                # print("Releasing scene items list")
                obs.sceneitem_list_release(scene_items)
            else:
                print("\t--No items in this scene--")
            obs.obs_scene_release(scene)

    def set_text_by_source_name(self, source_name: str, new_value: str):
        """Sets the value of a text source"""

        source = obs.obs_get_source_by_name(source_name)
        if not source:
            print(
                f"ERROR: Could not set text for source '{source_name}': Source not found.")
            return
        setter_data = obs.obs_data_create()

        obs.obs_data_set_string(setter_data, "text", new_value)
        obs.obs_source_update(source, setter_data)

        obs.obs_data_release(setter_data)
        obs.obs_source_release(source)

    def set_texts_by_source_names(self, source_texts: dict[str, str]):
        """Sets the values of multiple text sources"""
        for source_name, new_value in source_texts.items():
            self.set_text_by_source_name(source_name, new_value)

    def check_main_rls_api(self):
        """Check if there are any new alertables in the main RLS API and add them to the inboxes"""
        # We have no API URL or it was invalid (timers still run for test alerts)
        if not self.settings.api_url or self.api_url_error:
            return

        print("Checking main RLS API")
        for new_follower in self.api.new_followers:
            self.follower_inbox.put(new_follower)

        for new_subscriber in self.api.new_subscribers:
            self.subscriber_inbox.put(new_subscriber)

        # Livestream change handler
        # Current stream is no longer live
        if self.livestream and self.livestream.is_disappeared:
            print("Livestream shut down.")
            self.livestream = None
            self.abandon_chat_alert_receiver()

        # Other cases
        """
        We have a livestream and it is live: Even if there is a new one, stay here.
        We do not have a livestream and there is no new one. Do nothing.
        """

        # We have no livestream [anymore] and there is one live
        if not self.livestream and (new := self.api.latest_livestream):
            self.livestream = new
            print("New livestream:", self.livestream.title)
            self.chat_alert_receiver = ChatAlertReceiver(
                self.livestream.stream_id,
                self.rant_inbox,
                self.raid_inbox,
                self.gift_inbox,
            )
            self.chat_alert_receiver.start()

        # There is a livestream, so it may have new rants
        # Handle this in the chat alert receiver instead
        # for new_rant in self.livestream.chat.new_rants:
        #     self.rant_inbox.put(new_rant)

    def next_follower_alert(self):
        """Do the next follower alert, finishing up the last one"""
        self.__next_generic_alert(
            "follower",
            self.settings.follower.scene_source,
            self.follower_inbox,
            self.settings.follower.use,
            lambda follower:
                self.set_texts_by_source_names({
                    t.source: t.text.format(
                        username=follower.username,
                    )
                    for t in self.settings.follower.texts
                }),
        )

    def next_subscriber_alert(self):
        """Do the next subscriber alert, finishing up the last one"""
        self.__next_generic_alert(
            "subscriber",
            self.settings.subscriber.scene_source,
            self.subscriber_inbox,
            self.settings.subscriber.use,
            lambda subscriber:
                self.set_texts_by_source_names({
                    t.source: t.text.format(
                        username=subscriber.username,
                        dollars=subscriber.amount_cents // 100,
                        cents=subscriber.amount_cents % 100,
                    )
                    for t in self.settings.subscriber.texts
                }),
        )

    def next_rant_alert(self):
        """Do the next rant alert, finishing up the last one"""
        self.__next_generic_alert(
            "rant",
            self.settings.rant.scene_source,
            self.rant_inbox,
            self.settings.rant.use,
            lambda rant:
                self.set_texts_by_source_names({
                    t.source: t.text.format(
                        username=rant.user.username,
                        dollars=rant.rant_price_cents // 100,
                        cents=rant.rant_price_cents % 100,
                        message=rant.text,
                    )
                    for t in self.settings.rant.texts
                }),
        )

    def next_raid_alert(self):
        """Do the next raid alert, finishing up the last one"""
        self.__next_generic_alert(
            "raid",
            self.settings.raid.scene_source,
            self.raid_inbox,
            self.settings.raid.use,
            lambda raid:
                self.set_texts_by_source_names({
                    t.source: t.text.format(
                        username=raid.user.username,
                    )
                    for t in self.settings.raid.texts
                }),
        )

    def next_gift_alert(self):
        """Do the next gift alert, finishing up the last one"""
        self.__next_generic_alert(
            "gift",
            self.settings.gift.scene_source,
            self.gift_inbox,
            self.settings.gift.use,
            lambda gift:
                self.set_texts_by_source_names({
                    t.source: t.text.format(
                        username=gift.user.username,
                        gift_count=gift.gift_purchase_notification.total_gifts
                    )
                    for t in self.settings.gift.texts
                }),
        )

    def fill_alert_host_scene_list(self, prop):
        """Fill the Alert host scene selector. The dynamic option is first."""
        obs.obs_property_list_clear(prop)
        obs.obs_property_list_add_string(
            prop, DYNAMIC_CURRENT_SCENE, DYNAMIC_CURRENT_SCENE)
        for scene_name in sorted(self.scene_names_and_items):
            if scene_name == DYNAMIC_CURRENT_SCENE:
                print(
                    f"WARNING: A scene is named '{DYNAMIC_CURRENT_SCENE}', "
                    "which is reserved for the dynamic option."
                )
                continue
            obs.obs_property_list_add_string(prop, scene_name, scene_name)

    def refresh_alert_host_scene_list(self):
        """Rebuild the Alert host scene selector after the scene list changes.

        The scripts panel keeps a Qt copy of the combo. This updates the
        property OBS will use the next time that panel rebuilds its widgets.
        """
        if not self.props:
            return
        prop = obs.obs_properties_get(self.props, "alert_host_scene")
        if not prop:
            return
        print("Scene list changed. Refreshing Alert host scene selector.")
        self.get_scenes_and_sources()
        self.fill_alert_host_scene_list(prop)

    def update_studio_mode_warning(self, props=None, host_scene: str = None):
        """Show a one-line Studio Mode warning for the dynamic host scene.

        Called when the script loads, when its properties are built, and when
        Alert host scene changes. Prints the long warning once each time that
        combination becomes active. Returns True so the host-scene modified
        callback refreshes the scripts panel.
        """
        if host_scene is None:
            host_scene = self.settings.alert_host_scene
        applies = host_scene_is_dynamic(host_scene) and bool(
            obs.obs_frontend_preview_program_mode_active())

        props = props or self.props
        if props:
            warning_prop = obs.obs_properties_get(props, "studio_mode_warning")
            if warning_prop:
                if applies:
                    obs.obs_property_set_description(
                        warning_prop, STUDIO_MODE_WARNING_UI)
                    obs.obs_property_set_visible(warning_prop, True)
                else:
                    obs.obs_property_set_description(warning_prop, "")
                    obs.obs_property_set_visible(warning_prop, False)

        if applies:
            if not self.__studio_mode_warning_active:
                self.__studio_mode_warning_active = True
                print(STUDIO_MODE_WARNING_LOG)
        else:
            self.__studio_mode_warning_active = False
        return True

    def on_frontend_event(self, event):
        """Refresh the Alert host scene selector when the scene list changes.

        Studio Mode toggles do not rebuild the warning. That is checked when
        the script loads, when its properties are built, and when Alert host
        scene changes. Does not toggle Studio Mode.
        """
        # Scene add, remove, and rename. Collection switches replace the list.
        if event in (
            obs.OBS_FRONTEND_EVENT_SCENE_LIST_CHANGED,
            obs.OBS_FRONTEND_EVENT_SCENE_COLLECTION_CHANGED,
        ):
            self.refresh_alert_host_scene_list()

    def __next_generic_alert(self, name: str, alert_scene_source: str, inbox: Queue, set_to_use: bool, config_alert_display: callable):
        """Do the next generic alert, finishing up the last one"""
        print(f"Doing {name} alert tick")

        # Both lookups increment the source refcounter. obs_scene_from_source
        # does not. Release the source, not the scene.
        host_name = self.settings.alert_host_scene
        if host_scene_is_dynamic(host_name):
            host_source = obs.obs_frontend_get_current_scene()
        else:
            host_source = obs.obs_get_source_by_name(host_name)

        if not host_source:
            print(
                f"ERROR: Alert host scene '{host_name or DYNAMIC_CURRENT_SCENE}' was not found.")
            return

        # Does not increase the refcounter. Release host_source in finally.
        host_scene = obs.obs_scene_from_source(host_source)

        try:
            if not host_scene:
                print(
                    f"ERROR: Alert host '{obs.obs_source_get_name(host_source)}' is not a scene.")
                return

            subscene_sceneitem = obs.obs_scene_find_source(
                host_scene, alert_scene_source)
            if not subscene_sceneitem:
                print(
                    f"Alert host scene '{obs.obs_source_get_name(host_source)}' does not contain scene '{alert_scene_source}'")
                return

            # Finish up the last gift alert
            if obs.obs_sceneitem_visible(subscene_sceneitem):
                obs.obs_sceneitem_set_visible(subscene_sceneitem, False)
                self.alerts_mutex.release()
                print(f"Finished {name} alert.")
                # Have delay between alerts, so they can exit transition properly
                return

            # Check for a new gift
            if inbox.empty():
                return

            # We have a gift
            # Alerts must not happen at the same time
            lock = self.alerts_mutex.acquire(blocking=False)
            if not lock:
                print("Another alert is in progress. Wait.")
                return

            alertable = inbox.get()
            print(f"New {name}: {alertable}")

            # We are set to not do gift alerts
            if not set_to_use:
                print(f"{name.capitalize()} alerts are disabled.")
                self.alerts_mutex.release()
                return

            # Set the alert display based on the alertable
            config_alert_display(alertable)

            # Show the alert
            obs.obs_sceneitem_set_visible(subscene_sceneitem, True)

        finally:
            obs.obs_source_release(host_source)

    # TODO: Use lambda for these?
    def test_follower_alert(self, props, prop):
        """Test the follower alert button"""
        self.follower_inbox.put(TestAlert)
        print("Test follower queued.")
        return False

    def test_subscriber_alert(self, props, prop):
        """Test the subscriber alert button"""
        self.subscriber_inbox.put(TestAlert)
        print("Test subscriber queued.")
        return False

    def test_rant_alert(self, props, prop):
        """Test the rant alert button"""
        self.rant_inbox.put(TestAlert)
        print("Test rant queued.")
        return False

    def test_raid_alert(self, props, prop):
        """Test the raid alert button"""
        self.raid_inbox.put(TestAlert)
        print("Test raid queued.")
        return False

    def test_gift_alert(self, props, prop):
        """Test the gift alert button"""
        self.gift_inbox.put(TestAlert)
        print("Test gift queued.")
        return False

    def update_api_url_err_disp(self, props, prop, settings):
        """Update (or clear) the API URL error label. Returns True to refresh the UI."""
        error_prop = obs.obs_properties_get(props, "api_url_error")
        if not error_prop:
            return False

        if self.api_url_error:
            # Orange via OBS_TEXT_INFO_WARNING; optional extra HTML color if you want
            text = f"URL failed to load: {self.api_url_error}"
            obs.obs_property_set_description(error_prop, text)
            obs.obs_property_set_visible(error_prop, True)
        else:
            obs.obs_property_set_description(error_prop, "")
            obs.obs_property_set_visible(error_prop, False)

        return True  # required so OBS refreshes the properties widgets


rla = OBSRumLiveAlerts()
print("RLA initialized.")

# Global wrappers for source list updates


def update_follower_source_lists(props, prop, settings):
    """Filter available sources for follower alert displays (global wrapper for RLA instance)"""
    return rla.settings.follower.update_alert_source_lists(settings)


def update_subscriber_source_lists(props, prop, settings):
    """Filter available sources for subscriber alert displays (global wrapper for RLA instance)"""
    return rla.settings.subscriber.update_alert_source_lists(settings)


def update_rant_source_lists(props, prop, settings):
    """Filter available sources for rant alert displays (global wrapper for RLA instance)"""
    return rla.settings.rant.update_alert_source_lists(settings)


def update_raid_source_lists(props, prop, settings):
    """Filter available sources for raid alert displays (global wrapper for RLA instance)"""
    return rla.settings.raid.update_alert_source_lists(settings)


def update_gift_source_lists(props, prop, settings):
    """Filter available sources for gift alert displays (global wrapper for RLA instance)"""
    return rla.settings.gift.update_alert_source_lists(settings)

# Global wrappers for timed ticks


def check_main_rls_api():
    """(global wrapper for RLA instance)"""
    return rla.check_main_rls_api()


def next_follower_alert():
    """(global wrapper for RLA instance)"""
    return rla.next_follower_alert()


def next_subscriber_alert():
    """(global wrapper for RLA instance)"""
    return rla.next_subscriber_alert()


def next_rant_alert():
    """(global wrapper for RLA instance)"""
    return rla.next_rant_alert()


def next_raid_alert():
    """(global wrapper for RLA instance)"""
    return rla.next_raid_alert()


def next_gift_alert():
    """(global wrapper for RLA instance)"""
    return rla.next_gift_alert()


# Global wrappers for alert tests
def test_follower_alert(props, prop):
    """Test the follower alert button (global wrapper for RLA instance)"""
    return rla.test_follower_alert(props, prop)


def test_subscriber_alert(props, prop):
    """Test the subscriber alert button (global wrapper for RLA instance)"""
    return rla.test_subscriber_alert(props, prop)


def test_rant_alert(props, prop):
    """Test the rant alert button (global wrapper for RLA instance)"""
    return rla.test_rant_alert(props, prop)


def test_raid_alert(props, prop):
    """Test the raid alert button (global wrapper for RLA instance)"""
    return rla.test_raid_alert(props, prop)


def test_gift_alert(props, prop):
    """Test the gift alert button (global wrapper for RLA instance)"""
    return rla.test_gift_alert(props, prop)


def script_description() -> str:
    """The title and description for the script"""
    return SCRIPT_DESCRIPTION


# Global wrapper for URL error text
def update_api_url_err_disp(props, prop, settings):
    """Update (or clear) the API URL error label. Returns True to refresh the UI."""
    return rla.update_api_url_err_disp(props, prop, settings)


def update_studio_mode_warning_disp(props, prop, settings):
    """Show the Studio Mode warning when the dynamic host scene is selected."""
    host_scene = obs.obs_data_get_string(settings, "alert_host_scene")
    return rla.update_studio_mode_warning(props, host_scene)


def on_frontend_event(event):
    """Frontend event callback (global wrapper for RLA instance).

    Must be a function, not a bound method: OBS rejects methods with
    PyFunction_Check and would silently skip the registration.
    """
    return rla.on_frontend_event(event)


# Cocorum is available, we can continue as normal
if COCORUM_IMPORTED:
    # Make methods of the RLA instance globally accessible to OBS
    script_properties = rla.script_properties
    script_defaults = rla.script_defaults
    script_update = rla.script_update
    script_load = rla.script_load
    script_unload = rla.script_unload

# Cocorum failed to import, fall back
else:
    def script_properties():
        """Fallback script properties display to gracefully inform of error"""
        props = obs.obs_properties_create()
        obs.obs_properties_add_text(
            props,
            "error_notice",
            """
<center><h2>ERROR</h2></center>

<p>This script requires the Python library 'cocorum' to operate.
You can <a href="https://pypi.org/project/cocorum/">get it from PYPI</a>.
Note that it must be installed to the Python environment that OBS Studio is
using.
</p>
<ul>
<li><b>Linux:</b> If Pip complains that your default Python environment is
externally managed, or you are using the Flatpak version of OBS, create a
Python virtual environment, install cocorum to it, and then add its
`site-packages` directory to the `PYTHONPATH` environment variable for OBS.
For Flatpak, you should do this in Flatpak settings (possibly via Flatseal).
For regular system pckages or some other form, you can add it to the desktop
configuration file.</li>
<li><b>Windows:</b> You must tell OBS Studio where to load Python from, via the
<em>Python Settings</em> tab of this window.</li>
</ul>

<p>Goodbye!</p>
            """,
            obs.OBS_TEXT_INFO,
        )
        return props
