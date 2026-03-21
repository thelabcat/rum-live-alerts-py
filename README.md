# Rumble Live Alerts .PY
Replicate the behavior of RumBot 4.5 in OBS Studio, without WebSocket

## Prerequisites
- The Rumble Live Stream API not being blocked by Cloudflare for you. I've never had this happen to me, but it's the reason Tex "[VapinGamers](https://x.com/VapinGamers)" had to shut down RumBot 4.5, and switch to the new [RumBot Online](https://rumbot.org/) system.
- The desire to use custom OBS Studio sub-scene style alerts. If you are fine with slightly more generic web-render alerts, the above website can do that much more simply.
- A version of OBS Studio that allows you to install Pip wheels to the Python environment it uses for scripts. This basically means, not the Linux Flatpak version.
- Windows and MacOS only: The latest version of Python supported by OBS Studio, currently 3.12 as of the time of writing. 
- Linux only: The ability to install Pip packages to the default Python environment for your home directory. If your system Python environment is externally managed, this means setting up an environment that automatically activates when you enter the home directory. I recommend [PyEnv](https://github.com/pyenv/pyenv) personally.
- [Cocorum](https://pypi.org/project/cocorum/) installed to that same OBS Studio Python environment.

## Script Setup
1. In the OBS Studio header menu bar, choose "Tools" -> "Scripts". This will open the **Scripts dialog**.
2. If on Windows or MacOS, set OBS Studio to use your Python installation:
    1. Switch to the "Python Settings" tab of the dialog.
    2. Browse for your Python install path. You can find this by running `where python` in Windows Terminal, or `which python` on MacOS *I think.*
    3. Ensure that the text at the bottom of those Python Settings now says Python is loaded.
    4. Switch back to the main "Scripts" tab.
3. Click the "+" button in the bottom left-hand corner of the dialog, and browse for my script, `rum_live_alerts.py`.
4. Once the script is added, it should immediately show settings on the right. Setup is largely the same concepts as RumBot 4.5 from this point.

Note that what scripts are loaded and what settings they hold seems bound to what OBS Studio "Scene Collection" is loaded. Use this to your advantage to have multiple streaming profiles if desired.

## Legal
This file is part of Rumble Live Alerts .PY.

Rumble Live Alerts .PY is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Rumble Live Alerts .PY is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Foobar. If not, see <https://www.gnu.org/licenses/>.

## S.D.G.
