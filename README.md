# deezer-asy
Asynchronous version of the [py-deezer](https://github.com/acgonzales/pydeezer) module
At the moment, the functionality does not completely repeat the original library

### Differences
This version is asynchronous. Otherwise, it repeats the arguments of the original library.


# Last update `2.0.0`
    * Simplified module initialization
    * Changed response type of `download_track` function: {'track': path, 'lyric': path or None}
    


# What works?
* Getting information about albums, playlists, artists, tracks (their tags).
* Downloading tracks.


# What needs to be done
* Adding tags to .flac. `(So ​​far, idling)`

# Installation
```bash
pip install pydeezer-asy
```

# Usage as a package

```python
from deezer_asy import DeezerAsy
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main_logger")
loop = asyncio.get_event_loop()
ARL = "edit this"

async def main():
    # You can pass `loop` as an argument, or leave None
    # If you want logging, pass the `logger` as an argument
    deezer = DeezerAsy(ARL, loop=loop, logger=logger)
    await deezer._generate_main_session()
    track = await deezer.get_track(1421388612, True)
    data = await deezer.download_track(track['info'], './', with_lyrics=True, with_metadata=True)
    print(data)
    # p.s Changed response type of `download_track` function: {'track': path, 'lyric': path or None}



if __name__ == "__main__":
    loop.run_until_complete(main())
```
