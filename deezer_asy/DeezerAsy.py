import aiohttp, asyncio
from yarl import URL
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import mutagen
import aiofiles
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3
from os import path, remove
import hashlib
import httpx
from  threading import Thread

from .constants import *

from .exceptions import LoginError
from .exceptions import APIRequestError
from .exceptions import DownloadLinkDecryptionError

from . import util


class ResultThread(Thread):
    def __init__(self, *args, **kwargs):
        super(ResultThread, self).__init__(*args, **kwargs)
        self._result = None

    def run(self):
        self._result = self._target(*self._args, **self._kwargs)

    def result(self):
        return self._result

class DeezerAsy:
    def __init__(self, arl) -> None:
        """Instantiates a Deezer object

        Keyword Arguments:
            arl {str} -- Login using the given arl (default: {None})
        """

        self.token = None
        self.arl = arl

        self._main_session = aiohttp.ClientSession(headers=networking_settings.HTTP_HEADERS)
        self._main_session.cookie_jar.update_cookies({"arl": self.arl}, response_url=URL(api_urls.DEEZER_URL))



    """
        GENERAL
    """
    async def _generate_main_session(self):
        await self.get_user_data()

    """
        API
    """
    async def get_user_data(self):
        """Gets the data of the user, this will only work arl is the cookie. Make sure you have run login_via_arl() before using this.

        Raises:
            LoginError: Will raise if the arl given is not identified by Deezer
        """

        data = await self._api_call(api_methods.GET_USER_DATA)
        data = data['results']
        self.token = data["checkForm"]

        if not data["USER"]["USER_ID"]:
            raise LoginError("Arl is invalid.")

        raw_user = data["USER"]

        _arl = await self.get_cookies()
        self.cookies = _arl
        
        if raw_user["USER_PICTURE"]:
            self.user = {
                "id": raw_user["USER_ID"],
                "name": raw_user["BLOG_NAME"],
                "arl": _arl["arl"],
                "image": "https://e-cdns-images.dzcdn.net/images/user/{0}/250x250-000000-80-0-0.jpg".format(raw_user["USER_PICTURE"])
            }
        else:
            self.user = {
                "id": raw_user["USER_ID"],
                "name": raw_user["BLOG_NAME"],
                "arl": _arl["arl"],
                "image": "https://e-cdns-images.dzcdn.net/images/user/250x250-000000-80-0-0.jpg"
            }
    async def get_cookies(self):
        """Get cookies in the domain of {api_urls.DEEZER_URL}

        Returns:
            dict -- Cookies
        """

        cookies = self._main_session.cookie_jar.filter_cookies(api_urls.DEEZER_URL)
        if cookies:
            g = {name: cookie.value for name, cookie in cookies.items()}
            return g
        return None
    async def _api_call(self, method, params={}):
        token = "null"
        if method != api_methods.GET_USER_DATA:
            token = self.token

        if self._main_session.closed:
            async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
                response = await session.post(api_urls.API_URL, json=params, params={
                    "api_version": "1.0",
                    "api_token": token,
                    "input": "3",
                    "method": method
                })

                data = response.json()
        else:
            async with self._main_session.post(api_urls.API_URL, json=params, params={
                "api_version": "1.0",
                "api_token": token,
                "input": "3",
                "method": method
            }, cookies=await self.get_cookies()) as response:
                data = await response.json()


        if "error" in data and data["error"]:
            error_type = list(data["error"].keys())[0]
            error_message = data["error"][error_type]
            raise APIRequestError(
                "{0} : {1}".format(error_type, error_message))


        if self.token and not self._main_session.closed:
            await self._main_session.close()

        return data
    async def _legacy_api_call(self, method, params={}):
        url = "{0}/{1}".format(api_urls.LEGACY_API_URL, method)
        
        async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
            response = await session.get(url, params=params)
            data = response.json()

            if "error" in data and data["error"]:
                error_type = list(data["error"].keys())[0]
                error_message = data["error"][error_type]
                raise APIRequestError(
                    "{0} : {1}".format(error_type, error_message))

            return data
    async def _legacy_search(self, method, query, limit=30, index=0):
        query = util.clean_query(query)

        data = await self._legacy_api_call(method, {
            "q": query,
            "limit": limit,
            "index": index
        })

        return data["data"]
    async def get_track_valid_quality(self, track):
        """Gets the valid download qualities of the given track

        Arguments:
            track {dict} -- Track dictionary, similar to the {info} value that is returned {using get_track()}

        Returns:
            list -- List of keys of the valid qualities from the {track_formats.TRACK_FORMAT_MAP}
        """

        track = track["DATA"] if "DATA" in track else track

        qualities = []

        # Fixes issue #4
        for key in [track_formats.MP3_128, track_formats.MP3_320, track_formats.FLAC]:
            download_url = await self.get_track_download_url(
                track, quality=key, fallback=False)


            async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
                res = await session.get(download_url)

                if res.status_code == 200 and int(res.headers["Content-length"]) > 0:
                    qualities.append(key)

        return qualities
    async def _select_valid_quality(self, track, quality):
        valid_qualities = await self.get_track_valid_quality(track)

        if not quality or not quality in valid_qualities:
            default_size = int(track["FILESIZE"])

            for key in track_formats.TRACK_FORMAT_MAP.keys():
                if f"FILESIZE_{key}" in track and int(track[f"FILESIZE_{key}"]) == default_size:
                    quality = track_formats.TRACK_FORMAT_MAP[key]
                    break
        else:
            quality = track_formats.TRACK_FORMAT_MAP[quality]

        return quality
    """
        ALBUM
    """
    async def get_album(self, album_id):
        """Gets the album data of the given {album_id}

        Arguments:
            album_id {str} -- Album Id

        Returns:
            dict -- Album data
        """

        data = await self._legacy_api_call("/album/{0}".format(album_id))

        data["cover_id"] = str(data["cover_small"]).split(
            "cover/")[1].split("/")[0]

        return data
    async def get_album_poster(self, album, size=500, ext="jpg"):
        """Gets the album poster as a binary data

        Arguments:
            album {dict} -- Album data

        Keyword Arguments:
            size {int} -- Size of the image, {size}x{size} (default: {500})
            ext {str} -- Extension of the image, can be ('.jpg' or '.png') (default: {"jpg"})

        Returns:
            bytes -- Binary data of the image
        """
        return await self._get_poster(album["cover_id"], size=size, ext=ext)
    async def _get_poster(self, poster_id, size=500, ext="jpg"):
        ext = ext.lower()
        if ext != "jpg" and ext != "png":
            raise ValueError("Image extension should only be jpg or png!")

        url = f'https://e-cdns-images.dzcdn.net/images/cover/{poster_id}/{size}x{size}.{ext}'
        
        async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
            response = await session.get(url)
            if response.status_code == 200:
                image_bytes = response.content
                
                return {
                    "image": image_bytes,
                    "size": (size, size),
                    "ext": ext,
                    "mime_type": "image/jpeg" if ext == "jpg" else "image/png"
                }
    async def get_album_tracks(self, album_id):
        """Gets the tracks of the given {album_id}

        Arguments:
            album_id {str} -- Album Id

        Returns:
            list -- List of tracks
        """

        data = await self._api_call(api_methods.ALBUM_TRACKS, params={
            "ALB_ID": album_id,
            "NB": -1
        })

        for i, track in enumerate(data["results"]["data"]):
            track["_POSITION"] = i + 1

        return data["results"]["data"]
    async def search_albums(self, query, limit=30, index=0):
        """Searches albums on a given query

        Arguments:
            query {str} -- Query keyword

        Keyword Arguments:
            limit {int} -- Number of results (default: {30})
            index {int} -- Offset (default: {0})

        Returns:
            list -- List of albums
        """

        return await self._legacy_search(api_methods.SEARCH_ALBUM, query, limit=limit, index=index)

    """
        ARTIST
    """
    async def get_artist(self, artist_id):
        """Gets the artist data from the given {artist_id}

        Arguments:
            artist_id {str} -- Artist Id

        Returns:
            dict -- Artist data
        """

        data = await self._api_call(api_methods.PAGE_ARTIST, params={
            "ART_ID": artist_id,
            "LANG": "en"
        })

        return data["results"]
    async def get_artist_poster(self, artist, size=500, ext="jpg"):
        """Gets the artist poster as a binary data

        Arguments:
            artist {dict} -- artist data

        Keyword Arguments:
            size {int} -- Size of the image, {size}x{size} (default: {500})
            ext {str} -- Extension of the image, can be ('.jpg' or '.png') (default: {"jpg"})

        Returns:
            bytes -- Binary data of the image
        """

        if not "ART_PICTURE" in artist and "DATA" in artist:
            artist = artist["DATA"]

        return await self._get_poster(artist["ART_PICTURE"], size=size, ext=ext)
    async def get_artist_discography(self, artist_id):
        """Gets the artist's discography (tracks)

        Arguments:
            artist_id {str} -- Artist Id

        Returns:
            dict -- Artist discography data
        """

        data = await self._api_call(api_methods.ARTIST_DISCOGRAPHY, params={
            "ART_ID": artist_id,
            "NB": 500,
            "NB_SONGS": -1,
            "START": 0
        })

        return data["results"]["data"]
    async def get_artist_top_tracks(self, artist_id):
        """Gets the top tracks of the given artist

        Arguments:
            artist_id {str} -- Artist Id

        Returns:
            list -- List of track
        """

        data = await self._api_call(api_methods.ARTIST_TOP_TRACKS, params={
            "ART_ID": artist_id,
            "NB": 100
        })

        for i, track in enumerate(data["results"]["data"]):
            track["_POSITION"] = i + 1

        return data["results"]["data"]
    async def search_artists(self, query, limit=30, index=0):
        """Searches artists on a given query

        Arguments:
            query {str} -- Query keyword

        Keyword Arguments:
            limit {int} -- Number of tracks (default: {30})
            index {int} -- Offset (default: {0})

        Returns:
            list -- List of artists
        """

        return await self._legacy_search(api_methods.SEARCH_ARTIST, query, limit=limit, index=index)

    """
        PLAYLIST
    """
    async def get_playlist(self, playlist_id):
        """Gets the playlist data from the given playlist_id

        Arguments:
            playlist_id {str} -- Playlist Id

        Returns:
            dict -- Playlist data
        """

        data = await self._api_call(api_methods.PAGE_PLAYLIST, params={
            "playlist_id": playlist_id,
            "LANG": "en"
        })

        return data["results"]
    async def get_playlist_tracks(self, playlist_id):
        """Gets the tracks inside the playlist

        Arguments:
            playlist_id {str} -- Playlist Id

        Returns:
            list -- List of tracks
        """

        data = await self._api_call(api_methods.PLAYLIST_TRACKS, params={
            "PLAYLIST_ID": playlist_id,
            "NB": -1
        })

        for i, track in enumerate(data["results"]["data"]):
            track["_POSITION"] = i + 1

        return data["results"]["data"]
    async def search_playlists(self, query, limit=30, index=0):
        """Searches playlists on a given query

        Arguments:
            query {str} -- Query keyword

        Keyword Arguments:
            limit {int} -- Number of tracks (default: {30})
            index {int} -- Offset (default: {0})

        Returns:
            list -- List of playlists
        """

        return await self._legacy_search(api_methods.SEARCH_PLAYLIST, query, limit=limit, index=index)

    """
        TRACKS
    """
    async def search_tracks(self, query, limit=30, index=0):
        """Searches tracks on a given query

        Arguments:
            query {str} -- Query keyword

        Keyword Arguments:
            limit {int} -- Number of results (default: {30})
            index {int} -- Offset (default: {0})

        Returns:
            list -- List of tracks
        """

        return await self._legacy_search(api_methods.SEARCH_TRACK, query, limit=limit, index=index)
    async def get_track_tags(self, track, separator=", ", with_cover:bool=True):
        """Gets the possible ID3 tags of the track.

        Arguments:
            track {dict} -- Track dictionary, similar to the {info} value that is returned {using get_track()}

        Keyword Arguments:
            separator {str} -- Separator to separate multiple artists (default: {", "})

        Returns:
            dict -- Tags
        """

        track = track["DATA"] if "DATA" in track else track

        album_data = await self.get_album(track["ALB_ID"])

        if "main_artist" in track["SNG_CONTRIBUTORS"]:
            main_artists = track["SNG_CONTRIBUTORS"]["main_artist"]
            artists = main_artists[0]
            for i in range(1, len(main_artists)):
                artists += separator + main_artists[i]
        else:
            artists = track["ART_NAME"]

        title = track["SNG_TITLE"]

        if "VERSION" in track and track["VERSION"] != "":
            title += " " + track["VERSION"]

        def should_include_featuring():
            feat_keywords = ["feat.", "featuring", "ft."]

            for keyword in feat_keywords:
                if keyword in title.lower():
                    return False
            return True

        if should_include_featuring() and "featuring" in track["SNG_CONTRIBUTORS"]:
            featuring_artists_data = track["SNG_CONTRIBUTORS"]["featuring"]
            featuring_artists = featuring_artists_data[0]
            for i in range(1, len(featuring_artists_data)):
                featuring_artists += separator + featuring_artists_data[i]

            title += f" (feat. {featuring_artists})"

        total_tracks = album_data["nb_tracks"]
        track_number = str(track["TRACK_NUMBER"]) + "/" + str(total_tracks)

        if with_cover:
            cover = await self.get_album_poster(album_data, size=1000)

        tags = {
            "title": title,
            "artist": artists,
            "genre": None,
            "album": track["ALB_TITLE"],
            "albumartist": track["ART_NAME"],
            "label": album_data["label"],
            "date": track["PHYSICAL_RELEASE_DATE"],
            "discnumber": track["DISK_NUMBER"],
            "tracknumber": track_number,
            "isrc": track["ISRC"],
            "copyright": track["COPYRIGHT"],
            "_albumart": cover if with_cover else None,
        }

        if len(album_data["genres"]["data"]) > 0:
            tags["genre"] = album_data["genres"]["data"][0]["name"]

        if "author" in track["SNG_CONTRIBUTORS"]:
            _authors = track["SNG_CONTRIBUTORS"]["author"]

            authors = _authors[0]
            for i in range(1, len(_authors)):
                authors += separator + _authors[i]

            tags["author"] = authors

        return tags
    async def get_track(self, track_id, with_cover:bool=True):
        """Gets the track info using the Deezer API

        Arguments:
            track_id {str} -- Track Id

        Returns:
            dict -- Dictionary that contains the {info}, {download} partial function, {tags}, and {get_tag} partial function.
        """

        method = api_methods.SONG_GET_DATA
        params = {
            "SNG_ID": track_id
        }

        if not int(track_id) < 0:
            method = api_methods.PAGE_TRACK

        data = await self._api_call(method, params=params)
        data = data["results"]

        return {
            "info": data,
            "tags": await self.get_track_tags(data, with_cover=with_cover),
        }
    async def get_track_download_url(self, track, quality=None, fallback=True, renew=False, **kwargs):
        """Gets and decrypts the download url of the given track in the given quality

        Arguments:
            track {dict} -- Track dictionary, similar to the {info} value that is returned {using get_track()}

        Keyword Arguments:
            quality {str} -- Use values from {track_formats}, will get the default quality if None or an invalid is given. (default: {None})
            fallback {bool} -- Set to True to if you want to use fallback qualities when the given quality is not available. (default: {False})
            renew {bool} -- Will renew the track object (default: {False})

        Raises:
            DownloadLinkDecryptionError: Will be raised if the track dictionary does not have an MD5
            ValueError: Will be raised if valid track argument was given

        Returns:
            str -- Download url
        """

        if renew:
            track = await self.get_track(track["SNG_ID"])
            track = track["info"]

        if not quality:
            quality = track_formats.MP3_128
            fallback = True

        try:
            track = track["DATA"] if "DATA" in track else track

            if not "MD5_ORIGIN" in track:
                raise DownloadLinkDecryptionError(
                    "MD5 is needed to decrypt the download link.")

            md5_origin = track["MD5_ORIGIN"]
            track_id = track["SNG_ID"]
            media_version = track["MEDIA_VERSION"]
        except ValueError:
            raise ValueError(
                "You have passed an invalid argument. This method needs the \"DATA\" value in the dictionary returned by the get_track() method.")

        def decrypt_url(quality_code):
            magic_char = "¤"
            step1 = magic_char.join((md5_origin,
                                     str(quality_code),
                                     track_id,
                                     media_version))
            m = hashlib.md5()
            m.update(bytes([ord(x) for x in step1]))

            step2 = m.hexdigest() + magic_char + step1 + magic_char
            step2 = step2.ljust(80, " ")

            cipher = Cipher(algorithms.AES(bytes('jo6aey6haid2Teih', 'ascii')),
                            modes.ECB(), default_backend())

            encryptor = cipher.encryptor()
            step3 = encryptor.update(bytes([ord(x) for x in step2])).hex()

            cdn = track["MD5_ORIGIN"][0]

            return f'https://e-cdns-proxy-{cdn}.dzcdn.net/mobile/1/{step3}'

        url = decrypt_url(track_formats.TRACK_FORMAT_MAP[quality]["code"])


        async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
            response = await session.get(url)
            if not fallback or (response.status_code == 200 and int(response.headers.get("Content-Length", 0)) > 0):
                return (url, quality)
            else:
                if "fallback_qualities" in kwargs:
                    fallback_qualities = kwargs["fallback_qualities"]
                else:
                    fallback_qualities = track_formats.FALLBACK_QUALITIES

                for key in fallback_qualities:
                    url = decrypt_url(
                        track_formats.TRACK_FORMAT_MAP[key]["code"])

                    async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as session:
                        response = await session.get(url)
                    #async with self._main_session.get(url, cookies=self.get_cookies()) as response:
                        if not fallback or (response.status_code == 200 and int(response.headers.get("Content-Length", 0)) > 0):
                            return (url, key)  
    async def download_track(self, track, download_dir, quality=None, fallback=True, filename=None, renew=False,
            with_metadata=True, with_lyrics=True, tag_separator=", ", **kwargs):
        
        """Downloads the given track

        Arguments:
            track {dict} -- Track dictionary, similar to the {info} value that is returned {using get_track()}
            download_dir {str} -- Directory (without {filename}) where the file is to be saved.

        Keyword Arguments:
            quality {str} -- Use values from {constants.track_formats}, will get the default quality if None or an invalid is given. (default: {None})
            filename {str} -- Filename with or without the extension (default: {None})
            renew {bool} -- Will renew the track object (default: {False})
            with_metadata {bool} -- If true, will write id3 tags into the file. (default: {True})
            with_lyrics {bool} -- If true, will find and save lyrics of the given track. (default: {True})
            tag_separator {str} -- Separator to separate multiple artists (default: {", "})
        """

        ###########################
        if with_lyrics:
            if "LYRICS" in track:
                lyric_data = track["LYRICS"]
            else:
                try:
                    if "DATA" in track:
                        lyric_data = await self.get_track_lyrics(
                            track["DATA"]["SNG_ID"])["info"]
                    else:
                        lyric_data = await self.get_track_lyrics(
                            track["SNG_ID"])["info"]
                except APIRequestError:
                    with_lyrics = False

        track = track["DATA"] if "DATA" in track else track
        tags = await self.get_track_tags(track, separator=tag_separator, with_cover=False)
        url, quality_key = await self.get_track_download_url(
            track, quality, fallback=fallback, renew=renew, **kwargs)
        blowfish_key = util.get_blowfish_key(track["SNG_ID"])

        quality = track_formats.TRACK_FORMAT_MAP[quality_key]
        title = tags["title"]
        ext = quality["ext"]

        if not filename:
            filename =  title + ext
        if not str(filename).endswith(ext):
            filename += ext

        filename = util.clean_filename(filename)
        download_dir = path.normpath(download_dir)
        download_path = path.join(download_dir, filename)
        util.create_folders(download_dir)
        chunk_size = 2 * 1024

        async with httpx.AsyncClient(headers=networking_settings.HTTP_HEADERS, cookies=self.cookies) as client:
            res = await client.get(url, follow_redirects=True)
            data_iter = res.iter_bytes(chunk_size)
            i = 0
            async with aiofiles.open(download_path, 'wb') as f:
                f.seek(0)
            
                for chunk in data_iter:
                    if i % 3 > 0:
                        await f.write(chunk)
                    elif len(chunk) < chunk_size:
                        await f.write(chunk)
                        break
                    else:
                        cipher = Cipher(algorithms.Blowfish(blowfish_key),
                                    modes.CBC(
                                        bytes([i for i in range(8)])),
                                    default_backend())

                        decryptor = cipher.decryptor()
                        dec_data = decryptor.update(
                            chunk) + decryptor.finalize()

                        await f.write(dec_data)

                    i += 1

        if with_metadata:
            if ext.lower() == ".flac":
                pass #self._write_flac_tags(download_path, track, tags=tags)
            else:
                await self._write_mp3_tags(download_path, track, tags=tags)
        if with_lyrics:
            lyrics_path = path.join(download_dir, filename[:-len(ext)])
            lyric_check = await self.save_lyrics(lyric_data, lyrics_path)
            if not lyric_check[0]:
                asyncio.get_event_loop().run_in_executor(None, remove, lyric_check[1])
                return (download_path)

            return (download_path, lyric_check[1])

        return (download_path)
    
    async def get_tracks(self, track_ids):
        """Gets the list of the tracks that corresponds with the given {track_ids}

        Arguments:
            track_ids {list} -- List of track id

        Returns:
            dict -- List of tracks
        """

        data = await self._api_call(api_methods.SONG_GET_LIST_DATA, params={
            "SNG_IDS": track_ids
        })

        data = data["results"]
        valid_ids = [str(song["SNG_ID"]) for song in data["data"]]

        data["errors"] = []
        for id in track_ids:
            if not str(id) in valid_ids:
                data["errors"].append(id)

        return data

    """
        LYRIC
    """
    async def get_track_lyrics(self, track_id):
        """Gets the lyrics data of the given {track_id}

        Arguments:
            track_id {str} -- Track Id

        Returns:
            dict -- Dictionary that containts the {info}, and {save} partial function.
        """

        data = await self._api_call(api_methods.SONG_LYRICS, params={
            "SNG_ID": track_id
        })
        data = data["results"]

        return {
            "info": data
        }
    async def save_lyrics(self, lyric_data, save_path):
        """Saves the {lyric_data} into a .lrc file.

        Arguments:
            lyric_data {dict} -- The 'info' value returned from {get_track_lyrics()}
            save_path {str} -- Full path on where the file is to be saved

        Returns:
            bool -- Operation success
        """

        filename = path.basename(save_path)
        filename = util.clean_filename(filename)
        save_path = path.join(path.dirname(save_path), filename)

        if not str(save_path).endswith(".lrc"):
            save_path += ".lrc"

        util.create_folders(path.dirname(save_path))

        async with aiofiles.open(save_path, 'w', encoding="utf-8") as f:
            if not "LYRICS_SYNC_JSON" in lyric_data:
                return (False, save_path)

            sync_data = lyric_data["LYRICS_SYNC_JSON"]

            for line in sync_data:
                if str(line["line"]):
                    f.write("{0}{1}".format(
                        line["lrc_timestamp"], line["line"]))
                f.write("\n")

        return (True, save_path)
    
    """
        TAG EDIT

        p.s: It might be blocking the thread, not sure
    """
    async def __write_mp3_tags(self, path, track, tags=None):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _result = loop.run_until_complete(self._write_mp3_tags(path, track, tags))
        result = await _result

        return result
    
    def __update_mp3(self, path, tags):
        audio = mutagen.File(path, easy=True)
        if audio is None:
            raise ValueError("Invalid file format")

        audio.delete()
        EasyID3.RegisterTextKey("label", "TPUB")

        cover = tags["_albumart"]
        del tags["_albumart"]

        for key, val in tags.items():
            if val:
                audio[key] = str(val)
        

        if cover:
            cover_handle = ID3(path)
            cover_handle["APIC"] = APIC(
                type=3,
                mime=cover["mime_type"],
                data=cover["image"]
            )
            cover_handle.save(path)
        audio.save()

    async def _write_mp3_tags(self, path, track, tags=None):
        track = track["DATA"] if "DATA" in track else track

        if not tags:
            tags = await self.get_track_tags(track)

        _update_tags = ResultThread(target=self.__update_mp3, args=(path, tags,))
        _update_tags.start()
        _update_tags.join()
        return True