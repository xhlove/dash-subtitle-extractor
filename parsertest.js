goog.module('parser');

require("google-closure-library");
goog.require("shaka.text.Mp4VttParser");
const fs = require("fs");

try {
    const vttInitSegment = new Uint8Array(fs.readFileSync("test/assets/vtt-init.mp4"));
    const vttSegment = new Uint8Array(fs.readFileSync("test/assets/vtt-segment.mp4"));
    console.log("文件加载完成");
    const parser = new shaka.text.Mp4VttParser();
    console.log("Mp4VttParser初始化析完成");
    parser.parseInit(vttInitSegment);
    console.log("vttInitSegment解析完成");
    const time = {periodStart: 0, segmentStart: 0, segmentEnd: 0};
    const result = parser.parseMedia(vttSegment, time);
    console.log("vttSegment解析完成");
    for (let i = 0; i < result.length; i++){
        console.log(result[i]);
    }
} catch (err) {
    console.trace(err);
}