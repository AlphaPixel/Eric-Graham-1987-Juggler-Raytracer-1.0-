# ss-convert.py

`ss-convert.py` converts the still images displayed by Eric Graham's Amiga `ss` program.

The `ss` file itself is an Amiga Hunk executable named `SS: Ray Tracing Display Program`. The still image files are separate payloads, including `dragon` and `ele` from the original Raytracer 1.0 disk.

Those still files are not IFF/ILBM images. Each file contains:

- image width, big-endian 16-bit
- image height, big-endian 16-bit
- 16-entry HAM palette, stored as 4-bit red, green, blue byte triplets
- six contiguous Amiga bitplanes of image data

The converter is a stripped-down sibling of `jug2tga.py`. It uses the same basic bitplane rotation and HAM-to-RGB conversion logic adapted from Ernie Wright's `jug2tga.c` and `rotate.c`, but it reads one still image rather than a Juggler animation stream.

## Usage

```sh
python tools/ss-convert.py Raytracer_1987_Graham_Source_Code/dragon
python tools/ss-convert.py Raytracer_1987_Graham_Source_Code/ele
```

By default, the script writes an uncompressed 24-bit TGA image in the current directory. Output filenames use the input basename:

```text
dragon.tga
ele.tga
```

## Options

```sh
python tools/ss-convert.py dragon --format tga
python tools/ss-convert.py dragon --format png
python tools/ss-convert.py dragon --out-dir out/stills
python tools/ss-convert.py dragon --scale 4
```

`--format` may be `tga` or `png`. TGA is the default.

`--out-dir` selects the output directory.

`--scale` applies integer nearest-neighbor scaling before writing output.

## Pixel Aspect

PNG output includes `pHYs` pixel-aspect metadata for a non-square Amiga NTSC-style presentation. TGA output has no standard pixel-aspect metadata in this implementation.

Scaling changes the stored image dimensions but preserves the same pixel-aspect metadata for PNG output.

## Notes

The converter reads Amiga multi-byte values as big-endian, matching the 68000 platform.

The output is ordinary RGB image data. The original HAM palette and per-pixel HAM modifications are resolved during conversion.
