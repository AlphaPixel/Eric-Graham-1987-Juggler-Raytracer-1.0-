# jug2tga.py

`jug2tga.py` extracts frames from Eric Graham's original Amiga Juggler animation data.

The script is a Python port of Ernie Wright's `jug2tga.c`, dated February 15, 1998. Wright's decoder documented the private Juggler `movie.data` file format and converted the frames to TGA. The original C decoder used `rotate.c`, based on Sue-Ken Yap's 8 by 8 bitmap rotation routine from *Graphics Gems II*, to convert Amiga bitplane data into byte-per-pixel HAM indices.

This Python version keeps the same decoding structure where practical:

- `MOVIE` and `RGB` records
- `frame0`, `frame1`, `buf`, `index`, and `rgb` buffers
- `rotate8x8`
- `unHAM`
- `frame_first`
- `frame_next`
- `save_frame`

Multi-byte fields are read as big-endian values, matching the Amiga 68000 source data.

## Usage

```sh
python tools/jug2tga.py Raytracer_1987_Graham_Source_Code/movie.data
```

By default, the script writes TGA frames to the current directory. Output files use the input file basename:

```text
movie001.tga
movie002.tga
...
```

## Options

```sh
python tools/jug2tga.py movie.data --format tga
python tools/jug2tga.py movie.data --format png
python tools/jug2tga.py movie.data --format webm
python tools/jug2tga.py movie.data --out-dir out/juggler
python tools/jug2tga.py movie.data --scale 4
python tools/jug2tga.py movie.data --format webm --fps 24
```

`--format` may be `tga`, `png`, or `webm`. TGA is the default.

`--out-dir` selects the output directory.

`--scale` applies integer nearest-neighbor scaling before writing output.

`--fps` sets the frame rate for WebM output. It defaults to 30.

## Output formats

TGA output is uncompressed 24-bit truecolor, matching the original C tool's default behavior.

PNG output uses a small built-in PNG writer and does not require Pillow. PNG files include pixel-aspect metadata with a non-square Amiga NTSC-style ratio.

WebM output requires `ffmpeg` on `PATH`. The script streams raw RGB frames to ffmpeg and writes a VP9 WebM file. WebM output includes display-aspect metadata so players that honor it can present the animation with the intended pixel shape.

## Notes

The decoder reconstructs the first full frame, then applies the delta frames using Wright's original section/run structure. The two frame buffers alternate, matching the C implementation.

The HAM conversion follows the C decoder's `unHAM()` logic. The result is written as ordinary RGB image/video data.
