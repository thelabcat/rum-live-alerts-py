#!/usr/bin/env python3
"""Rumble Live Alerts OBS script

Live alerts for your Rumble livestream.
S.D.G."""

from queue import Queue, Empty as QueueEmpty
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


class OBSRumLiveAlerts():
    """OBS Rumble live alerts system"""

    def __init__(self):
        """Instanced once within script as a reliable memory system"""
        print("Initializing OBSRumLiveAlerts object")
        self.__obs_timers_set = False
        self.api = None
        self.livestream = None

        self.props = None
        self.scene_names = []
        self.subscene_names = []
        self.source_names_and_types = {}
        self.current_scene_name = ""

        # Inboxes of things waiting to be alerted for
        self.follower_inbox = Queue()
        self.subscriber_inbox = Queue()
        self.rant_inbox = Queue()

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

        print("script_defaults done")

    def set_obs_timers(self):
        """Set all the timers we need in OBS"""
        print("Activating timers")
        if self.__obs_timers_set:
            print("ERROR: Timers already set.")
            return
        self.__obs_timers_set = True
        obs.timer_add(self.refresh_alert_inboxes, self.refresh_rate * 1000)
        obs.timer_add(self.next_follower_alert, self.follower_alert_time * 1000)
        obs.timer_add(self.next_subscriber_alert, self.subscriber_alert_time * 1000)
        obs.timer_add(self.next_rant_alert, self.rant_alert_time * 1000)

    def remove_obs_timers(self):
        """Remove all the timers we would set for OBS"""
        print("Removing timers")
        if not self.__obs_timers_set:
            print("ERROR: Timers were not set.")
            return
        self.__obs_timers_set = False
        obs.timer_remove(self.refresh_alert_inboxes)
        obs.timer_remove(self.next_follower_alert)
        obs.timer_remove(self.next_subscriber_alert)
        obs.timer_remove(self.next_rant_alert)

    def script_unload(self):
        """Perform script cleanup"""
        print("Unload triggered. Cleaning up")

        # Deactivate timers and remove old livestream reference
        self.remove_obs_timers()
        self.livestream = None
        print("Unloaded.")

    def get_scenes_and_sources(self):
        """Get listing of OBS scenes and scene item sources"""
        print("Getting scenes and sources...")

        print("Enumerating non-subscene sources")
        # Sources that are not subscenes
        sources = obs.obs_enum_sources()
        if sources:
            print("Getting non-subscene source names")
            self.source_names_and_types = {obs.obs_source_get_name(s): obs.obs_source_get_unversioned_id(s) for s in sources}
            print("Releasing source list")
            obs.source_list_release(sources)
        else:
            print("No sources found.")

        print("Getting all scenes (as sources for some reason)")
        scene_sources = obs.obs_frontend_get_scenes()
        if scene_sources:
            print("Getting scene names")
            self.scene_names = [obs.obs_source_get_name(s) for s in scene_sources]
            print("Releasing scene sources list")
            obs.source_list_release(scene_sources)
        else:
            print("No scenes found.")

        print("Evaluating which scenes are subscenes")
        self.subscene_names = []
        for scene_name in self.scene_names:
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

                    # Is this item a subscene source?
                    #print("\t(identifying source type)")
                    # If this is not a subscene source, we will have a record of it already
                    unversioned_id = self.source_names_and_types.get(name) or obs.obs_source_get_unversioned_id(source)
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
        follower_uname_prop = obs.obs_properties_add_list(self.props, "follower_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        follower_scene_prop = obs.obs_properties_add_list(self.props, "follower_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        # Settings for the subscriber alert
        obs.obs_properties_add_text(self.props, "subscriber_alert_header", "\n--- Subscriber Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "subscriber_alert_use", "Use subscriber alert")
        obs.obs_properties_add_int(self.props, "subscriber_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        subscriber_uname_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        subscriber_amount_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        subscriber_scene_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        # Settings for the rant alert
        obs.obs_properties_add_text(self.props, "rant_alert_header", "\n--- Rant Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "rant_alert_use", "Use rant alert")
        obs.obs_properties_add_int(self.props, "rant_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        rant_uname_prop = obs.obs_properties_add_list(self.props, "rant_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_message_prop = obs.obs_properties_add_list(self.props, "rant_alert_message_source", "Message text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_amount_prop = obs.obs_properties_add_list(self.props, "rant_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_scene_prop = obs.obs_properties_add_list(self.props, "rant_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        print("Adding all text display sources to the text display selectors")
        for source_name, source_id in self.source_names_and_types.items():
            # Source is a text display, add it to text source selectors
            if source_id in ("text_gdiplus", "text_ft2_source"):
                obs.obs_property_list_add_string(follower_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_amount_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_message_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_amount_prop, source_name, source_name)

        print("Adding all subscene sources to the subscene source selectors")
        for subscene_name in self.subscene_names:
            obs.obs_property_list_add_string(follower_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(subscriber_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(rant_scene_prop, subscene_name, subscene_name)

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

        # Deactivate timers and remove old livestream reference
        self.remove_obs_timers()
        self.livestream = None

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

            self.livestream = self.api.latest_livestream

            # Clear these mailboxes
            print("Stale new followers: ", self.api.new_followers)
            print("Stale new subscribers: ", self.api.new_subscribers)
            if self.livestream:
                print("Stale new rants: ", self.livestream.chat.new_rants)

            self.set_obs_timers()

        print("Script settings updated.")

    def refresh_alert_inboxes(self):
        """Check if there are any new alertables and add them to the inboxes"""
        # We have no API URL or it was invalid
        if not self.api_url:
            return

        current_scene = obs.obs_frontend_get_current_scene()
        self.current_scene_name = obs.obs_source_get_name(current_scene)
        obs.obs_source_release(current_scene)

        for new_follower in self.api.new_followers:
            self.follower_inbox.put(new_follower)

        for new_subscriber in self.api.new_subscribers:
            self.subscriber_inbox.put(new_subscriber)

        # No livestream yet
        if not self.livestream:
            # Keep checking until we have a livestream
            self.livestream = self.api.latest_livestream
            return

        # There is a livestream, so it may have new rants
        for new_rant in self.livestream.chat.new_rants:
            self.rant_inbox.put(new_rant)

    def next_follower_alert(self):
        """Do the next follower alert, finishing up the last one"""
        # No current scene gotten yet
        if not self.current_scene_name:
            return

        try:
            # current_scene = obs.obs_get_scene_by_name(self.current_scene_name)
            subscene = obs.obs_get_source_by_name(self.follower_alert_scene_source)

        except KeyError:  # Scene selection or scene items table is invalid
            return

        # Finish up the last follower alert
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished follower alert.")

        # Check for a new follower
        try:
            follower = self.follower_inbox.get_nowait()

        # If there is none, exit
        except QueueEmpty:
            obs.obs_source_release(subscene)
            return

        print(f"New follower: {follower}")
        # There is no follower alert scene in the current scene
        # Do we even need to check this?
        #if self.follower_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
        #    print("Follower scene not present in", self.current_scene_name)
        #    return

        # We are set to not do follower alerts
        if not self.follower_alert_use:
            print("Follower alerts are disabled.")
            obs.obs_source_release(subscene)
            return

        # Set the text
        print("Setting text")
        f_uname_set = obs.obs_data_create()
        f_uname_source = obs.obs_get_source_by_name(self.follower_alert_uname_source)

        obs.obs_data_set_string(f_uname_set, "text", follower.username)
        obs.obs_source_update(f_uname_source, f_uname_set)

        obs.obs_data_release(f_uname_set)
        obs.obs_source_release(f_uname_source)

        # Show the alert
        print("Showing alert")
        obs.obs_sceneitem_set_visible(subscene, True)
        obs.obs_source_release(subscene)

        # Wait for alert to finish hide transition as well (DOES NOT WORK)
        # print("Waiting for hide transition")
        # time.sleep(obs.obs_sceneitem_get_hide_transition_duration(subscene) / 1000)

    def next_subscriber_alert(self):
        """Do the next subscriber alert, finishing up the last one"""
        # No current scene gotten yet
        if not self.current_scene_name:
            return

        try:
            # current_scene = obs.obs_get_scene_by_name(self.current_scene_name)
            subscene = obs.obs_get_source_by_name(self.follower_alert_scene_source)
        except KeyError:  # Scene selection or scene items table is invalid
            return

        # Finish up the last subscriber alert
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished subscriber alert.")

        # Check for a new subscriber
        try:
            subscriber = self.subscriber_inbox.get_nowait()

        # If there is none, exit
        except QueueEmpty:
            obs.obs_source_release(subscene)
            return

        print(f"New subscriber: {subscriber}")
        # There is no subscriber alert scene in the current scene
        # if self.subscriber_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
        #     print("Subscriber scene not present in", self.current_scene_name)
        #     return

        # We are set to not do subscriber alerts
        if not self.subscriber_alert_use:
            print("Subscriber alerts are disabled.")
            obs.obs_source_release(subscene)
            return

        # Set the userame text
        s_uname_set = obs.obs_data_create()
        s_uname_source = obs.obs_get_source_by_name(self.subscriber_alert_uname_source)

        obs.obs_data_set_string(s_uname_set, "text", subscriber.username)
        obs.obs_source_update(s_uname_source, s_uname_set)

        obs.obs_data_release(s_uname_set)
        obs.obs_source_release(s_uname_source)

        # Set the amount text
        s_amount_set = obs.obs_data_create()
        s_amount_source = obs.obs_get_source_by_name(self.subscriber_alert_amount_source)

        obs.obs_data_set_string(s_amount_set, "text", f"${subscriber.amount_cents:.2f}")
        obs.obs_source_update(s_amount_source, s_amount_set)

        obs.obs_data_release(s_amount_set)
        obs.obs_source_release(s_amount_source)

        # Show the alert
        obs.obs_sceneitem_set_visible(subscene, True)
        obs.obs_source_release(subscene)

    def next_rant_alert(self):
        """Do the next rant alert, finishing up the last one"""
        # No current scene gotten yet
        if not self.current_scene_name:
            return

        try:
            # current_scene = obs.obs_get_scene_by_name(self.current_scene_name)
            subscene = obs.obs_get_source_by_name(self.follower_alert_scene_source)
        except KeyError:  # Scene selection or scene items table is invalid
            return

        # Finish up the last rant alert
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished rant alert.")

        # Check for a new rant
        try:
            rant = self.rant_inbox.get_nowait()
        # If there is none, exit
        except QueueEmpty:
            obs.obs_source_release(subscene)
            return

        print(f"New rant: {rant}")
        # There is no rant alert scene in the current scene
        # if self.rant_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
        #     print("Rant scene not present in", self.current_scene_name)
        #     return

        # We are set to not do rant alerts
        if not self.rant_alert_use:
            print("Rant alerts are disabled.")
            obs.obs_source_release(subscene)
            return

        # Set the userame text
        r_uname_set = obs.obs_data_create()
        r_uname_source = obs.obs_get_source_by_name(self.rant_alert_uname_source)

        obs.obs_data_set_string(r_uname_set, "text", rant.username)
        obs.obs_source_update(r_uname_source, r_uname_set)

        obs.obs_data_release(r_uname_set)
        obs.obs_source_release(r_uname_source)

        # Set the message text
        r_message_set = obs.obs_data_create()
        r_message_source = obs.obs_get_source_by_name(self.rant_alert_message_source)

        obs.obs_data_set_string(r_message_set, "text", rant.text)
        obs.obs_source_update(r_message_source, r_message_set)

        obs.obs_data_release(r_message_set)
        obs.obs_source_release(r_message_source)

        # Set the amount text
        r_amount_set = obs.obs_data_create()
        r_amount_source = obs.obs_get_source_by_name(self.rant_alert_amount_source)

        obs.obs_data_set_string(r_amount_set, "text", f"${rant.amount_cents:.2}")
        obs.obs_source_update(r_amount_source, r_amount_set)

        obs.obs_data_release(r_amount_set)
        obs.obs_source_release(r_amount_source)

        # Show the alert
        obs.obs_sceneitem_set_visible(subscene, True)
        obs.obs_source_release(subscene)


rla = OBSRumLiveAlerts()
print("RLA initialized.")

script_properties = rla.script_properties
script_defaults = rla.script_defaults
script_update = rla.script_update
script_unload = rla.script_unload
