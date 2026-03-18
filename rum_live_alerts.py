#!/usr/bin/env python3
"""Rumble Live Alerts OBS script

Live alerts for your Rumble livestream.
S.D.G."""

from queue import Queue
import threading
import obspython as obs
import cocorum

#API_URL_START = "https://rumble.com/-livestream-api/get-data?key="
MAX_ALERT_TIME = 6000  # Maximum for how long an alert can be displayed

# Minimum and maximum refresh rates to check the API again
REFRESH_RATE_MIN = 10
REFRESH_RATE_MAX = 300


class DefaultSettings:
    """The default values for the various settings in the OBS UI"""
    # Base settings
    api_url = ""  # Rumble Live Stream API URL
    refresh_rate = 10  # API refresh rate

    # Settings for the follower alert
    follower_alert_use = True
    follower_alert_time = 10
    follower_alert_uname_source = "Follower Username"
    follower_alert_scene_source = "Follower Scene"

    # Settings for the subscriber alert
    subscriber_alert_use = True
    subscriber_alert_time = 10
    subscriber_alert_uname_source = "Subscriber Username"
    subscriber_alert_amount_source = "Subscriber Amount Dollars"
    subscriber_alert_scene_source = "Subscriber Scene"

    # Settings for the rant alert
    rant_alert_use = True
    rant_alert_time = 10
    rant_alert_uname_source = "Rant Username"
    rant_alert_message_source = "Rant Message"
    rant_alert_amount_source = "Rant Amount Dollars"
    rant_alert_scene_source = "Rant Scene"

    # Settings for the raid alert
    raid_alert_use = True
    raid_alert_time = 10
    raid_alert_uname_source = "Raid Username"
    raid_alert_scene_source = "Raid Scene"

    # Settings for the gift alert
    gift_alert_use = True
    gift_alert_time = 10
    gift_alert_uname_source = "Gift Username"
    gift_alert_count_source = "Gift Count"
    #gift_alert_amount_source = "Gift Amount Dollars"
    gift_alert_scene_source = "Gift Scene"


class TestFollower:
    """Follower dummy with the same attributes as a real one"""
    username = "NOBODY"


class TestSubscriber:
    """Subscriber dummy with the same attributes as a real one"""
    username = "NOBODY"
    amount_cents = 316


class TestRant:
    """Rant dummy with the same attributes as a real one"""
    class user:
        """User dummy sub"""
        username = "NOBODY"
    rant_price_cents = 316
    text = "Soli Deo gloria."


class TestRaid:
    """Raid dummy with the same attributes as a real one"""
    class user:
        """User dummy sub"""
        username = "NOBODY"


class TestGift:
    """Gift dummy with the same attributes as a real one"""
    class user:
        """User dummy sub"""
        username = "NOBODY"

    class gift_purchase_notification:
        """Gift purchase notification data dummy sub"""
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

        self.chat = cocorum.chatapi.ChatAPI(stream_id)
        self.chat.clear_mailbox()

        self.rant_queue = rant_queue
        self.raid_queue = raid_queue
        self.gift_queue = gift_queue

        # Thread-safe killswitch
        self.running = False

    def run(self):
        """The threaded code"""
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
        self.alerts_mutex = threading.Lock()
        self.api = None
        self.livestream = None
        self.chat_alert_receiver = None

        self.props = None
        self.scene_names_and_items = {}
        self.subscene_names = []
        self.source_names_to_types = {}

        # Inboxes of things waiting to be alerted for
        self.follower_inbox = Queue()
        self.subscriber_inbox = Queue()
        self.rant_inbox = Queue()
        self.raid_inbox = Queue()
        self.gift_inbox = Queue()

        # Base settings
        self.api_url = DefaultSettings.api_url
        self.refresh_rate = DefaultSettings.refresh_rate  # API refresh rate

        # Settings for the follower alert
        self.follower_alert_use = DefaultSettings.follower_alert_use
        self.follower_alert_time = DefaultSettings.follower_alert_time
        self.follower_alert_uname_source = DefaultSettings.follower_alert_uname_source
        self.follower_alert_scene_source = DefaultSettings.follower_alert_scene_source

        # Settings for the subscriber alert
        self.subscriber_alert_use = DefaultSettings.subscriber_alert_use
        self.subscriber_alert_time = DefaultSettings.subscriber_alert_time
        self.subscriber_alert_uname_source = DefaultSettings.subscriber_alert_uname_source
        self.subscriber_alert_amount_source = DefaultSettings.subscriber_alert_amount_source
        self.subscriber_alert_scene_source = DefaultSettings.subscriber_alert_scene_source

        # Settings for the rant alert
        self.rant_alert_use = DefaultSettings.rant_alert_use
        self.rant_alert_time = DefaultSettings.rant_alert_time
        self.rant_alert_uname_source = DefaultSettings.rant_alert_uname_source
        self.rant_alert_message_source = DefaultSettings.rant_alert_message_source
        self.rant_alert_amount_source = DefaultSettings.rant_alert_amount_source
        self.rant_alert_scene_source = DefaultSettings.rant_alert_scene_source

        # Settings for the raid alert
        self.raid_alert_use = DefaultSettings.raid_alert_use
        self.raid_alert_time = DefaultSettings.raid_alert_time
        self.raid_alert_uname_source = DefaultSettings.raid_alert_uname_source
        self.raid_alert_scene_source = DefaultSettings.raid_alert_scene_source

        # Settings for the gift alert
        self.gift_alert_use = DefaultSettings.gift_alert_use
        self.gift_alert_time = DefaultSettings.gift_alert_time
        self.gift_alert_uname_source = DefaultSettings.gift_alert_uname_source
        self.gift_alert_count_source = DefaultSettings.gift_alert_count_source
        #self.gift_alert_amount_source = DefaultSettings.gift_alert_amount_source
        self.gift_alert_scene_source = DefaultSettings.gift_alert_scene_source

    def script_defaults(self, settings):
        """Set OBS setting defaults"""
        print("Called script_defaults with settings", settings)
        # Base settings
        obs.obs_data_set_default_string(settings, "api_url", DefaultSettings.api_url)
        obs.obs_data_set_default_int(settings, "refresh_rate", DefaultSettings.refresh_rate)

        # Follower alert settings
        obs.obs_data_set_default_bool(settings, "follower_alert_use", DefaultSettings.follower_alert_use)
        obs.obs_data_set_default_int(settings, "follower_alert_time", DefaultSettings.follower_alert_time)
        obs.obs_data_set_default_string(settings, "follower_alert_uname_source", DefaultSettings.follower_alert_uname_source)
        obs.obs_data_set_default_string(settings, "follower_alert_scene_source", DefaultSettings.follower_alert_scene_source)

        # Subscriber alert settings
        obs.obs_data_set_default_bool(settings, "subscriber_alert_use", DefaultSettings.subscriber_alert_use)
        obs.obs_data_set_default_int(settings, "subscriber_alert_time", DefaultSettings.subscriber_alert_time)
        obs.obs_data_set_default_string(settings, "subscriber_alert_uname_source", DefaultSettings.subscriber_alert_uname_source)
        obs.obs_data_set_default_string(settings, "subscriber_alert_amount_source", DefaultSettings.subscriber_alert_amount_source)
        obs.obs_data_set_default_string(settings, "subscriber_alert_scene_source", DefaultSettings.subscriber_alert_scene_source)

        # Rant alert settings
        obs.obs_data_set_default_bool(settings, "rant_alert_use", DefaultSettings.rant_alert_use)
        obs.obs_data_set_default_int(settings, "rant_alert_time", DefaultSettings.rant_alert_time)
        obs.obs_data_set_default_string(settings, "rant_alert_uname_source", DefaultSettings.rant_alert_uname_source)
        obs.obs_data_set_default_string(settings, "rant_alert_message_source", DefaultSettings.rant_alert_message_source)
        obs.obs_data_set_default_string(settings, "rant_alert_amount_source", DefaultSettings.rant_alert_amount_source)
        obs.obs_data_set_default_string(settings, "rant_alert_scene_source", DefaultSettings.rant_alert_scene_source)

        # Raid alert settings
        obs.obs_data_set_default_bool(settings, "raid_alert_use", DefaultSettings.raid_alert_use)
        obs.obs_data_set_default_int(settings, "raid_alert_time", DefaultSettings.raid_alert_time)
        obs.obs_data_set_default_string(settings, "raid_alert_uname_source", DefaultSettings.raid_alert_uname_source)
        obs.obs_data_set_default_string(settings, "raid_alert_scene_source", DefaultSettings.raid_alert_scene_source)

        # Gift alert settings
        obs.obs_data_set_default_bool(settings, "gift_alert_use", DefaultSettings.gift_alert_use)
        obs.obs_data_set_default_int(settings, "gift_alert_time", DefaultSettings.gift_alert_time)
        obs.obs_data_set_default_string(settings, "gift_alert_uname_source", DefaultSettings.gift_alert_uname_source)
        obs.obs_data_set_default_string(settings, "gift_alert_count_source", DefaultSettings.gift_alert_count_source)
        #obs.obs_data_set_default_string(settings, "gift_alert_amount_source", DefaultSettings.gift_alert_amount_source)
        obs.obs_data_set_default_string(settings, "gift_alert_scene_source", DefaultSettings.gift_alert_scene_source)

        print("script_defaults done")

    def script_properties(self):
        """Set up the configuration properties for this script"""
        print("Setting up script properties")
        self.props = obs.obs_properties_create()
        self.get_scenes_and_sources()

        # Base settings
        obs.obs_properties_add_text(self.props, "base_settings_header", "--- Base Settings ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_text(self.props, "api_url", "API URL (with key)", obs.OBS_TEXT_PASSWORD)
        obs.obs_properties_add_int(self.props, "refresh_rate", "Refresh Rate (seconds)", REFRESH_RATE_MIN, REFRESH_RATE_MAX, 1)

        # Settings for the follower alert
        obs.obs_properties_add_text(self.props, "follower_alert_header", "\n--- Follower Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "follower_alert_use", "Use follower alert")
        obs.obs_properties_add_int(self.props, "follower_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        follower_scene_prop = obs.obs_properties_add_list(self.props, "follower_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_property_set_modified_callback(follower_scene_prop, update_follower_source_lists)
        follower_uname_prop = obs.obs_properties_add_list(self.props, "follower_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        # We have to bind the test button to a global callback instead of an instance method, because the OBS API is retarded
        obs.obs_properties_add_button(self.props, "follower_alert_test", "Queue fake follower", test_follower_alert)

        # Settings for the subscriber alert
        obs.obs_properties_add_text(self.props, "subscriber_alert_header", "\n--- Subscriber Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "subscriber_alert_use", "Use subscriber alert")
        obs.obs_properties_add_int(self.props, "subscriber_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        subscriber_scene_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_property_set_modified_callback(subscriber_scene_prop, update_subscriber_source_lists)
        subscriber_uname_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        subscriber_amount_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_properties_add_button(self.props, "subscriber_alert_test", "Queue fake subscriber", test_subscriber_alert)

        # Settings for the rant alert
        obs.obs_properties_add_text(self.props, "rant_alert_header", "\n--- Rant Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "rant_alert_use", "Use rant alert")
        obs.obs_properties_add_int(self.props, "rant_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        rant_scene_prop = obs.obs_properties_add_list(self.props, "rant_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        #obs.obs_property_set_modified_callback(rant_scene_prop, update_rant_source_lists)
        rant_uname_prop = obs.obs_properties_add_list(self.props, "rant_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_message_prop = obs.obs_properties_add_list(self.props, "rant_alert_message_source", "Message text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_amount_prop = obs.obs_properties_add_list(self.props, "rant_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_properties_add_button(self.props, "rant_alert_test", "Queue fake rant", test_rant_alert)

        # Settings for the raid alert
        obs.obs_properties_add_text(self.props, "raid_alert_header", "\n--- Raid Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "raid_alert_use", "Use raid alert")
        obs.obs_properties_add_int(self.props, "raid_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        raid_scene_prop = obs.obs_properties_add_list(self.props, "raid_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        #obs.obs_property_set_modified_callback(raid_scene_prop, update_raid_source_lists)
        raid_uname_prop = obs.obs_properties_add_list(self.props, "raid_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_properties_add_button(self.props, "raid_alert_test", "Queue fake raid", test_raid_alert)

        # Settings for the gift alert
        obs.obs_properties_add_text(self.props, "gift_alert_header", "\n--- Gift Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "gift_alert_use", "Use gift alert")
        obs.obs_properties_add_int(self.props, "gift_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        gift_scene_prop = obs.obs_properties_add_list(self.props, "gift_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        #obs.obs_property_set_modified_callback(gift_scene_prop, update_gift_source_lists)
        gift_uname_prop = obs.obs_properties_add_list(self.props, "gift_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        gift_count_prop = obs.obs_properties_add_list(self.props, "gift_alert_count_source", "Gift count text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        #gift_amount_prop = obs.obs_properties_add_list(self.props, "gift_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_properties_add_button(self.props, "gift_alert_test", "Queue fake gift", test_gift_alert)

        print("Adding all text display sources to the text display selectors")
        self.update_follower_source_lists(selected_scene=DefaultSettings.follower_alert_scene_source)
        for source_name, source_id in self.source_names_to_types.items():
            # Source is a text display, add it to text source selectors
            if source_id in ("text_gdiplus", "text_ft2_source"):
                #obs.obs_property_list_add_string(follower_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_amount_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_message_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_amount_prop, source_name, source_name)
                obs.obs_property_list_add_string(raid_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(gift_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(gift_count_prop, source_name, source_name)
                #obs.obs_property_list_add_string(gift_amount_prop, source_name, source_name)

        print("Adding all subscene sources to the subscene source selectors")
        for subscene_name in self.subscene_names:
            obs.obs_property_list_add_string(follower_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(subscriber_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(rant_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(raid_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(gift_scene_prop, subscene_name, subscene_name)

        print("Properties initialized.")
        return self.props

    def script_update(self, settings):
        """Update the script settings"""
        print("Updating with settings")
        # Base settings
        self.api_url = obs.obs_data_get_string(settings, "api_url")
        self.refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")

        # Settings for the follower alert
        self.follower_alert_use = obs.obs_data_get_bool(settings, "follower_alert_use")
        self.follower_alert_time = obs.obs_data_get_int(settings, "follower_alert_time")
        self.follower_alert_uname_source = obs.obs_data_get_string(settings, "follower_alert_uname_source")
        self.follower_alert_scene_source = obs.obs_data_get_string(settings, "follower_alert_scene_source")

        # Settings for the subscriber alert
        self.subscriber_alert_use = obs.obs_data_get_bool(settings, "subscriber_alert_use")
        self.subscriber_alert_time = obs.obs_data_get_int(settings, "subscriber_alert_time")
        self.subscriber_alert_uname_source = obs.obs_data_get_string(settings, "subscriber_alert_uname_source")
        self.subscriber_alert_amount_source = obs.obs_data_get_string(settings, "subscriber_alert_amount_source")
        self.subscriber_alert_scene_source = obs.obs_data_get_string(settings, "subscriber_alert_scene_source")

        # Settings for the rant alert
        self.rant_alert_use = obs.obs_data_get_bool(settings, "rant_alert_use")
        self.rant_alert_time = obs.obs_data_get_int(settings, "rant_alert_time")
        self.rant_alert_uname_source = obs.obs_data_get_string(settings, "rant_alert_uname_source")
        self.rant_alert_message_source = obs.obs_data_get_string(settings, "rant_alert_message_source")
        self.rant_alert_amount_source = obs.obs_data_get_string(settings, "rant_alert_amount_source")
        self.rant_alert_scene_source = obs.obs_data_get_string(settings, "rant_alert_scene_source")

        # Settings for the raid alert
        self.raid_alert_use = obs.obs_data_get_bool(settings, "raid_alert_use")
        self.raid_alert_time = obs.obs_data_get_int(settings, "raid_alert_time")
        self.raid_alert_uname_source = obs.obs_data_get_string(settings, "raid_alert_uname_source")
        self.raid_alert_scene_source = obs.obs_data_get_string(settings, "raid_alert_scene_source")

        # Settings for the gift alert
        self.gift_alert_use = obs.obs_data_get_bool(settings, "gift_alert_use")
        self.gift_alert_time = obs.obs_data_get_int(settings, "gift_alert_time")
        self.gift_alert_uname_source = obs.obs_data_get_string(settings, "gift_alert_uname_source")
        self.gift_alert_count_source = obs.obs_data_get_string(settings, "gift_alert_count_source")
        #self.gift_alert_amount_source = obs.obs_data_get_string(settings, "gift_alert_amount_source")
        self.gift_alert_scene_source = obs.obs_data_get_string(settings, "gift_alert_scene_source")

        # Deactivate timers and remove old livestream reference
        self.remove_obs_timers()
        self.livestream = None
        self.abandon_chat_alert_receiver()

        # We have an API URL
        if self.api_url:
            try:
                # We had no API before
                if not self.api:
                    print("Creating new Cocorum API object")
                    self.api = cocorum.RumbleAPI(self.api_url, refresh_rate=self.refresh_rate)

                # We do have an API but the URL is outdated
                elif self.api.api_url != self.api_url:
                    print("Updating Cocorum API URL")
                    self.api.api_url = self.api_url

            # The API URL was invalid
            except (AssertionError, cocorum.requests.exceptions.RequestException) as e:
                print(f"API connection failed: {e}")
                self.api_url = ""
                return

            # Reset livestream reference
            self.livestream = None
            self.abandon_chat_alert_receiver()

            # Clear these mailboxes
            print("Stale new followers: ", self.api.new_followers)
            print("Stale new subscribers: ", self.api.new_subscribers)

            self.set_obs_timers()

        print("Script settings updated.")

    def get_text_items(self, scene_name: str):
        """Pull up the records of all text type sources within a scene"""
        return [
                item_name
                for item_name in self.scene_names_and_items.get(scene_name, [])
                if self.source_names_to_types.get(item_name, "NULL_RECORD") in ("text_gdiplus", "text_ft2_source")
                ]

    def set_obs_timers(self):
        """Set all the timers we need in OBS"""
        print("Activating timers")
        if self.__obs_timers_set:
            print("ERROR: Timers already set.")
            return
        self.__obs_timers_set = True
        obs.timer_add(self.check_main_rls_api, self.refresh_rate * 1000)
        obs.timer_add(self.next_follower_alert, self.follower_alert_time * 1000)
        obs.timer_add(self.next_subscriber_alert, self.subscriber_alert_time * 1000)
        obs.timer_add(self.next_rant_alert, self.rant_alert_time * 1000)
        obs.timer_add(self.next_raid_alert, self.raid_alert_time * 1000)
        obs.timer_add(self.next_gift_alert, self.gift_alert_time * 1000)

    def remove_obs_timers(self):
        """Remove all the timers we would set for OBS"""
        print("Removing timers")
        if not self.__obs_timers_set:
            print("ERROR: Timers were not set.")
            return
        self.__obs_timers_set = False
        obs.timer_remove(self.check_main_rls_api)
        obs.timer_remove(self.next_follower_alert)
        obs.timer_remove(self.next_subscriber_alert)
        obs.timer_remove(self.next_rant_alert)
        obs.timer_remove(self.next_raid_alert)
        obs.timer_remove(self.next_gift_alert)

    def abandon_chat_alert_receiver(self):
        """If we have a chat alert receiver, tell it to stop, and remove its reference"""
        if self.chat_alert_receiver:
            self.chat_alert_receiver.running = False
            self.chat_alert_receiver = None

    def script_unload(self):
        """Perform script cleanup"""
        print("Unload triggered. Cleaning up")

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
            self.source_names_to_types = {obs.obs_source_get_name(s): obs.obs_source_get_unversioned_id(s) for s in sources}
            print("Releasing source list")
            obs.source_list_release(sources)
        else:
            print("No sources found.")

        print("Getting all scenes (as sources for some reason)")
        scene_sources = obs.obs_frontend_get_scenes()
        if scene_sources:
            print("Getting scene names")
            self.scene_names_and_items = {obs.obs_source_get_name(s): [] for s in scene_sources}
            print("Releasing scene sources list")
            obs.source_list_release(scene_sources)
        else:
            print("No scenes found.")

        print("Evaluating which scenes are subscenes")
        self.subscene_names = []
        for scene_name, item_names in self.scene_names_and_items.items():
            print(scene_name + ":")
            #print("\t(getting scene items)")
            scene = obs.obs_get_scene_by_name(scene_name)
            scene_items = obs.obs_scene_enum_items(scene)
            if scene_items:
                for item in scene_items:
                    # Get scene item as source and name
                    #print("\t(getting source of scene item)")
                    # Does not increment the reference, do not independently release
                    source = obs.obs_sceneitem_get_source(item)
                    #print("\t(getting source name)")
                    name = obs.obs_source_get_name(source)

                    # Make record that the item is in this scene
                    item_names.append(name)

                    # Is this item a subscene source?
                    #print("\t(identifying source type)")
                    # If this is not a subscene source, we will have a record of it already
                    unversioned_id = self.source_names_to_types.get(name) or obs.obs_source_get_unversioned_id(source)
                    if unversioned_id == "scene":
                        print(f"\t{unversioned_id}: {name} <--")
                        self.subscene_names.append(name)
                    else:
                        print(f"\t{unversioned_id}: {name}")
                    #print("\t(releasing that source)\n")
                    # obs.obs_source_release(source)

                #print("Releasing scene items list")
                obs.sceneitem_list_release(scene_items)
            else:
                print("\t--No items in this scene--")
            obs.obs_scene_release(scene)

    def set_text_by_source_name(self, source_name: str, new_value: str):
        """Sets the value of a text source"""

        source = obs.obs_get_source_by_name(source_name)
        if not source:
            print(f"ERROR: Could not set text for source '{source_name}': Source not found.")
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
        print("Checking main RLS API")
        # We have no API URL or it was invalid
        if not self.api_url:
            return

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
            self.follower_alert_scene_source,
            self.follower_inbox,
            self.follower_alert_use,
            lambda follower:
                self.set_text_by_source_name(
                    self.follower_alert_uname_source,
                    follower.username,
                    ),
                )

    def next_subscriber_alert(self):
        """Do the next subscriber alert, finishing up the last one"""
        self.__next_generic_alert(
            "subscriber",
            self.subscriber_alert_scene_source,
            self.subscriber_inbox,
            self.subscriber_alert_use,
            lambda subscriber:
                self.set_texts_by_source_names({
                    self.subscriber_alert_uname_source: subscriber.username,
                    self.subscriber_alert_amount_source: f"${subscriber.amount_cents / 100:.2f}",
                    })
                )

    def next_rant_alert(self):
        """Do the next rant alert, finishing up the last one"""
        self.__next_generic_alert(
            "rant",
            self.rant_alert_scene_source,
            self.rant_inbox,
            self.rant_alert_use,
            lambda rant:
                self.set_texts_by_source_names({
                    self.rant_alert_uname_source: rant.user.username,
                    self.rant_alert_message_source: rant.text,
                    self.rant_alert_amount_source: f"${rant.rant_price_cents / 100:.2f}",
                    })
                )

    def next_raid_alert(self):
        """Do the next raid alert, finishing up the last one"""
        self.__next_generic_alert(
            "raid",
            self.raid_alert_scene_source,
            self.raid_inbox,
            self.raid_alert_use,
            lambda raid:
                self.set_text_by_source_name(
                    self.raid_alert_uname_source,
                    raid.user.username,
                    ),
                )

    def next_gift_alert(self):
        """Do the next gift alert, finishing up the last one"""
        self.__next_generic_alert(
            "gift",
            self.gift_alert_scene_source,
            self.gift_inbox,
            self.gift_alert_use,
            lambda gift:
                self.set_texts_by_source_names({
                    self.gift_alert_uname_source: gift.user.username,
                    self.gift_alert_count_source: str(gift.gift_purchase_notification.total_gifts),
                    #self.gift_alert_amount_source: f"${gift.amount_cents / 100:.2f}",
                    }),
                )

    def __next_generic_alert(self, name: str, alert_scene_source: str, inbox: Queue, set_to_use: bool, config_alert_display: callable):
        """Do the next generic alert, finishing up the last one"""
        print(f"Doing {name} alert tick")

        current_scenesource = obs.obs_frontend_get_current_scene()  # returns obs_source_t

        # These do not increase the refcounter, release the above instead
        current_scene = obs.obs_scene_from_source(current_scenesource)
        subscene_sceneitem = obs.obs_scene_find_source(current_scene, alert_scene_source)

        try:
            if not subscene_sceneitem:
                print(f"Current scene '{obs.obs_source_get_name(current_scenesource)}' does not contain scene '{alert_scene_source}'")
                return

            # Finish up the last gift alert
            if obs.obs_sceneitem_visible(subscene_sceneitem):
                obs.obs_sceneitem_set_visible(subscene_sceneitem, False)
                self.alerts_mutex.release()
                print(f"Finished {name} alert.")

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
            obs.obs_source_release(current_scenesource)

    def update_follower_source_lists(self, props=None, prop=None, settings=None, selected_scene: str = None):
        """Filter available sources for follower alert displays"""
        return self.__update_alert_source_lists(
            "follower",
            ("follower_alert_uname_source",),
            settings=settings,
            selected_scene=selected_scene,
            )

    def update_subscriber_source_lists(self, props=None, prop=None, settings=None, selected_scene: str = None):
        """Filter available sources for subscriber alert displays"""
        return self.__update_alert_source_lists(
            "subscriber",
            (
                "subscriber_alert_uname_source",
                "subscriber_alert_amount_source",
                ),
            settings=settings,
            selected_scene=selected_scene,
            )

    def __update_alert_source_lists(self, name: str, sub_prop_names: iter, settings=None, selected_scene: str = None):
        """Filter available sources for named alert displays"""
        print(f"Updating {name} source lists")
        assert selected_scene or settings, "Must be able to know selected scene source"

        selected_scene = selected_scene or obs.obs_data_get_string(settings, f"{name}_alert_scene_source")

        if selected_scene not in self.scene_names_and_items:
            print(f"ERROR: Have no record of selected {name} scene '{selected_scene}'")
            return False

        # Allow for passing the sub property directly to avoid passing props
        sub_props_by_name = {
            prop_name:
            obs.obs_properties_get(self.props, prop_name)
            for prop_name in sub_prop_names
            }

        for sub_prop_name, sub_prop in sub_props_by_name.items():
            if not sub_prop:
                print(f"ERROR: Could not find a {name} alert property:", sub_prop_name)
                print("THIS SHOULD NEVER HAPPEN!\n")
                return False

            obs.obs_property_list_clear(sub_prop)
            for text_name in self.get_text_items(selected_scene):
                print(f"\t-{text_name}")
                obs.obs_property_list_add_string(sub_prop, text_name, text_name)

        return True

    def test_follower_alert(self, props, prop):
        """Test the follower alert button"""
        self.follower_inbox.put(TestFollower)
        print("Test follower queued.")
        return False

    def test_subscriber_alert(self, props, prop):
        """Test the subscriber alert button"""
        self.subscriber_inbox.put(TestSubscriber)
        print("Test subscriber queued.")
        return False

    def test_rant_alert(self, props, prop):
        """Test the rant alert button"""
        self.rant_inbox.put(TestRant)
        print("Test rant queued.")
        return False

    def test_raid_alert(self, props, prop):
        """Test the raid alert button"""
        self.raid_inbox.put(TestRaid)
        print("Test raid queued.")
        return False

    def test_gift_alert(self, props, prop):
        """Test the gift alert button"""
        self.gift_inbox.put(TestGift)
        print("Test gift queued.")
        return False


rla = OBSRumLiveAlerts()
print("RLA initialized.")


def update_follower_source_lists(props, prop, settings):
    """Filter available sources for follower alert displays (global wrapper for RLA instance)"""
    global rla
    return rla.update_follower_source_lists(props, prop, settings)


def update_subscriber_source_lists(props, prop, settings):
    """Filter available sources for subscriber alert displays (global wrapper for RLA instance)"""
    global rla
    return rla.update_subscriber_source_lists(props, prop, settings)


def test_follower_alert(props, prop):
    """Test the follower alert button (global wrapper for RLA instance)"""
    global rla
    return rla.test_follower_alert(props, prop)


def test_subscriber_alert(props, prop):
    """Test the subscriber alert button (global wrapper for RLA instance)"""
    global rla
    return rla.test_subscriber_alert(props, prop)


def test_rant_alert(props, prop):
    """Test the rant alert button (global wrapper for RLA instance)"""
    global rla
    return rla.test_rant_alert(props, prop)


def test_raid_alert(props, prop):
    """Test the raid alert button (global wrapper for RLA instance)"""
    global rla
    return rla.test_raid_alert(props, prop)


def test_gift_alert(props, prop):
    """Test the gift alert button (global wrapper for RLA instance)"""
    global rla
    return rla.test_gift_alert(props, prop)


script_properties = rla.script_properties
script_defaults = rla.script_defaults
script_update = rla.script_update
script_unload = rla.script_unload
