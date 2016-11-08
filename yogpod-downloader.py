#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 Gonçalo Baltazar <me@goncalomb.com>
# YoGPoD-Downloader is released under the terms of the MIT License.
# See LICENSE.txt for details.

from __future__ import division, absolute_import, print_function, unicode_literals
try: range = xrange
except NameError: pass
try: input = raw_input
except NameError: pass

try:
	from urlparse import urlparse
except ImportError:
	from urllib.parse import urlparse

import os, sys, io, time, re, signal, argparse
import xml.etree.ElementTree as ET
from email.utils import parsedate as parsedate

def signal_handler(sig):
	print("\r\033[K\r" + sig)
	sys.exit(1)
signal.signal(signal.SIGINT, lambda a, b: signal_handler("SIGINT"))
signal.signal(signal.SIGTERM, lambda a, b: signal_handler("SIGTERM"))

# control variables

data_dir = "yogpod-data"
rss_file = data_dir + "/yogpod.rss"
episode_types = {
	"YoGPoD": { "regex": "^YoGPoD (\d+\w?)\: (.+)$" },
	"Interviews": { "regex": "^Interview|^Nordrassil" },
	"YoGPoD-Animations": { "regex": "^(.+): YoGPoD Fan Animation (\d+|Bonus!)$" },
	"SimpleSimon": { "regex": "^Simple Simon " },
	"Triforce": { "regex": "^Triforce! #(\d+?): (.+)$" },
	"PyrionLovesAnime": { "regex": "^Pyrion Loves Anime #(\d+?) - (.+)$" }
}

# helper functions

def ensure_path(path):
	if not os.path.isdir(path):
		os.mkdir(path)

def format_size(size):
	if size >= 1073741824:
		return "{:.1f} GB".format(size/1073741824)
	elif size >= 1048576:
		return "{:.1f} MB".format(size/1048576)
	elif size >= 1024:
		return "{:.1f} KB".format(size/1024)
	elif size == 1:
		return str(size) + " byte"
	else:
		return str(size) + " bytes"

def confirm(message):
	while True:
		try:
			result = input(message + " (y/n)? ").lower();
			if result == "y":
				return True
			elif result == "n":
				return False
		except EOFError:
			return False

def reporthook(count, block_size, total_size):
	global reporthook_time
	now = time.time()
	if count == 0:
		reporthook_time = now
	current = count*block_size
	if current > total_size:
		current = total_size
	percent = current*100/total_size
	speed = 0 if count == 0 else current/(now - reporthook_time)
	sys.stdout.write("\r\033[K\r  {:.2f}%   {} / {}   {}/s\r".format(percent, format_size(current), format_size(total_size), format_size(speed)))
	sys.stdout.flush()

try:
	import requests
	def download_file(url, filename, progress=False):
		r = requests.get(url, stream=True, headers={"Accept-Encoding": ""})
		length = int(r.headers['Content-Length'])
		read = 0
		with open(filename, "wb") as fp:
			if progress:
				reporthook(read, 1, length)
			for chunk in r.iter_content(chunk_size=8192):
				read += len(chunk)
				if chunk:
					fp.write(chunk)
					if progress:
						reporthook(read, 1, length)
		if progress:
			sys.stdout.write("\r\033[K\r");
			sys.stdout.flush()
except ImportError:
	print("WARNING: Requests package not found! Using 'urlretrieve' to download the files, this may not work. Please install the Requests package.")
	print()
	try:
		from urllib.request import urlretrieve
	except:
		from urllib import urlretrieve
	def download_file(url, filename, progress=False):
		urlretrieve(url, filename, reporthook if progress else None)
		if progress:
			sys.stdout.write("\r\033[K\r");
			sys.stdout.flush()

# initialize

print("YoGPoD-Downloader")
print("2016 Gonçalo Baltazar <me@goncalomb.com>")
print()

ensure_path(data_dir)

episodes = []
for type_name, type_data in episode_types.items():
	type_data["dir"] = data_dir + "/" + type_name
	type_data["episodes"] = []
	type_data["count"] = 0
	type_data["count_have"] = 0
	type_data["size"] = 0
	type_data["size_have"] = 0
	type_data["download"] = True

# parse

parser = argparse.ArgumentParser()
parser.add_argument("--no-mtime", action="store_true", help="don't set file dates")
args = parser.parse_args()

# download and parse feed

print("Fetching RSS feed (yogpod.libsyn.com/rss)...")
download_file("http://yogpod.libsyn.com/rss", rss_file)
tree = ET.parse(rss_file)
root = tree.getroot()
channel = root.find("channel")
print()

# find episodes

found_unknown = False
for item in reversed(list(channel.iter("item"))):
	if item.find("enclosure") is None:
		continue

	episode = {
		"title": item.find("title").text,
		"date": item.find("pubDate").text,
		"url": item.find("enclosure").get("url"),
		"size": int(item.find("enclosure").get("length"))
	}

	for type_name, type_data in episode_types.items():
		matches = re.match(type_data["regex"], episode["title"])
		if matches:
			episode["type"] = type_name
			episode["matches"] = matches
			type_data["count"] += 1
			type_data["size"] += episode["size"]
			break

	if not "type" in episode:
		print("WARNING: Unknown episode '" + episode["title"] + "'!")
		found_unknown = True
		continue

	episode["local_file"] = data_dir + "/" + episode["type"] + "/" + os.path.basename(urlparse(episode["url"]).path)

	episode["have"] = False
	if os.path.isfile(episode["local_file"]) and os.path.getsize(episode["local_file"]) == episode["size"]:
		episode["have"] = True
		episode_types[episode["type"]]["count_have"] += 1
		episode_types[episode["type"]]["size_have"] += episode["size"]

	episode_types[episode["type"]]["episodes"].append(episode)
	episodes.append(episode)

if found_unknown:
	print("Cannot download unknown episodes. Look for an update on GitHub:")
	print("https://github.com/goncalomb/YoGPoD-Downloader")
	print()

# show information

total_count = 0
total_count_have = 0
total_size = 0
total_size_have = 0
type_name_just = 0
for type_name, type_data in episode_types.items():
	if len(type_name) > type_name_just:
		type_name_just = len(type_name)
for type_name, type_data in episode_types.items():
	total_count += type_data["count"]
	total_count_have += type_data["count_have"]
	total_size += type_data["size"]
	total_size_have += type_data["size_have"]
	print(type_name.ljust(type_name_just) + "  " + str(type_data["count_have"]) + " / " + str(type_data["count"]) + " episodes (" + format_size(type_data["size_have"]) + " / " + format_size(type_data["size"]) + ")")
print()
print("Total:".rjust(type_name_just) + "  " + str(total_count_have) + " / " + str(total_count) + " episodes")
print("".rjust(type_name_just) + "  " + format_size(total_size_have) + " / " + format_size(total_size))
print()

# ask what to download

if total_count_have != total_count:
	if not confirm("Download everything (" + format_size(total_size - total_size_have) + ")"):
		for type_name, type_data in episode_types.items():
			if type_data["count_have"] != type_data["count"]:
				type_data["download"] = confirm("Download " + type_name + " (" + format_size(type_data["size"] - type_data["size_have"]) + ")")
	print()
else:
	print("Nothing to download!")
	print()

# download files

for episode in episodes:
	if episode_types[episode["type"]]["download"] and not episode["have"]:
		print("Downloading " + episode["title"] + "...")
		ensure_path(episode_types[episode["type"]]["dir"])
		download_file(episode["url"], episode["local_file"], True);
		episode["have"] = True
		episode_types[episode["type"]]["count_have"] += 1
		episode_types[episode["type"]]["size_have"] += episode["size"]

# touch files

if not args.no_mtime:
	print("Setting file dates...")
	for episode in episodes:
		if episode["have"]:
			atime = os.stat(episode["local_file"]).st_mtime
			mtime = int(time.mktime(parsedate(episode["date"])))
			os.utime(episode["local_file"], (0, mtime))

# create playlists

print("Creating playlists...")
for type_name, type_data in episode_types.items():
	if type_data["count_have"] == 0:
		continue
	with io.open(data_dir + "/" + type_name + ".m3u8", "w", encoding="utf-8") as fp:
		fp.write("#EXTM3U\r\n")
		for episode in type_data["episodes"]:
			if episode["have"]:
				fp.write("#EXTINF:0," + episode["title"] + "\r\n")
				fp.write(episode["local_file"][len(data_dir) + 1:] + "\r\n")
		fp.close()

# the end

print("Done.")
