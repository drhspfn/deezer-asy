# deezer-asy
Asynchronous version of the [py-deezer](https://github.com/acgonzales/pydeezer) module
At the moment, the functionality does not completely repeat the original library

### Differences
This version is asynchronous. Otherwise, it repeats the arguments of the original library.


# Last update `2.2.5`
 * Simplified module initialization
 * Changed response type of `download_track` function: `{'track': path, 'lyric': path or None}`
 * Added `httpx` support to replace `aiohttp`*. Specify during initialization: `DeezerAsy(ARL, _httpx=True)`
 * Minor changes regarding cookies `(Not sure but queries should work in both cases)`
 * Fixed tags (load cover)
 * The module has two versions. Changes in both deal with bugs with `aiohttp`. [More]()


# What works?
* Getting information about albums, playlists, artists, tracks (their tags).
* Downloading tracks.


# What needs to be done
* Adding tags to .flac. `(So ​​far, idling)`

# Installation
```bash
pip install pydeezer-asy
```

# Usage
## General
```
You can pass `loop` as an argument, or leave None
If you want logging, pass the `logger` as an argument
```
1) `DeezerAsy` - _httpx parameter during initialization. Replacing the module for asynchronous requests with `httpx`
2) `aioDeezer` - The `aio_session` parameter on initialization. Pass an instance of aiohttp.ClientSession into it

### Usage DeezerAsy
```python
from deezer_asy import DeezerAsy
import logging
import asyncio


ARL = "edit this"
loop = asyncio.get_event_loop()
logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main_logger")

deezer = DeezerAsy(ARL, loop=loop, logger=logger, _httpx=True)

async def main():
    search_data = await deezer.search_tracks('post malone rockstar', 1)
    track_data = await deezer.get_track(search_data[0]['id'], False)
    download = await deezer.download_track(track_data['info'], './', with_lyrics=True, with_metadata=True)
    print(download)
    # Output: {'track': '.\\rockstar (feat. 21 Savage).mp3', 'lyruc': '.\\rockstar (feat. 21 Savage).lrc'}

    await deezer.close_session() # Closing session

if __name__ == "__main__":
    loop.run_until_complete(main())
```


### Usage aioDeezer
```python
from deezer_asy import DeezerAsy
import logging
import asyncio


ARL = "edit this"
loop = asyncio.get_event_loop()
aio_session = aiohttp.ClientSession()
logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main_logger")

deezer = aioDeezer(ARL, loop=loop, logger=logger, aio_session=aio_session)

async def main():
    search_data = await deezer.search_tracks('post malone rockstar', 1)
    track_data = await deezer.get_track(search_data[0]['id'], False)
    download = await deezer.download_track(track_data['info'], './', with_lyrics=True, with_metadata=True)
    print(download)
    # Output: {'track': '.\\rockstar (feat. 21 Savage).mp3', 'lyruc': '.\\rockstar (feat. 21 Savage).lrc'}

    await deezer.close_session() # Closing session

if __name__ == "__main__":
    loop.run_until_complete(main())
```
