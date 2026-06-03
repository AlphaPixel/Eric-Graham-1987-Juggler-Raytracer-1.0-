#!/usr/bin/env python3
"""
Convert Eric Graham Raytracer still image files displayed by ss.

This is a stripped-down sibling of jug2tga.py for files such as dragon
and ele.  The files contain a 320 x 200 HAM palette image, not an IFF.
"""

import argparse
import binascii
import struct
import sys
import zlib
from pathlib import Path


class RGB:
    def __init__(self, red=0, green=0, blue=0):
        self.red = red
        self.green = green
        self.blue = blue


class IMAGE:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.pal = [RGB() for _ in range(16)]


frame0 = bytearray(48000)
buf = bytearray(48000)
index = bytearray(320)
rgb = bytearray(960)

out_format = "tga"
out_dir = Path(".")
out_base = "image"
scale = 1
pixel_aspect_x = 86
pixel_aspect_y = 100


def bgr_to_rgb(pixels):
    data = bytearray(len(pixels))
    for i in range(0, len(pixels), 3):
        data[i + 0] = pixels[i + 2]
        data[i + 1] = pixels[i + 1]
        data[i + 2] = pixels[i + 0]
    return data


def png_chunk(name, data):
    chunk = name + data
    return (
        struct.pack(">L", len(data))
        + chunk
        + struct.pack(">L", binascii.crc32(chunk) & 0xffffffff)
    )


def scaled_size(img):
    return img.width * scale, img.height * scale


def scale_bgr(img, pixels):
    if scale == 1:
        return pixels

    width, height = scaled_size(img)
    data = bytearray(width * height * 3)
    src_stride = img.width * 3
    dst_stride = width * 3

    for y in range(height):
        src_y = y // scale
        src_row = pixels[src_y * src_stride:(src_y + 1) * src_stride]
        dst_row = bytearray(dst_stride)
        for x in range(width):
            src = (x // scale) * 3
            dst = x * 3
            dst_row[dst:dst + 3] = src_row[src:src + 3]
        data[y * dst_stride:(y + 1) * dst_stride] = dst_row

    return data


def rotate8x8(src, srcpos, srcstep, dst, dstpos, dststep):
    for row in range(8):
        v = src[srcpos + row * srcstep]
        for col in range(8):
            if v & (0x80 >> col):
                dst[dstpos + col * dststep] |= 1 << row


def write_tgahdr(img, fp):
    width, height = scaled_size(img)
    hdr = bytearray(18)
    hdr[2] = 2
    hdr[12:14] = struct.pack("<H", width)
    hdr[14:16] = struct.pack("<H", height)
    hdr[16] = 24
    hdr[17] = 0x20
    fp.write(hdr)
    return True


def unHAM(img, src, dst):
    prev = RGB()
    hbits = 4
    mbits = 8 - hbits
    mask = (1 << hbits) - 1

    for i in range(img.width):
        j = src[i]
        if j >> hbits == 0:
            dst[0] = img.pal[j & mask].blue
            dst[1] = img.pal[j & mask].green
            dst[2] = img.pal[j & mask].red
        elif j >> hbits == 1:
            dst[0] = ((j & mask) << mbits) | (j & mask)
            dst[1] = prev.green
            dst[2] = prev.red
        elif j >> hbits == 2:
            dst[0] = prev.blue
            dst[1] = prev.green
            dst[2] = ((j & mask) << mbits) | (j & mask)
        elif j >> hbits == 3:
            dst[0] = prev.blue
            dst[1] = ((j & mask) << mbits) | (j & mask)
            dst[2] = prev.red

        prev.red = dst[2]
        prev.green = dst[1]
        prev.blue = dst[0]
        dst = memoryview(dst)[3:]


def frame_to_bgr(img):
    pixels = bytearray(img.width * img.height * 3)
    rowbytes = img.width // 8

    for j in range(img.height):
        buf[:img.width] = b"\0" * img.width
        index[:img.width] = b"\0" * img.width
        buf[:rowbytes * 6] = frame0[j * rowbytes * 6:(j + 1) * rowbytes * 6]
        for i in range(rowbytes):
            k = i * 8
            rotate8x8(buf, i, rowbytes, index, k, 1)
        row = memoryview(pixels)[j * img.width * 3:(j + 1) * img.width * 3]
        unHAM(img, index, row)

    return pixels


def save_tga(img, pixels):
    name = out_dir / f"{out_base}.tga"
    pixels = scale_bgr(img, pixels)
    with name.open("wb") as fp:
        write_tgahdr(img, fp)
        fp.write(pixels)
    return True


def save_png(img, pixels):
    width, height = scaled_size(img)
    name = out_dir / f"{out_base}.png"
    pixels = scale_bgr(img, pixels)
    data = bgr_to_rgb(pixels)
    rows = bytearray()
    stride = width * 3

    for y in range(height):
        rows.append(0)
        rows.extend(data[y * stride:(y + 1) * stride])

    with name.open("wb") as fp:
        fp.write(b"\x89PNG\r\n\x1a\n")
        fp.write(png_chunk(b"IHDR", struct.pack(">LLBBBBB", width, height, 8, 2, 0, 0, 0)))
        fp.write(png_chunk(b"pHYs", struct.pack(">LLB", pixel_aspect_y, pixel_aspect_x, 0)))
        fp.write(png_chunk(b"IDAT", zlib.compress(bytes(rows), 9)))
        fp.write(png_chunk(b"IEND", b""))
    return True


def save_frame(img):
    pixels = frame_to_bgr(img)
    if out_format == "tga":
        return save_tga(img, pixels)
    if out_format == "png":
        return save_png(img, pixels)
    return False


def read_image(fp):
    img = IMAGE()

    data = fp.read(4)
    if len(data) != 4:
        raise EOFError("Couldn't read image header.")
    img.width, img.height = struct.unpack(">HH", data)

    data = fp.read(16 * 3)
    if len(data) != 16 * 3:
        raise EOFError("Couldn't read HAM palette.")
    for i in range(16):
        img.pal[i].red = data[i * 3 + 0] * 17
        img.pal[i].green = data[i * 3 + 1] * 17
        img.pal[i].blue = data[i * 3 + 2] * 17

    rowbytes = img.width // 8
    frame_size = img.height * rowbytes * 6
    data = fp.read(frame_size)
    if len(data) != frame_size:
        raise EOFError("Couldn't read image bitplanes.")

    for i in range(6):
        k = rowbytes * i
        n = img.height * rowbytes * i
        for j in range(img.height):
            frame0[k:k + rowbytes] = data[n:n + rowbytes]
            k += rowbytes * 6
            n += rowbytes

    return img


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Convert Eric Graham ss still images such as dragon and ele."
    )
    parser.add_argument("image", help="ss still image file, such as dragon or ele")
    parser.add_argument(
        "--format",
        choices=("tga", "png"),
        default="tga",
        help="output format, default: tga",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="directory for output image, default: current directory",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="nearest-neighbor integer scale factor, default: 1",
    )
    return parser.parse_args(argv)


def main(argv=None):
    global out_format, out_dir, out_base, scale

    args = parse_args(argv or sys.argv[1:])
    if args.scale < 1:
        print("--scale must be 1 or greater", file=sys.stderr)
        return 1

    out_format = args.format
    out_dir = Path(args.out_dir)
    out_base = Path(args.image).stem
    scale = args.scale
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(args.image, "rb") as fp:
            img = read_image(fp)
            if not save_frame(img):
                print("Couldn't save image.")
                return 0
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
