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

#Base settings
API_URL_DEFAULT = "" #Rumble Live Stream API URL
REFRESH_RATE_DEFAULT = 10 #API refresh rate

#Settings for the follower alert
FOLLOWER_ALERT_USE_DEFAULT = True
FOLLOWER_ALERT_TIME_DEFAULT = 10
FOLLOWER_ALERT_UNAME_SOURCE_DEFAULT = "Follower Username"
FOLLOWER_ALERT_SCENE_SOURCE_DEFAULT = "Follower Scene"

#Settings for the subscriber alert
SUBSCRIBER_ALERT_USE_DEFAULT = True
SUBSCRIBER_ALERT_TIME_DEFAULT = 10
SUBSCRIBER_ALERT_UNAME_SOURCE_DEFAULT = "Subscriber Username"
SUBSCRIBER_ALERT_AMOUNT_SOURCE_DEFAULT = "Subscriber Amount Dollars"
SUBSCRIBER_ALERT_SCENE_SOURCE_DEFAULT = "Subscriber Scene"

#Settings for the rant alert
RANT_ALERT_USE_DEFAULT = True
RANT_ALERT_TIME_DEFAULT = 10
RANT_ALERT_UNAME_SOURCE_DEFAULT = "Rant Username"
RANT_ALERT_MESSAGE_SOURCE_DEFAULT = "Rant Message"
RANT_ALERT_AMOUNT_SOURCE_DEFAULT = "Rant Amount Dollars"
RANT_ALERT_SCENE_SOURCE_DEFAULT = "Rant Scene"

api = None
livestream = None

props = None
sources_by_name = {}
scenes_by_name = {}
scene_items_by_name = {}
subscene_names = []
current_scene_name = ""

#Inboxes of things waiting to be alerted for
follower_inbox = []
subscriber_inbox = []
rant_inbox = []

#Base settings
api_url = API_URL_DEFAULT
refresh_rate = REFRESH_RATE_DEFAULT

#Settings for the follower alert
follower_alert_use = FOLLOWER_ALERT_USE_DEFAULT
follower_alert_time = FOLLOWER_ALERT_TIME_DEFAULT
follower_alert_uname_source = FOLLOWER_ALERT_UNAME_SOURCE_DEFAULT
follower_alert_scene_source = FOLLOWER_ALERT_SCENE_SOURCE_DEFAULT

#Settings for the subscriber alert
subscriber_alert_use = SUBSCRIBER_ALERT_USE_DEFAULT
subscriber_alert_time = SUBSCRIBER_ALERT_TIME_DEFAULT
subscriber_alert_uname_source = SUBSCRIBER_ALERT_UNAME_SOURCE_DEFAULT
subscriber_alert_amount_source = SUBSCRIBER_ALERT_AMOUNT_SOURCE_DEFAULT
subscriber_alert_scene_source = SUBSCRIBER_ALERT_SCENE_SOURCE_DEFAULT

#Settings for the rant alert
rant_alert_use = RANT_ALERT_USE_DEFAULT
rant_alert_time = RANT_ALERT_TIME_DEFAULT
rant_alert_uname_source = RANT_ALERT_UNAME_SOURCE_DEFAULT
rant_alert_message_source = RANT_ALERT_MESSAGE_SOURCE_DEFAULT
rant_alert_amount_source = RANT_ALERT_AMOUNT_SOURCE_DEFAULT
rant_alert_scene_source = RANT_ALERT_SCENE_SOURCE_DEFAULT

def script_defaults(settings):
    """Reset all settings to their defaults"""
    #Base settings
    obs.obs_data_set_default_string(settings, "api_url", API_URL_DEFAULT)
    obs.obs_data_set_default_int(settings, "refresh_rate", REFRESH_RATE_DEFAULT)

    #Follower alert settings
    obs.obs_data_set_default_bool(settings, "follower_alert_use", FOLLOWER_ALERT_USE_DEFAULT)
    obs.obs_data_set_default_int(settings, "follower_alert_time", FOLLOWER_ALERT_TIME_DEFAULT)
    obs.obs_data_set_default_string(settings, "follower_alert_uname_source", FOLLOWER_ALERT_UNAME_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "follower_alert_scene_source", FOLLOWER_ALERT_SCENE_SOURCE_DEFAULT)

    #Subscriber alert settings
    obs.obs_data_set_default_bool(settings, "subscriber_alert_use", SUBSCRIBER_ALERT_USE_DEFAULT)
    obs.obs_data_set_default_int(settings, "subscriber_alert_time", SUBSCRIBER_ALERT_TIME_DEFAULT)
    obs.obs_data_set_default_string(settings, "subscriber_alert_uname_source", SUBSCRIBER_ALERT_UNAME_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "subscriber_alert_amount_source", SUBSCRIBER_ALERT_AMOUNT_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "subscriber_alert_scene_source", SUBSCRIBER_ALERT_SCENE_SOURCE_DEFAULT)

    #Rant alert settings
    obs.obs_data_set_default_bool(settings, "rant_alert_use", RANT_ALERT_USE_DEFAULT)
    obs.obs_data_set_default_int(settings, "rant_alert_time", RANT_ALERT_TIME_DEFAULT)
    obs.obs_data_set_default_string(settings, "rant_alert_uname_source", RANT_ALERT_UNAME_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "rant_alert_message_source", RANT_ALERT_MESSAGE_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "rant_alert_amount_source", RANT_ALERT_AMOUNT_SOURCE_DEFAULT)
    obs.obs_data_set_default_string(settings, "rant_alert_scene_source", RANT_ALERT_SCENE_SOURCE_DEFAULT)

    print("Settings reset to default")

def script_unload():
    """Perform script cleanup"""
    print("Unload triggered. Cleaning up.")
    global api
    global livestream

    #Erase OBS-linked data
    release_old_sns_data()

    #Deactivate timers and remove old livestream reference
    obs.timer_remove(refresh_alert_inboxes)
    obs.timer_remove(next_follower_alert)
    obs.timer_remove(next_subscriber_alert)
    obs.timer_remove(next_rant_alert)
    livestream = None
    api = None
    print("Cleaned up.")

def release_old_sns_data():
    """Release and erase old scenes and sources data"""
    print("Releasing old OBS scenes and sources data")
    global sources_by_name
    global scenes_by_name
    global scene_items_by_name
    obs.source_list_release(list(sources_by_name.values()))
    sources_by_name = {}
    for scene in scenes_by_name.values():
        obs.obs_scene_release(scene)
    scenes_by_name = {}

    released_items = []
    for items in scene_items_by_name.values():
        for name, item in items.items():
            #Ensure we do not release an item twice
            if name not in released_items:
                obs.obs_sceneitem_release(item)
                released_items.append(name)

    scene_items_by_name = {}
    print("Released.")

def get_scenes_and_sources():
    """Get listing of OBS scenes and scene item sources"""
    print("Getting scenes and sources...")
    global sources_by_name
    global scenes_by_name
    global scene_items_by_name
    global subscene_names

    #Release the old values
    release_old_sns_data()

    sources = obs.obs_enum_sources() #Sources that are not subscenes
    if sources is None:
        sources = []

    sources_by_name = {obs.obs_source_get_name(s) : s for s in sources}

    scene_sources = obs.obs_frontend_get_scenes()
    scenes_by_name = {obs.obs_source_get_name(s) : obs.obs_scene_from_source(s) for s in scene_sources}
    obs.source_list_release(scene_sources)
    subscene_names = []
    for scene_name, scene in scenes_by_name.items():
        print(scene_name + ":")
        scene_items = obs.obs_scene_enum_items(scene)
        scene_items_by_name[scene_name] = {}
        if scene_items:
            for i in scene_items:
                source = obs.obs_sceneitem_get_source(i)
                name = obs.obs_source_get_name(source)
                scene_items_by_name[scene_name][name] = i
                unversioned_id = obs.obs_source_get_unversioned_id(source)
                print("\t" + unversioned_id + ": " + name)
                if unversioned_id == "scene":
                    subscene_names.append(name)
                obs.obs_source_release(source)
    print("Got all scenes and sources.")

def script_properties():
    """Set up the configuration properties for this script"""
    print("Properties initializing...")
    props = obs.obs_properties_create()
    get_scenes_and_sources()

    #Base settings
    obs.obs_properties_add_text(props, "base_settings_header", "--- Base Settings ---", obs.OBS_TEXT_INFO)
    obs.obs_properties_add_text(props, "api_url", "API URL (with key)", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_int(props, "refresh_rate", "Refresh Rate (seconds)", 10, 300, 1)

    #Settings for the follower alert
    obs.obs_properties_add_text(props, "follower_alert_header", "\n--- Follower Alert ---", obs.OBS_TEXT_INFO)
    obs.obs_properties_add_bool(props, "follower_alert_use", "Use follower alert")
    obs.obs_properties_add_int(props, "follower_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
    follower_uname_prop = obs.obs_properties_add_list(props, "follower_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    follower_scene_prop = obs.obs_properties_add_list(props, "follower_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

    #Settings for the subscriber alert
    obs.obs_properties_add_text(props, "subscriber_alert_header", "\n--- Subscriber Alert ---", obs.OBS_TEXT_INFO)
    obs.obs_properties_add_bool(props, "subscriber_alert_use", "Use subscriber alert")
    obs.obs_properties_add_int(props, "subscriber_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
    subscriber_uname_prop = obs.obs_properties_add_list(props, "subscriber_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    subscriber_amount_prop = obs.obs_properties_add_list(props, "subscriber_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    subscriber_scene_prop = obs.obs_properties_add_list(props, "subscriber_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

    #Settings for the rant alert
    obs.obs_properties_add_text(props, "rant_alert_header", "\n--- Rant Alert ---", obs.OBS_TEXT_INFO)
    obs.obs_properties_add_bool(props, "rant_alert_use", "Use rant alert")
    obs.obs_properties_add_int(props, "rant_alert_time", "Display for seconds", 0, MAX_ALERT_TIME, 1)
    rant_uname_prop = obs.obs_properties_add_list(props, "rant_alert_uname_source", "Username text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    rant_message_prop = obs.obs_properties_add_list(props, "rant_alert_message_source", "Message text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    rant_amount_prop = obs.obs_properties_add_list(props, "rant_alert_amount_source", "Amount (dollars) text source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    rant_scene_prop = obs.obs_properties_add_list(props, "rant_alert_scene_source", "Scene source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)

    for source_name, source in sources_by_name.items():
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
    for subscene_name in subscene_names:
            obs.obs_property_list_add_string(follower_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(subscriber_scene_prop, subscene_name, subscene_name)
            obs.obs_property_list_add_string(rant_scene_prop, subscene_name, subscene_name)

    print("Initialized properties.")
    return props

def script_update(settings):
    """Update the script settings"""
    print("Updating settings...")

    #Base settings
    global api_url
    global refresh_rate

    #Settings for the follower alert
    global follower_alert_use
    global follower_alert_time
    global follower_alert_uname_source
    global follower_alert_scene_source

    #Settings for the subscriber alert
    global subscriber_alert_use
    global subscriber_alert_time
    global subscriber_alert_uname_source
    global subscriber_alert_amount_source
    global subscriber_alert_scene_source

    #Settings for the rant alert
    global rant_alert_use
    global rant_alert_time
    global rant_alert_uname_source
    global rant_alert_message_source
    global rant_alert_amount_source
    global rant_alert_scene_source

    global livestream
    global api_url
    global api

    print("Settings variables all accessed...")

    #Base settings
    api_url = obs.obs_data_get_string(settings, "api_url")
    refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")

    #Settings for the follower alert
    follower_alert_use = obs.obs_data_get_bool(settings, "follower_alert_use")
    follower_alert_time = obs.obs_data_get_int(settings, "follower_alert_time")
    follower_alert_uname_source = obs.obs_data_get_string(settings, "follower_alert_uname_source")
    follower_alert_scene_source = obs.obs_data_get_string(settings, "follower_alert_scene_source")

    #Settings for the subscriber alert
    subscriber_alert_use = obs.obs_data_get_bool(settings, "subscriber_alert_use")
    subscriber_alert_time = obs.obs_data_get_int(settings, "subscriber_alert_time")
    subscriber_alert_uname_source = obs.obs_data_get_string(settings, "subscriber_alert_uname_source")
    subscriber_alert_amount_source = obs.obs_data_get_int(settings, "subscriber_alert_amount_source")
    subscriber_alert_scene_source = obs.obs_data_get_string(settings, "subscriber_alert_scene_source")

    #Settings for the rant alert
    rant_alert_use = obs.obs_data_get_bool(settings, "rant_alert_use")
    rant_alert_time = obs.obs_data_get_int(settings, "rant_alert_time")
    rant_alert_uname_source = obs.obs_data_get_string(settings, "rant_alert_uname_source")
    rant_alert_message_source = obs.obs_data_get_string(settings, "rant_alert_message_source")
    rant_alert_amount_source = obs.obs_data_get_int(settings, "rant_alert_amount_source")
    rant_alert_scene_source = obs.obs_data_get_string(settings, "rant_alert_scene_source")

    print("Settings loaded from properties...")

    #Deactivate timers and remove old livestream reference
    obs.timer_remove(refresh_alert_inboxes)
    obs.timer_remove(next_follower_alert)
    obs.timer_remove(next_subscriber_alert)
    obs.timer_remove(next_rant_alert)
    livestream = None

    print("Old timers removed...")

    #We have an API URL
    if api_url:
        print("API URL set, so activating API...")
        try:
            #We had no API before
            if not api:
                print("No API object yet, creating new one...")
                api = cocorum.RumbleAPI(api_url, refresh_rate = refresh_rate - 0.5)

            #We do have an API but the URL is outdated
            elif api.api_url != api_url:
                print("API exists but URL is out of date, updating...")
                api.api_url = api_url

            #The API URL has not changed
            else:
                print("API URL remains the same...")

        #The API URL was invalid
        except Exception as e:
            print(f"API connection failed: {e}")
            api_url = ""
            return

        print("Getting livestream...")
        livestream = api.latest_livestream

        print("Clearing API mailboxes...")
        #Clear these mailboxes
        api.new_followers
        api.new_subscribers
        if livestream:
            print("Livestream found, so clearing new rants mailbox...")
            livestream.chat.new_rants
        else:
            print("No livestream found...")

        print("Adding timers...")
        obs.timer_add(refresh_alert_inboxes, refresh_rate * 1000)
        obs.timer_add(next_follower_alert, follower_alert_time * 1000)
        obs.timer_add(next_subscriber_alert, subscriber_alert_time * 1000)
        obs.timer_add(next_rant_alert, rant_alert_time * 1000)

    print("Script settings updated.")

def refresh_alert_inboxes():
    """Check if there are any new alertables and add them to the inboxes"""
    global current_scene_name
    global follower_inbox
    global subscriber_inbox
    global rant_inbox
    global livestream

    #We have no API URL or it was invalid
    if not api_url:
        return

    current_scene = obs.obs_frontend_get_current_scene()
    current_scene_name = obs.obs_source_get_name(current_scene)
    obs.obs_source_release(current_scene)

    follower_inbox += api.new_followers

    subscriber_inbox += api.new_subscribers

    #No livestream yet
    if not livestream:
        #Keep checking until we have a livestream
        livestream = api.latest_livestream
        return

    rant_inbox += livestream.chat.new_rants

def next_follower_alert():
    """Do the next follower alert, finishing up the last one"""
    global follower_inbox

    #No current scene gotten yet
    if not current_scene_name:
        return

    try:
        subscene = scene_items_by_name[current_scene_name][follower_alert_scene_source]
    except KeyError: #Scene selection or scene items table is invalid
        return

    #Finish up the last follower alert
    if obs.obs_sceneitem_visible(subscene):
        obs.obs_sceneitem_set_visible(subscene, False)
        print("Finished follower alert.")

    #No new followers
    if not follower_inbox:
        return

    follower = follower_inbox.pop(0)
    print(f"New follower: {follower}")
    #There is no follower alert scene in the current scene
    if follower_alert_scene_source not in scene_items_by_name[current_scene_name]:
        print("Follower scene not present in", current_scene_name)
        return

    #We are set to not do follower alerts
    if not follower_alert_use:
        print("Follower alerts are disabled.")
        return

    #Set the text
    print("Setting text...")
    f_uname_set = obs.obs_data_create()
    obs.obs_data_set_string(f_uname_set, "text", follower.username)
    obs.obs_source_update(sources_by_name[follower_alert_uname_source], f_uname_set)
    obs.obs_data_release(f_uname_set)

    #Show the alert
    print("Showing alert...")
    obs.obs_sceneitem_set_visible(subscene, True)

    #Wait for alert to finish hide transition as well (DOES NOT WORK)
    #print("Waiting for hide transition...")
    #time.sleep(obs.obs_sceneitem_get_hide_transition_duration(subscene) / 1000)

def next_subscriber_alert():
    """Do the next subscriber alert, finishing up the last one"""
    global subscriber_inbox

    #No current scene gotten yet
    if not current_scene_name:
        return

    try:
        subscene = scene_items_by_name[current_scene_name][subscriber_alert_scene_source]
    except KeyError: #Scene selection or scene items table is invalid
        return

    #Finish up the last subscriber alert
    if obs.obs_sceneitem_visible(subscene):
        obs.obs_sceneitem_set_visible(subscene, False)
        print("Finished subscriber alert.")

    #No new subscribers
    if not subscriber_inbox:
        return

    subscriber = subscriber_inbox.pop(0)
    print(f"New subscriber: {subscriber}")
    #There is no subscriber alert scene in the current scene
    if subscriber_alert_scene_source not in scene_items_by_name[current_scene_name]:
        print("Subscriber scene not present in", current_scene_name)
        return

    #We are set to not do subscriber alerts
    if not subscriber_alert_use:
        print("Subscriber alerts are disabled.")
        return

    #Set the userame text
    s_uname_set = obs.obs_data_create()
    obs.obs_data_set_string(s_uname_set, "text", subscriber.username)
    obs.obs_source_update(sources_by_name[subscriber_alert_uname_source], s_uname_set)
    obs.obs_data_release(s_uname_set)

    #Set the amount text
    s_amount_set = obs.obs_data_create()
    obs.obs_data_set_string(s_amount_set, "text", f"${subscriber.amount_cents:.2}")
    obs.obs_source_update(sources_by_name[subscriber_alert_amount_source], s_amount_set)
    obs.obs_data_release(s_amount_set)

    #Show the alert
    subscene = scene_items_by_name[current_scene_name][subscriber_alert_scene_source]
    obs.obs_sceneitem_set_visible(subscene, True)

def next_rant_alert():
    """Do the next rant alert, finishing up the last one"""
    global rant_inbox

    #No current scene gotten yet
    if not current_scene_name:
        return

    try:
        subscene = scene_items_by_name[current_scene_name][rant_alert_scene_source]
    except KeyError: #Scene selection or scene items table is invalid
        return

    #Finish up the last rant alert
    if obs.obs_sceneitem_visible(subscene):
        obs.obs_sceneitem_set_visible(subscene, False)
        print("Finished rant alert.")

    #No new rants
    if not rant_inbox:
        return

    rant = rant_inbox.pop(0)
    print(f"New rant: {rant}")
    #There is no rant alert scene in the current scene
    if rant_alert_scene_source not in scene_items_by_name[current_scene_name]:
        print("Rant scene not present in", current_scene_name)
        return

    #We are set to not do rant alerts
    if not rant_alert_use:
        print("Rant alerts are disabled.")
        return

    #Set the userame text
    r_uname_set = obs.obs_data_create()
    obs.obs_data_set_string(r_uname_set, "text", rant.username)
    obs.obs_source_update(sources_by_name[rant_alert_uname_source], r_uname_set)
    obs.obs_data_release(r_uname_set)

    #Set the message text
    r_message_set = obs.obs_data_create()
    obs.obs_data_set_string(r_message_set, "text", rant.text)
    obs.obs_source_update(sources_by_name[rant_alert_message_source], r_message_set)
    obs.obs_data_release(r_message_set)

    #Set the amount text
    r_amount_set = obs.obs_data_create()
    obs.obs_data_set_string(r_amount_set, "text", f"${rant.amount_cents:.2}")
    obs.obs_source_update(sources_by_name[rant_alert_amount_source], r_amount_set)
    obs.obs_data_release(r_amount_set)

    #Show the alert
    subscene = scene_items_by_name[current_scene_name][rant_alert_scene_source]
    obs.obs_sceneitem_set_visible(subscene, True)
