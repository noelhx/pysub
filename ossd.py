# Copyright (C) 2012, Nikola Kovcevic <nikolak@outlook.com>

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
# OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

from xmlrpclib import ServerProxy, Error
import StringIO
import argparse
import gzip
import os
import struct
import sys
import urllib2

allowed_file_ext = [
    '.3g2', '.3gp', '.3gp2', '.3gpp', '.60d', '.ajp', '.asf', '.asx', '.avchd', '.avi',
    '.bik', '.bix', '.box', '.cam', '.dat', '.divx', '.dmf', '.dv', '.dvr-ms', '.evo',
    'flc', '.fli', '.flic', '.flv', '.flx', '.gvi', '.gvp', '.h264', '.m1v', '.m2p',
    '.m2ts', '.m2v', '.m4e', '.m4v', '.mjp', '.mjpeg', '.mjpg', '.mkv', '.moov', '.mov',
    '.movhd', '.movie', '.movx', '.mp4', '.mpe', '.mpeg', '.mpg', '.mpv', '.mpv2', '.mxf',
    '.nsv', '.nut', '.ogg', '.ogm', '.omf', '.ps', '.qt', '.ram', '.rm', '.rmvb',
    '.swf', '.ts', '.vfw', '.vid', '.video', '.viv', '.vivo', '.vob', '.vro', '.wm',
    '.wmv', '.wmx', '.wrap', '.wvx', '.wx', '.x264', '.xvid'
]

sub_language = 'en'
opensub_domain = "http://api.opensubtitles.org/xml-rpc"
default_useragent = "OS Test User Agent"

server = ServerProxy(opensub_domain)

overwrite = False


def find_and_download(file_list):
    session = server.LogIn("", "", sub_language, default_useragent)
    token = session["token"]
    count = 0
    done_count = 0
    for f in file_list:
        count += 1
        do_download = True
        file_name, file_xtension = os.path.splitext(f)
        print '=' * 20
        print 'Searching subtitle for {0} | ({1}/{2})'.format(os.path.basename(f), count, len(file_list))

        if os.path.exists(file_name + '.srt'):
            if overwrite:
                print 'Subtitle exist, but new one will be downloaded'
            else:
                print 'Subtitle already exists, skipping'
                do_download = False

        if do_download:
            current_hash = get_hash(f)
            current_size = os.path.getsize(f)

            if current_hash == None:
                print "IOError"
                do_download = False

        if do_download:
            searchlist = []
            searchlist.append({'moviehash': current_hash, 'moviebytesize': str(current_size)})
            moviesList = server.SearchSubtitles(token, searchlist)

            if moviesList['data']:
                #http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC#SearchSubtitles
                index = 0
                data = moviesList['data']
                while index < len(data) - 1 and data[index]['ISO639'] != sub_language:
                    index += 1

                if index > len(data) - 1 or data[index]['ISO639'] != sub_language:
                    print 'Can\'t find subtitle in desired language...'

                else:
                    sub = data[index]
                    subURL = sub['SubDownloadLink']
                    print 'Subtitle found, downloading...'
                    sub_zip_file = urllib2.urlopen(subURL)

                    try:
                        sub_gzip = gzip.GzipFile(fileobj=StringIO.StringIO(sub_zip_file.read()))
                        subtitle_content = sub_gzip.read()
                        with open(file_name + '.srt', 'wb') as subtitle_output:
                            subtitle_output.write(subtitle_content)
                        done_count += 1
                        print 'Done!'
                    except:
                        print 'couldn\'t save subtitle, permissions issue?'
            else:
                print 'Couldn\'t find subtitles in {0} for {1}'.format(sub_language, file_name)
    print '-' * 30 +\
        '\nDownloaded subtitles for {0} out of {1} files'.format(done_count, len(file_list))


def get_hash(name):
    try:
        longlongformat = 'q'  # long long
        bytesize = struct.calcsize(longlongformat)

        f = open(name, "rb")

        filesize = os.path.getsize(name)
        hash = filesize

        if filesize < 65536 * 2:
            return "SizeError"

        for x in range(65536 / bytesize):
            buffer = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, buffer)
            hash += l_value
            hash = hash & 0xFFFFFFFFFFFFFFFF  # to remain as 64bit number

        f.seek(max(0, filesize - 65536), 0)
        for x in range(65536 / bytesize):
            buffer = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, buffer)
            hash += l_value
            hash = hash & 0xFFFFFFFFFFFFFFFF

        f.close()
        returnedhash = "%016x" % hash
        return returnedhash

    except(IOError):
        return None

if __name__ == '__main__':
    valid_files = []

    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=str,
                        help="Folder which will be scanned for allowed video files, and subtitles for those files will be downloaded")
    parser.add_argument("-o", "--overwrite", action="store_true",
                        help="Downloads subtitle file even if subtitle with <video filename>.srt already exists; overwrites existing file")
    parser.add_argument("-l", "--language", type=str,
                        help="Subtitle language, must be an ISO 639-1 Code i.e. (en,fr,de) Default English(en); Full list http://en.wikipedia.org/wiki/List_of_ISO_639-1_codes")
    args = parser.parse_args()

    directory = args.folder
    if not directory.endswith('\\'):
        directory += '\\'
    if args.overwrite:
        overwrite = True
    if args.language:
        if len(args.language) == 2:
            sub_language = args.language.lower()
        else:
            print 'Argument not  ISO 639-1 Code check this for list of valid codes http://en.wikipedia.org/wiki/List_of_ISO_639-1_codes'
            sys.exit()

    names = os.listdir(directory)

    for name in names:
        file_name, file_extension = os.path.splitext(name)
        if file_extension in allowed_file_ext:
            valid_files.append(directory + file_name + file_extension)

    find_and_download(valid_files)
