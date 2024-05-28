#!/usr/bin/env python3
"""Rumble Live Alerts OBS script

Live alerts for your Rumble livestream.
S.D.G."""

import os
import time
import obspython as obs
import cocorum

#API_URL_START = "https://rumble.com/-livestream-api/get-data?key="
MAX_ALERT_TIME = 6000 #Maximum for how long an alert can be displayed

class OBSRumLiveAlerts():
    """OBS Rumble live alerts system"""
    def __init__(self):
        """Instanced once within script as a reliable memory system"""
        self.api = None
        self.livestream = None

        self.props = None
        self.sources_by_name = {}
        self.scenes_by_name = {}
        self.scene_items_by_name = {}
        self.subscene_names = []
        self.current_scene_name = ""

        #Inboxes of things waiting to be alerted for
        self.follower_inbox = []
        self.subscriber_inbox = []
        self.rant_inbox = []

        #Base settings
        self.api_url = "" #Rumble Live Stream API URL
        self.refresh_rate = 10 #API refresh rate

        #Settings for the follower alert
        self.follower_alert_use = True
        self.follower_alert_time = 10
        self.follower_alert_uname_source = "Follower Username"
        self.follower_alert_scene_source = "Follower Scene"

        #Settings for the subscriber alert
        self.subscriber_alert_use = True
        self.subscriber_alert_time = 10
        self.subscriber_alert_uname_source = "Subscriber Username"
        self.subscriber_alert_amount_source = "Subscriber Amount Dollars"
        self.subscriber_alert_scene_source = "Subscriber Scene"

        #Settings for the rant alert
        self.rant_alert_use = True
        self.rant_alert_time = 10
        self.rant_alert_uname_source = "Rant Username"
        self.rant_alert_message_source = "Rant Message"
        self.rant_alert_amount_source = "Rant Amount Dollars"
        self.rant_alert_scene_source = "Rant Scene"

    def script_defaults(self, settings):
        """Reset all settings to their defaults"""
        #Base settings
        obs.obs_data_set_default_string(settings, "api_url", "")
        obs.obs_data_set_default_int(settings, "refresh_rate", self.refresh_rate)

        #Follower alert settings
        obs.obs_data_set_default_bool(settings, "follower_alert_use", self.follower_alert_use)
        obs.obs_data_set_default_int(settings, "follower_alert_time", self.follower_alert_time)
        obs.obs_data_set_default_string(settings, "follower_alert_uname_source", self.follower_alert_uname_source)
        obs.obs_data_set_default_string(settings, "follower_alert_scene_source", self.follower_alert_scene_source)

        #Subscriber alert settings
        obs.obs_data_set_default_bool(settings, "subscriber_alert_use", self.subscriber_alert_use)
        obs.obs_data_set_default_int(settings, "subscriber_alert_time", self.subscriber_alert_time)
        obs.obs_data_set_default_string(settings, "subscriber_alert_uname_source", self.subscriber_alert_uname_source)
        obs.obs_data_set_default_string(settings, "subscriber_alert_amount_source", self.subscriber_alert_amount_source)
        obs.obs_data_set_default_string(settings, "subscriber_alert_scene_source", self.subscriber_alert_scene_source)

        #Rant alert settings
        obs.obs_data_set_default_bool(settings, "rant_alert_use", self.rant_alert_use)
        obs.obs_data_set_default_int(settings, "rant_alert_time", self.rant_alert_time)
        obs.obs_data_set_default_string(settings, "rant_alert_uname_source", self.rant_alert_uname_source)
        obs.obs_data_set_default_string(settings, "rant_alert_message_source", self.rant_alert_message_source)
        obs.obs_data_set_default_string(settings, "rant_alert_amount_source", self.rant_alert_amount_source)
        obs.obs_data_set_default_string(settings, "rant_alert_scene_source", self.rant_alert_scene_source)

        print("Settings reset to default")

    def get_scenes_and_sources(self):
        """Get listing of OBS scenes and scene item sources"""
        #Release the old values
        obs.source_list_release(list(self.sources_by_name))
        for scene in self.scenes_by_name.values():
            obs.obs_scene_release(scene)
        for items in self.scene_items_by_name.values():
            for item in items.values():
                obs.obs_sceneitem_release(item)

        sources = obs.obs_enum_sources() #Sources that are not subscenes
        if sources is None:
            sources = []

        self.sources_by_name = {obs.obs_source_get_name(s) : s for s in sources}

        scene_sources = obs.obs_frontend_get_scenes()
        self.scenes_by_name = {obs.obs_source_get_name(s) : obs.obs_scene_from_source(s) for s in scene_sources}
        obs.source_list_release(scene_sources)
        self.scene_items_by_name = {}
        self.subscene_names = []
        for scene_name, scene in self.scenes_by_name.items():
            print(scene_name + ":")
            scene_items = obs.obs_scene_enum_items(scene)
            self.scene_items_by_name[scene_name] = {}
            if scene_items:
                for i in scene_items:
                    source = obs.obs_sceneitem_get_source(i)
                    name = obs.obs_source_get_name(source)
                    self.scene_items_by_name[scene_name][name] = i
                    unversioned_id = obs.obs_source_get_unversioned_id(source)
                    print("\t" + unversioned_id + ": " + name)
                    if unversioned_id == "scene":
                        self.subscene_names.append(name)
                    obs.obs_source_release(source)

    def script_properties(self):
        """Set up the configuration properties for this script"""
        self.props = obs.obs_properties_create()
        self.get_scenes_and_sources()

        #Base settings
        obs.obs_properties_add_text(self.props, "base_settings_header", "--- Base Settings ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_text(self.props, "api_url", "API URL (with key)", obs.OBS_TEXT_PASSWORD)
        obs.obs_properties_add_int(self.props, "refresh_rate", "Refresh Rate (seconds)", 10, 300, 1)

        #Settings for the follower alert
        obs.obs_properties_add_text(self.props, "follower_alert_header", "\n--- Follower Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "follower_alert_use", "Use follower alert")
        obs.obs_properties_add_int(self.props, "follower_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        follower_uname_prop = obs.obs_properties_add_list(self.props, "follower_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        follower_scene_prop = obs.obs_properties_add_list(self.props, "follower_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        #Settings for the subscriber alert
        obs.obs_properties_add_text(self.props, "subscriber_alert_header", "\n--- Subscriber Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "subscriber_alert_use", "Use subscriber alert")
        obs.obs_properties_add_int(self.props, "subscriber_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        subscriber_uname_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        subscriber_amount_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        subscriber_scene_prop = obs.obs_properties_add_list(self.props, "subscriber_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        #Settings for the rant alert
        obs.obs_properties_add_text(self.props, "rant_alert_header", "\n--- Rant Alert ---", obs.OBS_TEXT_INFO)
        obs.obs_properties_add_bool(self.props, "rant_alert_use", "Use rant alert")
        obs.obs_properties_add_int(self.props, "rant_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
        rant_uname_prop = obs.obs_properties_add_list(self.props, "rant_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_message_prop = obs.obs_properties_add_list(self.props, "rant_alert_message_source", "Message text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_amount_prop = obs.obs_properties_add_list(self.props, "rant_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
        rant_scene_prop = obs.obs_properties_add_list(self.props, "rant_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

        for source_name, source in self.sources_by_name.items():
            source_id = obs.obs_source_get_unversioned_id(source)

            #Source is a text display, add it to text source selectors
            if source_id in ("text_gdiplus", "text_ft2_source"):
                obs.obs_property_list_add_string(follower_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(subscriber_amount_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_uname_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_message_prop, source_name, source_name)
                obs.obs_property_list_add_string(rant_amount_prop, source_name, source_name)

        #Add all subscene sources to the subscene source selectors
        for subscene_name in self.subscene_names:
                obs.obs_property_list_add_string(follower_scene_prop, subscene_name, subscene_name)
                obs.obs_property_list_add_string(subscriber_scene_prop, subscene_name, subscene_name)
                obs.obs_property_list_add_string(rant_scene_prop, subscene_name, subscene_name)

        return self.props

    def script_update(self, settings):
        """Update the script settings"""
        #Base settings
        self.api_url = obs.obs_data_get_string(settings, "api_url")
        self.refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")

        #Settings for the follower alert
        self.follower_alert_use = obs.obs_data_get_bool(settings, "follower_alert_use")
        self.follower_alert_time = obs.obs_data_get_int(settings, "follower_alert_time")
        self.follower_alert_uname_source = obs.obs_data_get_string(settings, "follower_alert_uname_source")
        self.follower_alert_scene_source = obs.obs_data_get_string(settings, "follower_alert_scene_source")

        #Settings for the subscriber alert
        self.subscriber_alert_use = obs.obs_data_get_bool(settings, "subscriber_alert_use")
        self.subscriber_alert_time = obs.obs_data_get_int(settings, "subscriber_alert_time")
        self.subscriber_alert_uname_source = obs.obs_data_get_string(settings, "subscriber_alert_uname_source")
        self.subscriber_alert_amount_source = obs.obs_data_get_int(settings, "subscriber_alert_amount_source")
        self.subscriber_alert_scene_source = obs.obs_data_get_string(settings, "subscriber_alert_scene_source")

        #Settings for the rant alert
        self.rant_alert_use = obs.obs_data_get_bool(settings, "rant_alert_use")
        self.rant_alert_time = obs.obs_data_get_int(settings, "rant_alert_time")
        self.rant_alert_uname_source = obs.obs_data_get_string(settings, "rant_alert_uname_source")
        self.rant_alert_message_source = obs.obs_data_get_string(settings, "rant_alert_message_source")
        self.rant_alert_amount_source = obs.obs_data_get_int(settings, "rant_alert_amount_source")
        self.rant_alert_scene_source = obs.obs_data_get_string(settings, "rant_alert_scene_source")

        #Deactivate timers and delete the API object
        obs.timer_remove(self.refresh_alert_inboxes)
        obs.timer_remove(self.next_follower_alert)
        obs.timer_remove(self.next_subscriber_alert)
        obs.timer_remove(self.next_rant_alert)
        self.api = None
        self.livestream = None

        #We have an API URL, so activate timers
        if self.api_url:
            self.api = cocorum.RumbleAPI(self.api_url, refresh_rate = 0) #The refreshing happens on this side
            self.livestream = self.api.latest_livestream

            #Clear these mailboxes
            self.api.new_followers
            self.api.new_subscribers
            if self.livestream:
                self.livestream.chat.new_rants

            obs.timer_add(self.refresh_alert_inboxes, self.refresh_rate * 1000)
            obs.timer_add(self.next_follower_alert, self.follower_alert_time * 1000)
            obs.timer_add(self.next_subscriber_alert, self.subscriber_alert_time * 1000)
            obs.timer_add(self.next_rant_alert, self.rant_alert_time * 1000)

        print("Script settings updated.")

    def refresh_alert_inboxes(self):
        """Check if there are any new alertables and add them to the inboxes"""
        current_scene = obs.obs_frontend_get_current_scene()
        self.current_scene_name = obs.obs_source_get_name(current_scene)
        obs.obs_source_release(current_scene)

        self.follower_inbox += self.api.new_followers

        self.subscriber_inbox += self.api.new_subscribers

        #No livestream yet
        if not self.livestream:
            #Keep checking until we have a livestream
            self.livestream = self.api.latest_livestream
            return

        self.rant_inbox += self.livestream.chat.new_rants

    def next_follower_alert(self):
        """Do the next follower alert, finishing up the last one"""
        #No current scene gotten yet
        if not self.current_scene_name:
            return

        #Finish up the last follower alert
        subscene = self.scene_items_by_name[self.current_scene_name][self.follower_alert_scene_source]
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished follower alert.")

        #No new followers
        if not self.follower_inbox:
            return

        follower = self.follower_inbox.pop(0)
        print(f"New follower: {follower}")
        #There is no follower alert scene in the current scene
        if self.follower_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
            print("Follower scene not present in", self.current_scene_name)
            return

        #We are set to not do follower alerts
        if not self.follower_alert_use:
            print("Follower alerts are disabled.")
            return

        #Set the text
        print("Setting text...")
        f_uname_set = obs.obs_data_create()
        obs.obs_data_set_string(f_uname_set, "text", follower.username)
        obs.obs_source_update(self.sources_by_name[self.follower_alert_uname_source], f_uname_set)
        obs.obs_data_release(f_uname_set)

        #Show the alert
        print("Showing alert...")
        obs.obs_sceneitem_set_visible(subscene, True)

        #Wait for alert to finish hide transition as well (DOES NOT WORK)
        #print("Waiting for hide transition...")
        #time.sleep(obs.obs_sceneitem_get_hide_transition_duration(subscene) / 1000)

    def next_subscriber_alert(self):
        """Do the next subscriber alert, finishing up the last one"""
        #No current scene gotten yet
        if not self.current_scene_name:
            return

        #Finish up the last subscriber alert
        subscene = self.scene_items_by_name[self.current_scene_name][self.subscriber_alert_scene_source]
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished subscriber alert.")

        #No new subscribers
        if not self.subscriber_inbox:
            return

        subscriber = self.subscriber_inbox.pop(0)
        print(f"New subscriber: {subscriber}")
        #There is no subscriber alert scene in the current scene
        if self.subscriber_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
            print("Subscriber scene not present in", self.current_scene_name)
            return

        #We are set to not do subscriber alerts
        if not self.subscriber_alert_use:
            print("Subscriber alerts are disabled.")
            return

        #Set the userame text
        s_uname_set = obs.obs_data_create()
        obs.obs_data_set_string(s_uname_set, "text", subscriber.username)
        obs.obs_source_update(self.sources_by_name[self.subscriber_alert_uname_source], s_uname_set)
        obs.obs_data_release(s_uname_set)

        #Set the amount text
        s_amount_set = obs.obs_data_create()
        obs.obs_data_set_string(s_amount_set, "text", f"${subscriber.amount_cents:.2}")
        obs.obs_source_update(self.sources_by_name[self.subscriber_alert_amount_source], s_amount_set)
        obs.obs_data_release(s_amount_set)

        #Show the alert
        subscene = self.scene_items_by_name[self.current_scene_name][self.subscriber_alert_scene_source]
        obs.obs_sceneitem_set_visible(subscene, True)

    def next_rant_alert(self):
        """Do the next rant alert, finishing up the last one"""
        #No current scene gotten yet
        if not self.current_scene_name:
            return

        #Finish up the last rant alert
        subscene = self.scene_items_by_name[self.current_scene_name][self.rant_alert_scene_source]
        if obs.obs_sceneitem_visible(subscene):
            obs.obs_sceneitem_set_visible(subscene, False)
            print("Finished rant alert.")

        #No new rants
        if not self.rant_inbox:
            return

        rant = self.rant_inbox.pop(0)
        print(f"New rant: {rant}")
        #There is no rant alert scene in the current scene
        if self.rant_alert_scene_source not in self.scene_items_by_name[self.current_scene_name]:
            print("Rant scene not present in", self.current_scene_name)
            return

        #We are set to not do rant alerts
        if not self.rant_alert_use:
            print("Rant alerts are disabled.")
            return

        #Set the userame text
        r_uname_set = obs.obs_data_create()
        obs.obs_data_set_string(r_uname_set, "text", rant.username)
        obs.obs_source_update(self.sources_by_name[self.rant_alert_uname_source], r_uname_set)
        obs.obs_data_release(r_uname_set)

        #Set the message text
        r_message_set = obs.obs_data_create()
        obs.obs_data_set_string(r_message_set, "text", rant.text)
        obs.obs_source_update(self.sources_by_name[self.rant_alert_message_source], r_message_set)
        obs.obs_data_release(r_message_set)

        #Set the amount text
        r_amount_set = obs.obs_data_create()
        obs.obs_data_set_string(r_amount_set, "text", f"${rant.amount_cents:.2}")
        obs.obs_source_update(self.sources_by_name[self.rant_alert_amount_source], r_amount_set)
        obs.obs_data_release(r_amount_set)

        #Show the alert
        subscene = self.scene_items_by_name[self.current_scene_name][self.rant_alert_scene_source]
        obs.obs_sceneitem_set_visible(subscene, True)

rla = OBSRumLiveAlerts()
script_properties = rla.script_properties
script_defaults = rla.script_defaults
script_update = rla.script_update
