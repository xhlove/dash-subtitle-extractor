goog.module('parser');

require("google-closure-library");
goog.require("shaka.text.Mp4VttParser");
const fs = require("fs");
const path = require('path');
const args = require('args-parser')(process.argv);

if (!args["init-segment"]){
    console.log(`--init-segment option is required`)
    process.exit()
}
let init_segment = args["init-segment"]
if (!fs.existsSync(init_segment)){
    console.log(`init segment file ${init_segment} is not exists`)
    process.exit()
}
if (!args["segments-path"]){
    console.log(`--segments-path option is required`)
    process.exit()
}
let segments_path = args["segments-path"]
if (!fs.existsSync(init_segment)){
    console.log(`segments folder path ${segments_path} is not exists`)
    process.exit()
}
let debug = false;
if (args["debug"]){
    debug = true;
    console.info(`args => ${JSON.stringify(args)}`);
}

function travel(dir, callback) {
    fs.readdirSync(dir).forEach((file) => {
        var pathname = path.join(dir, file)
        if (fs.statSync(pathname).isDirectory()) {
            travel(pathname, callback)
        } else {
            callback(pathname)
        }
    })
}

function compare(a, b) {
    if (a.startTime < b.startTime) {
        return -1;
    }
    if (a.startTime > b.startTime) {
        return 1;
    }
    return 0;
}

function gentm(tm){
    return new Date(tm * 1000).toISOString().slice(11, -1);
}

try {
    let parser = new shaka.text.Mp4VttParser();
    
    let vttInitSegment = new Uint8Array(fs.readFileSync(init_segment));
    parser.parseInit(vttInitSegment);
    let time = { periodStart: 0, segmentStart: 0, segmentEnd: 0 };
    let count = 0;
    let lines = [];
    travel(segments_path, function (pathname) {
        // console.log(path.basename(pathname), pathname)
        let name = path.basename(pathname);
        // skip init segment
        if (name == path.basename(init_segment)) return;
        // now only allow mp4 file
        if (!name.endsWith(".mp4")) return;
        let vttSegment = new Uint8Array(fs.readFileSync(pathname));
        let results = parser.parseMedia(vttSegment, time);
        // console.log(`${name} 解析完成`);
        for (let i = 0; i < results.length; i++) {
            let result = results[i];
            result.name = name
            if (debug){
                console.log(`${count} ${result.name} ${result.startTime} ${result.endTime} ${result.payload}`);
            }
            lines.push(result);
            count += 1;
        }
    });
    // 按startTime从小到大排序
    lines.sort(compare);
    // 去重
    // 1. 如果当前行的endTime等于下一行的startTime 并且下一行内容与当前行相同 取下一行的endTime作为当前行的endTime 然后去除下一行
    // 2. 否则将下一行作为当前行 再次进行比较 直到比较结束
    let offset = 0;
    let lines_fix = [];
    let line = lines[offset];
    while (offset < lines.length - 1){
        offset += 1;
        let next_line = lines[offset];
        if (line.payload == next_line.payload && line.endTime == next_line.startTime){
            line.endTime = next_line.endTime;
        }
        else{
            lines_fix.push(line);
            line = next_line;
        }
    };
    // 最后一行也不能掉
    let next_line = lines[offset];
    if (line.payload == next_line.payload && line.endTime == next_line.startTime){
        line.endTime = next_line.endTime;
    }
    else{
        lines_fix.push(line);
        line = next_line;
    }
    if (debug){
        console.log(`after reduce duplicated lines, now lines count is ${lines_fix.length}`)
    }
    // 先用列表放内容 最后join
    let contents = ["WEBVTT"];
    for (let i = 0; i < lines_fix.length; i++){
        let line = lines_fix[i];
        contents.push(`${gentm(line.startTime)} --> ${gentm(line.endTime)}\n${line.payload}`)
    }
    let content = contents.join("\n\n");
    fs.writeFileSync(`${path.basename(segments_path)}.vtt`, content, "utf-8");
    console.log(`${lines_fix.length} lines of subtitle was founded. (*^▽^*)`)
    console.log(`write to ${path.basename(segments_path)}.vtt`)
} catch (err) {
    console.trace(err);
}

// node parser_compiled.js --init-segment=path/to/init.mp4 --segments-path=path/to/segments/folder
// node parser_compiled.js --init-segment=test/dashvtt_subtitle_WVTT_zh-TW/init.mp4 --segments-path=test/dashvtt_subtitle_WVTT_zh-TW