# Rumble Live Alerts .PY
Replicate the behavior of RumBot 4.5 in OBS Studio, without WebSocket

## Prerequisites
- The desire to use custom OBS Studio sub-scene style alerts. If you are fine with slightly more generic web-render alerts, I recommend the new [RumBot Online](https://rumbot.org/) system as it is much simpler to use than mine.
- **Windows and MacOS only:** The latest version of Python supported by OBS Studio, currently 3.12 as of the time of writing. 
- **Linux only:** The ability to install Pip packages to the environment OBS Studio uses. If your system Python environment is externally managed, you're gonna have to do some jerry-rigging. A reliable solution seems to be to create a Python virtual environment based on the system one, install the packages to it, then add that virtual environment's `site-packages` directory to the `PYTHONPATH` environment variable where you launch OBS Studio. This even works for the Flatpak version of OBS, but you need to configure the environment variable with Flatseal or something.
- [Cocorum](https://pypi.org/project/cocorum/) installed to that same OBS Studio Python environment.

## Script Setup
1. Download `rum_live_alerts.py` from this repository.
2. In the OBS Studio header menu bar, choose "Tools" -> "Scripts". This will open the **Scripts dialog**.
3. If on Windows or MacOS, set OBS Studio to use your Python installation:
    1. Switch to the "Python Settings" tab of the dialog.
    2. Browse for your Python install path. If you're not sure where this is, run `where.exe python` in Windows Terminal, or I think `which python` on MacOS.
    3. Ensure that the text at the bottom of those Python Settings now says Python is loaded.
    4. Switch back to the main "Scripts" tab.
4. Click the "+" button in the bottom left-hand corner of the dialog, and browse for my script, `rum_live_alerts.py`, wherever you downloaded it.
5. Once the script is added, it should immediately show settings on the right. Setup is largely the same concepts as RumBot 4.5 from this point, but there are some differences.

## Key differences from RumBot 4.5
- Everything for selecting sources was a text field in RumBot. In this program, it is a hybrid between a text field and a pull-down of valid sources. You can still manually enter source names that are not in the pull-down list, even invalid ones, and the script will quietly make note of the error in the debug before moving on. This currently serves as a way to disable some aspects of an alert, by just leaving an invalid source selected if you don't want that bit (for example, a rant's message). The text source pull-downs in particular are each auto-populated with only whatever text sources are available in the selected sub-scene. Select the sub-scene for each alert first, before trying to select text sources for it.
- I added fields with Python string formatting, so you can put stuff around the text that the script sets. The default values should reflect this, with formatted values inside `{}` curly braces. One thing they don't indicate, however, is that each text field actually checks for *all* the values associated with that alert. If you want to include the username of the rant in the rant message for some reason, you can. I'm planning on adding ways to add or remove text source targeters from an alert at will, so that you can have as many or as few as you want, but for now it's just this.
- Test alerts are not configurable. They will always have the same values.

Note that what scripts are loaded and what settings they hold seems bound to what OBS Studio "Scene Collection" is loaded. Use this to your advantage to have multiple streaming profiles if desired.

## Alert host scene

**Alert host scene** is under Base Settings. The default is `<dynamic: current scene>`, which is how the script used to work: each alert shows by toggling its sub-scene inside whatever scene is live. Every scene you might cut to needs its own copies of those alert sub-scenes (Follower Scene, Subscriber Scene, and the rest).

To keep one layout instead, make a single master scene (for example, `Alerts`) and put the alert sub-scenes in it. Leave them hidden until an alert fires. Add that master scene as a source in every program scene, then set **Alert host scene** to it. Alerts toggle inside that master scene, so it does not matter which program scene is live. The alert sub-scenes need to be direct items in the host scene. One that is tucked inside a group is not found. If you rename the host scene later, pick it again in the script.

### Studio Mode

Studio Mode shows a duplicate of the current scene on the program output. With `<dynamic: current scene>`, the script toggles items in the current scene, and those toggles can stay invisible on stream until the next Studio Mode transition. A fixed Alert host scene avoids that: the alert items live in the nested master scene, which both the preview and the program copy share.

If `<dynamic: current scene>` is selected while Studio Mode is on, the script prints the explanation above to the log and shows a one-line note in the script settings. It checks this when the script loads, when the script settings are opened, and when Alert host scene is changed. Turning Studio Mode on or off after that does not refresh the note. The script will not turn Studio Mode off. Pick a fixed Alert host scene if you stream in Studio Mode.

## Legal
This file is part of Rumble Live Alerts .PY.

Rumble Live Alerts .PY is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Rumble Live Alerts .PY is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Foobar. If not, see <https://www.gnu.org/licenses/>.

## S.D.G.
