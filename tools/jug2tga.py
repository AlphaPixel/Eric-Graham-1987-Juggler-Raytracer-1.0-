#!/usr/bin/env python3
"""
Extract frames from Eric Graham's original Juggler animation.

This is a Python port of Ernie Wright's jug2tga.c.  The decoder keeps
the C implementation's structure and variable names where practical.
"""

import argparse
import binascii
import struct
import subprocess
import sys
import zlib
from pathlib import Path


class RGB:
    def __init__(self, red=0, green=0, blue=0):
        self.red = red
        self.green = green
        self.blue = blue


class MOVIE:
    def __init__(self):
        self.nframes = 0
        self.width = 0
        self.height = 0
        self.pal = [RGB() for _ in range(16)]


frame0 = bytearray(48000)
frame1 = bytearray(48000)
buf = bytearray(48000)
index = bytearray(320)
rgb = bytearray(960)

out_format = "tga"
out_dir = Path(".")
out_base = "juglr"
scale = 1
webm_frames = []
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


def scaled_size(mov):
    return mov.width * scale, mov.height * scale


def scaled_display_size(mov):
    width, height = scaled_size(mov)
    return max(1, round(width * pixel_aspect_x / pixel_aspect_y)), height


def scale_bgr(mov, pixels):
    if scale == 1:
        return pixels

    width, height = scaled_size(mov)
    data = bytearray(width * height * 3)
    src_stride = mov.width * 3
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


def write_tgahdr(mov, fp):
    width, height = scaled_size(mov)
    hdr = bytearray(18)
    hdr[2] = 2
    hdr[12:14] = struct.pack("<H", width)
    hdr[14:16] = struct.pack("<H", height)
    hdr[16] = 24
    hdr[17] = 0x20
    fp.write(hdr)
    return True


def unHAM(mov, src, dst):
    prev = RGB()
    hbits = 4
    mbits = 8 - hbits
    mask = (1 << hbits) - 1

    for i in range(mov.width):
        j = src[i]
        if j >> hbits == 0:
            dst[0] = mov.pal[j & mask].blue
            dst[1] = mov.pal[j & mask].green
            dst[2] = mov.pal[j & mask].red
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


def frame_to_bgr(mov, n):
    f = frame1 if ((n - 1) % 2) else frame0
    pixels = bytearray(mov.width * mov.height * 3)

    for j in range(mov.height):
        buf[:320] = b"\0" * 320
        index[:mov.width] = b"\0" * mov.width
        buf[:240] = f[j * 240:j * 240 + 240]
        for i in range(40):
            k = i * 8
            rotate8x8(buf, i, 40, index, k, 1)
        row = memoryview(pixels)[j * mov.width * 3:(j + 1) * mov.width * 3]
        unHAM(mov, index, row)

    return pixels


def save_tga(mov, n, pixels):
    name = out_dir / f"{out_base}{n:03d}.tga"
    pixels = scale_bgr(mov, pixels)
    with name.open("wb") as fp:
        write_tgahdr(mov, fp)
        fp.write(pixels)
    return True


def save_png(mov, n, pixels):
    width, height = scaled_size(mov)
    name = out_dir / f"{out_base}{n:03d}.png"
    pixels = scale_bgr(mov, pixels)
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


def save_webm_frame(mov, n, pixels):
    pixels = scale_bgr(mov, pixels)
    webm_frames.append(bytes(bgr_to_rgb(pixels)))
    return True


def save_frame(mov, n):
    pixels = frame_to_bgr(mov, n)
    if out_format == "tga":
        return save_tga(mov, n, pixels)
    if out_format == "png":
        return save_png(mov, n, pixels)
    if out_format == "webm":
        return save_webm_frame(mov, n, pixels)
    return False


def frame_first(mov, fp):
    global frame0, frame1, buf

    for i in range(6):
        data = fp.read(8000)
        if len(data) != 8000:
            raise EOFError("Couldn't read first frame.")
        buf[:8000] = data
        k = 40 * i
        n = 0
        for j in range(200):
            frame0[k:k + 40] = buf[n:n + 40]
            k += 240
            n += 40

    frame1[:] = frame0
    return save_frame(mov, 1)


def frame_next(mov, fp, fnum):
    global buf

    f = frame1 if ((fnum - 1) % 2) else frame0

    data = fp.read(4)
    if len(data) != 4:
        raise EOFError("Couldn't read delta size.")
    size = struct.unpack(">L", data)[0]
    data = fp.read(size)
    if len(data) != size:
        raise EOFError("Couldn't read delta frame.")
    buf[:size] = data

    b = 0
    for i in range(5):
        b += 4
        w = 10 - 2 * i
        c = struct.unpack(">H", buf[b:b + 2])[0]
        b += 2

        for j in range(c):
            offset = struct.unpack(">H", buf[b:b + 2])[0]
            b += 2

            y = offset // 40
            x = offset - y * 40
            for k in range(6):
                if x >= 0 and x + w <= 40:
                    dst = y * 240 + k * 40 + x
                    f[dst:dst + w] = buf[b:b + w]
                b += w

    return save_frame(mov, fnum)


def write_webm(mov, fps):
    if not webm_frames:
        return

    ffmpeg = "ffmpeg"
    width, height = scaled_size(mov)
    display_width, display_height = scaled_display_size(mov)
    output = out_dir / f"{out_base}.webm"
    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libvpx-vp9",
        "-aspect",
        f"{display_width}:{display_height}",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None
        for frame in webm_frames:
            proc.stdin.write(frame)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed while writing WEBM")
    except FileNotFoundError as exc:
        raise RuntimeError("WEBM output requires ffmpeg on PATH") from exc


def read_movie(fp):
    mov = MOVIE()
    data = fp.read(8)
    if len(data) != 8:
        raise EOFError("Couldn't read movie header.")
    mov.nframes, mov.width, mov.height = struct.unpack(">LHH", data)

    data = fp.read(16 * 3)
    if len(data) != 16 * 3:
        raise EOFError("Couldn't read HAM palette.")
    for i in range(16):
        mov.pal[i].red = data[i * 3 + 0] * 17
        mov.pal[i].green = data[i * 3 + 1] * 17
        mov.pal[i].blue = data[i * 3 + 2] * 17

    return mov


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Extract frames from Eric Graham's original Juggler animation."
    )
    parser.add_argument("movie", help="movie.data file")
    parser.add_argument(
        "--format",
        choices=("tga", "png", "webm"),
        default="tga",
        help="output format, default: tga",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="directory for output frames or WEBM file, default: current directory",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="WEBM frame rate, default: 30",
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
    out_base = Path(args.movie).stem
    scale = args.scale
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(args.movie, "rb") as fp:
            mov = read_movie(fp)

            if not frame_first(mov, fp):
                print("Couldn't save frame 1.")
                return 0

            for i in range(1, mov.nframes):
                if not frame_next(mov, fp, i + 1):
                    print(f"Couldn't save frame {i + 1}.")
                    return 0

        if out_format == "webm":
            write_webm(mov, args.fps)

    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
