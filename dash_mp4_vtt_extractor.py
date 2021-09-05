  
'''
作者: weimo
创建日期: 2020-09-13 13:32:00
上次编辑时间: 2020-12-16 22:45:24
一个人的命运啊,当然要靠自我奋斗,但是...
'''

import math
import struct
from enum import Enum
from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser

TIMESCALE = 1000


def format_time(tm: int) -> str:
    return datetime.utcfromtimestamp(tm).strftime('%H:%M:%S.%f')[:-3]


def bit_right_shift(ac, n):
    return ((ac + 0x100000000) >> n) & 255 if ac > 0 else ac >> n


def generate_vtt_file(fpath: Path, vtts: list):
    if len(vtts) == 0:
        print("no vtt subtitle was founded TAT.")
    separators = "\n" * 2
    first_line = "WEBVTT"
    lines = dict()
    for vtt in vtts:
        line_number = vtt["line"]
        if lines.get(line_number) is None:
            lines.update({
                line_number: {
                    "startTime": vtt["startTime"],
                    "currentTime": vtt["currentTime"],
                    "settings": vtt["settings"],
                    "subtitle": vtt["subtitle"],
                }
            })
            continue
        if lines[line_number]["startTime"] > vtt["startTime"]:
            lines[line_number]["startTime"] = vtt["startTime"]
        if lines[line_number]["currentTime"] < vtt["currentTime"]:
            lines[line_number]["currentTime"] = vtt["currentTime"]
        if lines[line_number]["subtitle"] != vtt["subtitle"]:
            lines[line_number]["subtitle"] = lines[line_number]["subtitle"] + vtt["subtitle"]
    line_values = list(lines.values())
    line_values = sorted(line_values, key=lambda line: line["startTime"])
    texts = [first_line]
    for line in line_values:
        startTime = format_time(line["startTime"])
        currentTime = format_time(line["currentTime"])
        text = f"{startTime}  --> {currentTime} {line['settings']}\n{line['subtitle']}"
        texts.append(text)
    fpath.write_text(separators.join(texts), encoding="utf-8")
    print(f"vtt file path is {str(fpath)}")
    print(f"{len(texts)-1} lines of vtt subtitles were founded. (*^▽^*)")


class BoxType(Enum):
    BASIC_BOX = 0
    FULL_BOX = 1


class Endianness(Enum):
    BIG_ENDIAN = 0
    LITTLE_ENDIAN = 1


class ParsedTRUNSample(object):
    def __init__(self):
        self.sampleDuration = None
        self.sampleSize = None
        self.sampleCompositionTimeOffset = None


class ParsedBox(object):
    def __init__(self, **kwargs):
        self.parser: VTTParser = kwargs["parser"]
        self.partial_okay: bool = kwargs["partial_okay"]
        self.version: int = kwargs["version"]
        self.flags: int = kwargs["flags"]
        self.viewer: memoryview = kwargs["viewer"]
        self.size: int = kwargs["size"]
        self.start: int = kwargs["start"]


class Viewer(object):

    def __init__(self, buffer: bytes):
        self.buffer = memoryview(buffer)
        self.length = len(self.buffer)
        self.offset = 0

    def readInt32(self) -> int:
        num, = struct.unpack_from("!l", self.buffer, offset=self.offset)
        self.offset += 4
        return num

    def readUint32(self) -> int:
        num, = struct.unpack_from("!L", self.buffer, offset=self.offset)
        self.offset += 4
        # print(sys._getframe().f_back.f_code.co_name, "call readUint32", self.offset, 4)
        return num

    def readUint64(self) -> int:
        high, = struct.unpack_from("L", self.buffer, offset=self.offset)
        low, = struct.unpack_from("L", self.buffer, offset=self.offset + 4)
        self.offset += 8
        return (high * math.pow(2, 32)) + low

    def readBytes(self, size: int) -> bytes:
        if self.offset + size > self.length:
            raise Exception("Bad call to VttParser.readBytes")
        binary = self.buffer[self.offset:self.offset + size].tobytes()
        self.offset += size
        return binary

    def skip(self, size: int):
        self.offset += size

    def getPosition(self) -> int:
        return self.offset

    def getLength(self) -> int:
        return len(self.buffer)

    def has_more_data(self) -> bool:
        return self.offset < self.length


class VTTParser(object):
    __BoxType = BoxType
    base_time = 0
    presentations = list()
    raw_payload = bytes()
    saw_tfdt = False
    saw_trun = False
    saw_mdat = False
    default_duration = None

    def __init__(self):
        self.header_box_type = {}
        self.box_callback_func = {}
        self.linenumber = None # type: int

    @staticmethod
    def children(box: ParsedBox):
        header = 12 if box.flags is not None else 8
        while box.viewer.has_more_data() is True and box.parser.done is False:
            box.parser.read_box(box.start + header, box.viewer, box.partial_okay)

    @staticmethod
    def typeToString(mtype: int) -> str:
        return struct.pack("!L", mtype).decode("utf-8")

    @staticmethod
    def typeFromString(name: str) -> int:
        if len(name) != 4:
            raise Exception("Mp4 box names must be 4 characters long")
        code = 0
        for char in name:
            code = (code << 8) | ord(char)
        return code

    def box(self, name: int, box_callback_func: classmethod):
        type_code = self.typeFromString(name)
        self.header_box_type[type_code] = VTTParser.__BoxType.BASIC_BOX
        self.box_callback_func[type_code] = box_callback_func

    def fullBox(self, name: int, fullbox_callback_func: classmethod):
        type_code = self.typeFromString(name)
        self.header_box_type[type_code] = VTTParser.__BoxType.FULL_BOX
        self.box_callback_func[type_code] = fullbox_callback_func

    def read(self, data: bytes, partial_okay: bool = False):
        viewer = Viewer(data)
        self.done = False
        results = []
        while viewer.has_more_data() and self.done is False:
            result = self.read_box(0, viewer, partial_okay)
            if result is not None:
                results.append(result)
        return results

    def read_box(self, abs_start: int, viewer: Viewer, partial_okay: bool):
        start = viewer.getPosition()
        size = viewer.readUint32()
        mtype = viewer.readUint32()
        box_type = self.typeToString(mtype)
        # print(f"--->Parsing MP4 box {box_type}<---")
        if size == 0:
            size = viewer.getLength() - start
        elif size == 1:
            size = viewer.readUint64()
        box_callback_func = self.box_callback_func.get(mtype)
        if box_callback_func is not None:
            if self.header_box_type[mtype] == VTTParser.__BoxType.FULL_BOX:
                version_flags = viewer.readUint32()
                version = bit_right_shift(version_flags, 24)
                flags = version_flags & 0xFFFFFF
            else:
                version = None
                flags = None
            end = start + size
            if partial_okay and end > viewer.getLength():
                end = viewer.getLength()
            payload_size = end - viewer.getPosition()
            payload = viewer.readBytes(payload_size) if payload_size > 0 else bytes()
            box = ParsedBox(**{
                "parser": self,
                "partial_okay": partial_okay or False,
                "version": version,
                "flags": flags,
                "viewer": Viewer(payload),
                "size": size,
                "start": start + abs_start,
            })
            return box_callback_func(box)
        else:
            skip_length = min(
                start + size - viewer.getPosition(),
                viewer.getLength() - viewer.getPosition()
            )
            viewer.skip(skip_length)

    def read_base_time(self, box: ParsedBox):
        self.saw_tfdt = True
        if box.version == 0 or box.version == 1:
            pass
        else:
            raise Exception("TFDT version can only be 0 or 1")
        if box.version == 1:
            baseMediaDecodeTime = box.viewer.readUint64()
        if box.version == 0:
            baseMediaDecodeTime = box.viewer.readUint32()
        self.base_time = baseMediaDecodeTime
        return baseMediaDecodeTime

    def read_default_duration(self, box: ParsedBox) -> tuple:
        if box.flags is None:
            raise Exception("A TFHD box should have a valid flags value")
        defaultSampleDuration = None
        defaultSampleSize = None
        trackId = box.viewer.readUint32()
        # Skip "base_data_offset" if present.
        if box.flags & 0x000001:
            box.viewer.skip(8)
        # Skip "sample_description_index" if present.
        if box.flags & 0x000002:
            box.viewer.skip(4)
        # Read "default_sample_duration" if present.
        if box.flags & 0x000008:
            defaultSampleDuration = box.viewer.readUint32()
        # Read "default_sample_size" if present.
        if box.flags & 0x000010:
            defaultSampleSize = box.viewer.readUint32()
        self.default_duration = defaultSampleDuration

    def read_presentations(self, box: ParsedBox) -> tuple:
        self.saw_trun = True
        if box.version is None:
            raise Exception("A TRUN box should have a valid version value")
        if box.flags is None:
            raise Exception("A TRUN box should have a valid flags value")
        sampleCount = box.viewer.readUint32()
        sampleData = []
        # Skip "data_offset" if present.
        if box.flags & 0x000001:
            box.viewer.skip(4)
        # Skip "first_sample_flags" if present.
        if box.flags & 0x000004:
            box.viewer.skip(4)
        for index in range(sampleCount):
            sample = ParsedTRUNSample()
            # Read "sample duration" if present.
            if box.flags & 0x000100:
                sample.sampleDuration = box.viewer.readUint32()
            # Read "sample_size" if present.
            if box.flags & 0x000200:
                sample.sampleSize = box.viewer.readUint32()
            # Skip "sample_flags" if present.
            if box.flags & 0x000400:
                box.viewer.skip(4)
            # Read "sample_time_offset" if present.
            if box.flags & 0x000800:
                if box.version == 0:
                    sample.sampleCompositionTimeOffset = box.viewer.readUint32()
                else:
                    sample.sampleCompositionTimeOffset = box.viewer.readInt32()
            sampleData.append(sample)
        self.presentations = sampleData

    def read_raw_payload(self, box: ParsedBox):
        if ~self.saw_mdat is False:
            raise Exception("VTT cues in mp4 with multiple MDAT are not currently supported")
        self.saw_mdat = True
        size = box.viewer.getLength() - box.viewer.getPosition()
        self.raw_payload = box.viewer.readBytes(size)

    def allData(self, box: ParsedBox) -> bytes:
        size = box.viewer.getLength() - box.viewer.getPosition()
        return box.viewer.readBytes(size)


def extract_sub(path: Path, payload: bytes, startTime: int, currentTime: int, linenumber: int):
    VTTP = VTTParser()
    VTTP.box("payl", VTTP.allData)
    VTTP.box("iden", VTTP.allData)
    VTTP.box("sttg", VTTP.allData)
    result = VTTP.read(payload, partial_okay=False)
    timescale = TIMESCALE
    periodStart = 0
    if len(result) > 0:
        if len(result) == 1:
            line = linenumber
            settings = "line:90% align:middle"
            payload = result[0].decode("utf-8")
        else:
            line, settings, payload = result
            line = int(line.decode("utf-8"))
            settings = settings.decode("utf-8")
            payload = payload.decode("utf-8")
        if payload:
            vtt = {
                "line": line,
                "file": path.name,
                "startTime": periodStart + startTime / timescale,
                "currentTime": periodStart + currentTime / timescale,
                "settings": settings,
                "subtitle": payload,
            }
            # print(colorama.Fore.LIGHTBLUE_EX + f"____>>>>\n{json.dumps(vtt, ensure_ascii=False, indent=4)}")
            return vtt


def extract_work(path: Path, VP: VTTParser):
    currentTime = VP.base_time
    viewer = Viewer(VP.raw_payload)
    tmp_vtt = []
    for presentation in VP.presentations:
        duration = presentation.sampleDuration or VP.default_duration
        if presentation.sampleCompositionTimeOffset:
            startTime = VP.base_time + presentation.sampleCompositionTimeOffset
        else:
            startTime = currentTime
        currentTime = startTime + (duration or 0)
        totalSize = 0
        while True:
            # Read the payload size.
            payloadSize = viewer.readUint32()
            totalSize += payloadSize
            # Skip the type.
            payloadType = viewer.readUint32()
            payloadName = VTTParser.typeToString(payloadType)
            payload = None
            if payloadName == 'vttc':
                if payloadSize > 8:
                    payload = viewer.readBytes(payloadSize - 8)
                elif payloadName == 'vtte':
                    print("vtte (vtt cue) 为空跳过")
                    viewer.skip(payloadSize - 8)
                else:
                    print(f"未知类型box -> {payloadName} 跳过")
                    viewer.skip(payloadSize - 8)
            if duration:
                if payload:
                    # print("payload is ->", payload)
                    res = extract_sub(path, payload, startTime, currentTime, VP.linenumber)
                    if res:
                        tmp_vtt.append(res)
            else:
                print("WVTT sample duration unknown, and no default found!")        
            if ~bool(presentation.sampleSize) or totalSize <= presentation.sampleSize:
                pass
            else:
                raise Exception("The samples do not fit evenly into the sample sizes given in the TRUN box!")
            if presentation.sampleSize and totalSize < presentation.sampleSize:
                continue
            else:
                break
    return tmp_vtt


def extractor(fpath: Path, has_linenumber: bool):
    vtts = []
    index = 1
    for path in fpath.iterdir():
        if path.suffix != ".mp4":
            continue
        VP = VTTParser()
        if has_linenumber is False:
            VP.linenumber = index
        VP.box("moof", VP.children)
        VP.box("traf", VP.children)
        VP.fullBox("tfdt", VP.read_base_time)
        VP.fullBox("tfhd", VP.read_default_duration)
        VP.fullBox("trun", VP.read_presentations)
        VP.box("mdat", VP.read_raw_payload)
        VP.read(path.read_bytes(), partial_okay=False)
        _vtts = extract_work(path, VP)
        if len(_vtts) > 0:
            index += 1
        vtts += _vtts
    generate_vtt_file(fpath.with_suffix(".vtt"), vtts)


if __name__ == "__main__":
    parser = ArgumentParser(
        prog="dash mp4 vtt extractor v1.2@xhlove",
        description=(
            "Dash Mp4 VTT Subtitle Extractor, "
            "which is translated from shaka-player project by xhlove. "
            "Report bug to vvtoolbox.dev@gmail.com"
        )
    )
    parser.add_argument("-p", "--path", help="Dash mp4 folder path")
    parser.add_argument("-ts", "--timescale", default=1000, type=int, help="set video timescale, default is 1000")
    parser.add_argument("-line", "--has-linenumber", action="store_true", help="use this option if your file has linenumber")
    args = parser.parse_args()
    if args.timescale is not None:
        TIMESCALE = args.timescale
    if args.path is None:
        args.path = input("paste dash mp4 folder path plz:\n")
    fpath = Path(args.path).resolve()
    if fpath.exists():
        extractor(fpath, args.has_linenumber)
    else:
        print(f"{str(fpath)} is not exists!")