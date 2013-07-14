#!/usr/bin/env python

# Copyright (C) 2013  Nikola Kovacevic

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import gzip
import struct
import difflib
import urllib2# +import urllib.request, urllib.error, urllib.parse
import argparse
import StringIO# +import io
from xmlrpclib import ServerProxy# +from xmlrpc.client import ServerProxy

try:
    # noinspection PyUnresolvedReferences
    import guessit
except ImportError:
    print "Can't import guessit module, only searches using file hash will be performed"

FILE_EXT = [
    '.3g2', '.3gp', '.3gp2', '.3gpp', '.60d', '.ajp', '.asf', '.asx', '.avchd', '.avi',
    '.bik', '.bix', '.box', '.cam', '.dat', '.divx', '.dmf', '.dv', '.dvr-ms', '.evo',
    'flc', '.fli', '.flic', '.flv', '.flx', '.gvi', '.gvp', '.h264', '.m1v', '.m2p',
    '.m2ts', '.m2v', '.m4e', '.m4v', '.mjp', '.mjpeg', '.mjpg', '.mkv', '.moov', '.mov',
    '.movhd', '.movie', '.movx', '.mp4', '.mpe', '.mpeg', '.mpg', '.mpv', '.mpv2', '.mxf',
    '.nsv', '.nut', '.ogg', '.ogm', '.omf', '.ps', '.qt', '.ram', '.rm', '.rmvb',
    '.swf', '.ts', '.vfw', '.vid', '.video', '.viv', '.vivo', '.vob', '.vro', '.wm',
    '.wmv', '.wmx', '.wrap', '.wvx', '.wx', '.x264', '.xvid'
]

sub_language = 'eng'
useragent = "ossubd"
server = ServerProxy("http://api.opensubtitles.org/xml-rpc")

# hash_search = True
AUTO_DOWNLOAD = False
SUBFOLDER = None
MATCH_CUTOFF = 0.75  # difflib ratio cutoff float range[0,1],
# 0- strings don't have anything in common, 1- strings are identical

slashes_type = "\\" if os.name == "nt" else "/" # assume unix like path


# noinspection PyBroadException
def search_subtitles(file_list):
    """
    :param file_list: list of video files(with full path) for which to search subtitles
    """
    #TODO: Check if user is over the download limit
    #http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC#ServerInfo
    count = 0
    try:
        session = server.LogIn("", "", sub_language, useragent)
    except:
        print "Can't log in to opensubtitles API, try again later..."
        exit()
    token = session["token"]
    for file_name in file_list:
        count += 1
        ep_info = None
        file_name, file_extension = os.path.splitext(file_name)
        print "-" * 50 + '\nSearching subtitle for "{}" | ({}/{})'.format(os.path.basename(file_name) + file_extension,
                                                                          count, len(file_list))
        file_size = os.path.getsize(file_name + file_extension)
        current_hash = get_hash(file_name + file_extension, file_size)

        if current_hash is None:
            print "Can't calculate hash for {}".format(file_name)
            hash_search = False
        else:
            hash_search_query = [{"sublanguageid": sub_language,
                                  'moviehash': current_hash,
                                  'moviebytesize': file_size}]
            hash_search=True

        try:
            ep_info = guessit.guess_episode_info(file_name)

            tv_show = ep_info['series']
            season = ep_info['season']
            episode = ep_info['episodeNumber']
            # todo: Construct query like this perhaps: array('query' => 'south
            # park', 'season' => 1, 'episode' => 1, 'sublanguageid'=>'all'),
            query_info = "{} S{:02d}E{:02d}".format(tv_show, # TODO: season & episode redundant?
                                                    int(season),
                                                    int(episode),
            ).replace(" ", "+")

            # **If you define moviehash and moviebytesize, then imdbid and query in same array are ignored.**
            # If you define imdbid, then moviehash, moviebytesize and query is ignored.
            # If you define query, then moviehash, moviebytesize and imdbid is ignored.
            file_search_query = [{'sublanguageid': sub_language,
                                  'query': query_info, # TODO: Replace with only tv_show name
                                  'season': season, # XXX: Check if this improves results.
                                  'episode': episode}]
            query_search=True
        except KeyError:
            print "Can't determine enough info about series/episode from the filename."
            # do_download = False
            query_search = False

        if query_search:
            query_results = server.SearchSubtitles(token, file_search_query)
            if query_results['status'] != "200 OK":
                print "Query search failed ", query_results['status']
                query_results=None
            else:
                if not query_results['data']:
                    print "Query search returned no results"
                    query_results=None
                else:
                    query_results = query_results['data']

        if hash_search:
            hash_results = server.SearchSubtitles(token, file_search_query)
            if hash_results['status'] != '200 OK':
                print '"Hash search failed', hash_results['status']
                hash_results=None
            else:
                if not hash_results['data']:
                    print "Hash search returned no results"
                    hash_results=None
                else:
                    hash_results = hash_results['data']


        if query_search is False and hash_search is False:
            do_download = False
            print "Couldn't find subtitles in {} for {}".format(sub_language, file_name)
        else:
            do_download=True
        if do_download:
            ep_info["filename"] = file_name
            subtitles_list = []
            if query_results:# Subtitle results exist
                for item in query_results:
                    subtitles_list.append(item)
            if hash_results:
                for item in hash_results:
                    subtitles_list.append(item)

            #XXX: Debug stuff remove before git push
            with open("log.log", "a") as log:
                log.write("\n\n\n"+file_name + "\n -- QUERY")
                log.write(str(file_search_query) + "\n\n")
                log.write(str(query_results) + "\n\n")
                log.write("-" * 10 + "\n")

                log.write(file_name + "\n -- HASH")
                log.write(str(hash_search_query) + "\n\n")
                log.write(str(hash_results) + "\n\n")
                log.write("-" * 10 + "\n")

                log.write("*" * 75 + "\n\n\n")
                log.write("subtitles_list:\n\n")
                log.write(str(subtitles_list))

            download_prompt(subtitles_list, ep_info)


# noinspection PyBroadException
def download_prompt(subtitles_list, ep_info):
    """
    :param subtitles_list: list containing dicts of each subtitle returned from opensubtitles api
    :param ep_info:  dict containing episode info most important -- 'series' - tv show name and 'title' -ep title
    :return: Nothing
    """
    if AUTO_DOWNLOAD:
        auto_download(subtitles_list, ep_info)
        return
    user_choice = ""
    possible_choices = ["a", "q", "s"]
    sub_dict = {}
    count = 1

    for subtitle in subtitles_list:
        sync = subtitle['MatchedBy'] == 'moviehash'
        print "{}:{} {} | Downloads: {}".format(count,
                                                "" if not sync else " [sync match]",
                                                subtitle["SubFileName"],
                                                subtitle["SubDownloadsCnt"], )
        sub_dict[count] = subtitle
        count += 1
    possible_choices.extend(sub_dict.keys())

    while user_choice not in possible_choices:
        user_input = raw_input("Enter subtitle # to download or 's' - skip this file,"
                        " 'a' - auto download,"
                        " 'q' - quit\n>>>")
        try:  # Faster than .isdigit()
            user_choice = int(user_input)
        except:
            user_choice = user_input.lower()

        if user_choice not in possible_choices:
            print "invalid input"

    if type(user_choice) is int:
        if sub_dict.get(user_choice, False) is not False:
            download_subtitle(sub_dict[user_choice], ep_info)
        else:
            print "Invalid input only subtitle choices from {} to {} are available".format(1, count)

    elif user_choice.lower() == "a":
        auto_download(subtitles_list, ep_info)

    elif user_choice.lower() == "q":
        print 'Quitting'
        exit()

    elif user_choice.lower() == "s":
        print "skipping..."
    else:
        print "Invalid input"


# noinspection PyArgumentList
def auto_download(subtitles_list, ep_info):
    """
    :param subtitles_list: list containing (all) subtitle dicts returned from opensubtitles
    :param ep_info: episode info dict
    ep_info example:
    {u'mimetype': u'video/x-flv', u'episodeNumber': 11, u'container': u'flv',
    u'title': u'Adventures in Babysitting', u'series': u'Supernatural',
    u'type': u'episode', u'season': 7, u'filename':<full file path>}
    """
    # MatchedBy can be: moviehash, imdbid, tag, fulltext

    sequence = difflib.SequenceMatcher(None, "", "")
    possible_matches = []
    best_choice = {"best": None, "downloads": 0}

    for subtitle in subtitles_list:
        # Change title from i.e. "The Office (US) Dunder Mifflin Infinity" to the office (us) dunder mifflin infinity
        try:
            subtitle_title_name = subtitle['MovieName'].replace("'", "").replace('"', '').lower()
            episode_title_name = "{} {}".format(ep_info['series'].lower(), ep_info['title'].lower())
        except KeyError:
            subtitle_title_name=0
            episode_title_name=1
        # TV Show name and title are separate keys in ep_info dict, not like in sub dict

        sequence.set_seqs(subtitle_title_name, episode_title_name)
        if sequence.ratio() > MATCH_CUTOFF:
            # Names of series title and episode names match enough, should be valid subtitle
            possible_matches.append(subtitle)

        if subtitle['MatchedBy'] == 'moviehash':
                possible_matches.append(subtitle)


    for sub in possible_matches:
        if sub['MatchedBy'] == 'moviehash':
            best_choice['best'] = sub
            best_choice['downloads'] = "Movie hash"
            break
        if int(sub["SubDownloadsCnt"]) > best_choice["downloads"]:
            best_choice["best"] = sub
            best_choice["downloads"] = sub["SubDownloadsCnt"]

    #print best_choice["best"]["SubFileName"], best_choice["downloads"]
    if best_choice["best"] is not None:
        download_subtitle(best_choice["best"], ep_info)
    else:
        print "Can't match subtitle..."


# noinspection PyBroadException
def download_subtitle(subtitle_info, ep_info):
    """
    :param subtitle_info: dict of the subtitle with sub info such as download link etc.
    :param ep_info: episode info dict
    ep_info example:
    {u'mimetype': u'video/x-flv', u'episodeNumber': 11, u'container': u'flv',
    u'title': u'Adventures in Babysitting', u'series': u'Supernatural',
    u'type': u'episode', u'season': 7, u'filename':<full file path>}
    """
    download_url = subtitle_info["SubDownloadLink"]
    subtitle_folder = os.path.dirname(ep_info['filename'])
    subtitle_folder += slashes_type if SUBFOLDER is None else slashes_type + SUBFOLDER + slashes_type
    subtitle_name = subtitle_folder + os.path.basename(ep_info["filename"])
    subtitle_name += "." + subtitle_info["SubFormat"]  # .srt only on opensubtitles?

    if not os.path.isdir(subtitle_folder):
        os.mkdir(subtitle_folder)
        # TODO: Add exception handling, if we can't create folder we won't be able to save sub there (probably)

    # Not in try/except because this shouldn't ever fail, and if it does other subtitles
    # won't be downloaded too so ignoring it seems useless. letting it to raise
    # error makes more sense
    sub_zip_file = urllib2.urlopen(download_url)
    sub_gzip = gzip.GzipFile(fileobj=StringIO.StringIO(sub_zip_file.read()))
    subtitle_content = sub_gzip.read()
    try:
        with open(subtitle_name, 'wb') as subtitle_output:
            subtitle_output.write(subtitle_content)
    except:
        print "Couldn't save subtitle, permissions issue?"


def get_hash(file_name, file_size):
    """
    :param file_name: File path for which to calculate hash
    :return: Hash or None
    """
    if file_size < 65536 * 2:
        return None
    try:
        longlongformat = 'q'  # long long
        bytesize = struct.calcsize(longlongformat)

        f = open(file_name, "rb")

        file_hash = file_size

        for x in range(65536 / bytesize):
            file_buffer = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, file_buffer)
            file_hash += l_value
            file_hash &= 0xFFFFFFFFFFFFFFFF  # to remain as 64bit number

        f.seek(max(0, file_size - 65536), 0)
        for x in range(65536 / bytesize):
            file_buffer = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, file_buffer)
            file_hash += l_value
            file_hash &= 0xFFFFFFFFFFFFFFFF

        f.close()
        return "%016x" % file_hash

    except IOError:
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Subtitle downloader for TV Shows')
    parser.add_argument("folder", type=str,
                        help="Folder which will be scanned for allowed video files, "
                             "and subtitles for those files will be downloaded")
    parser.add_argument("-s", "--subfolder", type=str,
                        help="Subfolder to save subtitles to, relative to original video file path")
    parser.add_argument("-l", "--language", type=str,
                        help="Subtitle language, must be an ISO 639-1 Code i.e. (eng,fre,deu) Default English(eng)")
    parser.add_argument("-a", "--auto", action="store_true",
                        help="Auto download subtitles for all files without prompt "
                             "(Overwrites subtitles with same filename)")
    args = parser.parse_args()

    directory = args.folder
    if os.path.isfile(directory):
        valid_files = [directory]  # single file, although its name is directory
    elif os.path.isdir(directory):
        directory += slashes_type if not directory.endswith(slashes_type) else ""

        valid_files = [directory + name for name in os.listdir(directory)
                       if os.path.splitext(name)[1] in FILE_EXT]
    else:
        print "{} is not a valid file or directory".format(directory)
    if args.subfolder:
        SUBFOLDER = args.subfolder
        SUBFOLDER = SUBFOLDER.replace(slashes_type, "")
    if args.language:
        if len(args.language) == 3:
            sub_language = args.language.lower()
        else:
            print 'Argument not ISO 639-1 Code check this for list of valid codes' \
                  ' http://en.wikipedia.org/wiki/List_of_ISO_639-1_codes'
            exit()

    if args.auto:
        AUTO_DOWNLOAD = True

    # print "f: {}\nsubfolder: {}\nl: {}\na:{}".format(directory, SUBFOLDER, sub_language, AUTO_DOWNLOAD)
    # print valid_files
    search_subtitles(valid_files)
