# Twitch Modpack Server Updater

# [User configuration]
	# Mods profile
PROFILE = "profile.zip"

	# By changing the setting below to True you are indicating your agreement to the Minecraft EULA (https://account.mojang.com/documents/minecraft_eula)
MC_EULA = False

	# JVM settings
MEMORY_MIN = 2048
MEMORY_MAX = 4096
JAVA_PATH = ""

	# Number of threads a threadpool should spawn
	# Typically, this should be set to the amount of cores available times two
NUM_THREADS = 16
# ---

# --- TOUCHING ANYTHING BEYOND THIS POINT MAY BREAK TMSU --- #

# [Imports]
import os
import sys
import json
import requests

from io import BytesIO
from time import sleep
from zipfile import ZipFile
from subprocess import call as spcall
from multiprocessing.dummy import Pool
# ---

# [Internal configuration]
FORGE_INSTALLER_TEMPLATE = "forge-{}-{}-installer.jar"
VANILLA_SERVER_TEMPLATE = "minecraft_server.{}.jar"
FORGE_SERVER_TEMPLATE = "forge-{}-{}-universal.jar"
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
CURSE_URL_TEMPLATE = "https://minecraft.curseforge.com/projects/{}/files/{}/download"
FORGE_URL_TEMPLATE = "http://files.minecraftforge.net/maven/net/minecraftforge/forge/{0}-{1}/forge-{0}-{1}-installer.jar"
HOUSEKEEPING_FILE = "tmsu.json"
OVERRIDES_FOLDER = "./"
MODS_FOLDER = "./mods/"

FORGE_SERVER_JAR = ""
FORGE_DOUBLE_VERSIONS = [ "1.7.10", "1.8.9" ]
FORGE_URL_TEMPLATE_DOUBLE = "http://files.minecraftforge.net/maven/net/minecraftforge/forge/{0}-{1}-{0}/forge-{0}-{1}-{0}-installer.jar"
FORGE_SERVER_TEMPLATE_DOUBLE = "forge-{0}-{1}-{0}-universal.jar"
# ---

# [Helper functions]
def Request( url ):
	print( "> " + url, end = " " )
	sys.stdout.flush()
	result = requests.get( url )
	print( "[OK]" )

	return result

def Path():
    return os.path.dirname( os.path.realpath( sys.argv[ 0 ] ) )
# ---

# [Download functions]
def DownloadVanilla( version ): # Download vanilla server jar by version (e.g. version="1.12.2")
	# Fetch version manifest
	versionManifest = Request( VERSION_MANIFEST_URL ).json()

	# Search for requested version
	mfEntry = [ v for v in versionManifest[ "versions" ] if v[ "id" ] == version ]

	if len( mfEntry ) == 0:
		raise KeyError( "Requested version not found in manifest file" )
	
	# Request and return the actual version json after finding it
	versionInfo = Request( mfEntry[ 0 ][ "url" ] ).json()

	with open( VANILLA_SERVER_TEMPLATE.format( version ), "wb" ) as f:
		f.write( Request( versionInfo[ "downloads" ][ "server" ][ "url" ] ).content )

def DownloadForge( mcVersion, forgeVersion ):
	filename = FORGE_INSTALLER_TEMPLATE.format( mcVersion, forgeVersion )
	with open( filename, "wb" ) as f:
		if mcVersion in FORGE_DOUBLE_VERSIONS:
			f.write( Request( FORGE_URL_TEMPLATE_DOUBLE.format( mcVersion, forgeVersion ) ).content )
		else:
			f.write( Request( FORGE_URL_TEMPLATE.format( mcVersion, forgeVersion ) ).content )

	print( "> Installing Forge", end = " " )
	sys.stdout.flush()
	with open( os.devnull, "w" ) as fnull:
		spcall( [ JAVA_PATH + "java", "-jar", filename, "--installServer" ], stdout = fnull )
	os.remove( filename )
	print( "[OK]" )

def DownloadMod( projectID, fileID ):
	mod = requests.get( CURSE_URL_TEMPLATE.format( str( projectID ), str( fileID ) ) )
	filename = mod.url[ mod.url.rfind( "/" ) + 1 : ]

	key = str( projectID ) + "-" + str( fileID )

	with open( MODS_FOLDER + filename, "wb" ) as f:
			f.write( mod.content )

	print( "> " + mod.url + " [OK]" )
	return [ key, filename ]

def ExtractOverride( zf, filename, overrides ):
	with zf.open( filename ) as f:
		target = OVERRIDES_FOLDER + filename[ len( overrides ) : ]
		if os.path.isfile( target ):
			os.remove( target )
		
		with open( target, "wb" ) as ff:
			ff.write( f.read() )

def UpdateFromZip( zipFile ): # Update install by zip file (e.g. file="MyCustomPack-1.0a.zip")
	modManifest = {}
	
	# Read mod manifest from zip
	with ZipFile( zipFile ) as zf:
		with zf.open( "manifest.json" ) as f:
			modManifest = json.loads( f.read() )

	# Check if vanilla server jar is installed
	mcVersion = modManifest[ "minecraft" ][ "version" ]
	if not os.path.isfile( VANILLA_SERVER_TEMPLATE.format( mcVersion ) ):
		DownloadVanilla( mcVersion )

	# Check if forge universal jar is installed
	forgeVersion = modManifest[ "minecraft" ][ "modLoaders" ][ 0 ][ "id" ].split( "-" )[ 1 ]

	global FORGE_SERVER_JAR
	if mcVersion in FORGE_DOUBLE_VERSIONS:
		FORGE_SERVER_JAR = FORGE_SERVER_TEMPLATE_DOUBLE.format( mcVersion, forgeVersion )
	else:
		FORGE_SERVER_JAR = FORGE_SERVER_TEMPLATE.format( mcVersion, forgeVersion )

	if not os.path.isfile( FORGE_SERVER_JAR ):
		DownloadForge( mcVersion, forgeVersion )
	# Check if mods folder exsits
	if not os.path.isdir( MODS_FOLDER ):
		os.mkdir( MODS_FOLDER )

	# Housekeeping
	print( "> Housekeeping (1/2)", end = " " )
	sys.stdout.flush()
	hkNew = {}
	for file in modManifest[ "files" ]:
		key = str( file[ "projectID" ] ) + "-" + str( file[ "fileID" ] )
		hkNew[ key ] = key + ".jar"

	hkOld = {}
	if os.path.isfile( HOUSEKEEPING_FILE ):
		with open( HOUSEKEEPING_FILE, "r" ) as f: # Load old housekeeping file
			hkOld = json.loads( f.read() )
		
		os.remove( HOUSEKEEPING_FILE )

		for key in hkOld: # Remove obsolete mods
			if not key in hkNew:
				if os.path.isfile( MODS_FOLDER + hkOld[ key ] ):
					os.remove( MODS_FOLDER + hkOld[ key ] )
			else:
				hkNew[ key ] = hkOld[ key ] # Move filename from old to new housekeeping file
	
	print( "[OK]" )

	# Download new mods and build new housekeeping file
	job = [] # Make a job for threaded downloads
	jobResult = []

	for file in modManifest[ "files" ]:
		key = str( file[ "projectID" ] ) + "-" + str( file[ "fileID" ] )
		if not os.path.isfile( MODS_FOLDER + hkNew[ key ] ):
			job.append( ( file[ "projectID" ], file[ "fileID" ] ) )

	with Pool( NUM_THREADS ) as p:
		jobResult = p.starmap( DownloadMod, job )

	print( "> Housekeeping (2/2)", end = " " )
	sys.stdout.flush()
	for v in jobResult:
		hkNew[ v[ 0 ] ] = v[ 1 ]
	
	with open( HOUSEKEEPING_FILE, "w" ) as f: # Write new housekeeping file
		f.write( json.dumps( hkNew, sort_keys = True ) )

	print( "[OK]" )

	overrides = modManifest[ "overrides" ] + "/"

	job = [] # New job for threaded extraction

	print( "> Overrides", end = " " )
	with ZipFile( zipFile ) as zf:
		for filename in zf.namelist():
			if filename.startswith( overrides ) and not filename.endswith( "/" ):
				dirs = os.path.dirname( filename[ len( overrides ) : ] )
				if not os.path.isdir( dirs ): # Make directory if it does not exist
					os.makedirs( dirs )

				job.append( ( zf, filename, overrides ) )
			
		with Pool( NUM_THREADS ) as p:
			jobResult = p.starmap( ExtractOverride, job )
	print( "[OK]" )

def UpdateFromURL( url ): # Update install by url (e.g. url="http://my.host/my-pack.zip")
	mods = Request( url )
	
	with BytesIO() as buffer:
		buffer.write( mods.content )
		UpdateFromZip( buffer )
# ---

# [Run updater]
if PROFILE.startswith( "http://" ) or PROFILE.startswith( "https://" ) or PROFILE.startswith( "ftp://" ):
	UpdateFromURL( PROFILE )
else:
	UpdateFromZip( PROFILE )
# ---

# [MC EULA]
if MC_EULA == True:
	if os.path.isfile( "eula.txt" ):
		os.remove( "eula.txt" )
	
	with open( "eula.txt", "w" ) as f:
		f.write( "eula=true" )
# ---

# [Run server]
spcall( [ JAVA_PATH + "java", "-Xms" + str( MEMORY_MIN ) + "M", "-Xmx" + str( MEMORY_MAX ) + "M", "-jar", FORGE_SERVER_JAR, "nogui" ] )
# ---