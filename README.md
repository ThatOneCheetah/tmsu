# TMSU
Twitch Modpack Server Updater (requires `requests`, install: `pip install requests`)

# Usage
Change the `PROFILE` variable to one of the following things:
 * A relative path to a Twitch App Modpack archive.
 * An absolute path to a Twitch App Modpack archive.
 * A URL to a Twitch App Modpack archive.
 
 Change `MEMORY_MIN` and `MEMORY_MAX` according to the memory requirements of the modpack.
 
 If necessary, change `JAVA_PATH` to the Java path, ending in a path delimiter (Windows: `\\`, GNU: `/`)
 
 To accept the Minecraft EULA from within TMSU you may change `MC_EULA` to `True`, no responsibilities are taken by the creator of TMSU if you decide to do so.

Launch `tmsu.py`, it will now download everything *automagically* and run the modpack server.

# Disclaimer
This script was hastily written. It works, but is nowhere near perfect.

The script will not work, and most likely crash, if the modpack uses any mod loader other than Forge.
