# deezer-asy
Asynchronous version of the [py-deezer](https://github.com/acgonzales/pydeezer) module


At the moment, the functionality does not completely repeat the original library


# Differences
This version is asynchronous. Otherwise, it repeats the arguments of the original library.

All that differs is initialization. You need to create a session that will get some information from your ARL, 
`await deezer._generate_main_session()` is responsible for this. 

It must be called when you start your application, in `on_startup` in your bot, or otherwise


# What works?
* Getting information about albums, tracks (their tags).
* Downloading tracks.

## Installation
```bash
pip install pydeezer-asy
```

## Usage as a package

```python
from deezer_asy import DeezerAsy
import asyncio

ARL = "edit this"

async def main():
    deezer = DeezerAsy(ARL)
    await deezer._generate_main_session()
    track = await deezer.get_track(1421388612, True)
    data = await deezer.download_track(track['info'], './', with_lyrics=True, with_metadata=True)
    print(data)



if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```
