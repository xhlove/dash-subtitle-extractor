goog.module('parser');

require("google-closure-library");
goog.require("shaka.text.Mp4VttParser");
goog.require('shaka.text.Mp4TtmlParser');
const fs = require("fs");
const path = require('path');
const args = require('args-parser')(process.argv);

let debug = false;
if (args["debug"]){
    debug = true;
    console.info(`args => ${JSON.stringify(args)}`);
}
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
let codecs = ["wvtt", "ttml"];
let subtype = args["type"]
if (!subtype || !codecs.includes(subtype)){
    console.log(`must set --type option which is one of ${codecs}, not ${subtype}`);
    process.exit()
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

function loop_nestedCues(lines, nestedCues){
    let payload = "";
    for (let i = 0; i < nestedCues.length; i++) {
        let cue = nestedCues[i];
        if (cue.nestedCues && cue.nestedCues.length > 0){
            loop_nestedCues(lines, cue.nestedCues)
        }
        if (cue.payload != ""){
            if (payload == ""){
                payload = cue.payload;
            }
            else{
                payload = `${payload} ${cue.payload}`;
            }
        }
        // lines.push(cue);
    }
    let cue = nestedCues[0];
    cue.payload = payload;
    if(cue.payload != ""){
        lines.push(cue);
    }
}

let parser = null;

try {
    switch (subtype) {
        case "wvtt":
            parser = new shaka.text.Mp4VttParser();
            break;
        case "ttml":
            parser = new shaka.text.Mp4TtmlParser();
            break;
        default:
            process.exit();
    }
    
    let InitSegment = new Uint8Array(fs.readFileSync(init_segment));
    parser.parseInit(InitSegment);
    let time = { periodStart: 0, segmentStart: 0, segmentEnd: 0 };
    let lines = [];
    let debug_contents = [];
    travel(segments_path, function (pathname) {
        // console.log(path.basename(pathname), pathname)
        let name = path.basename(pathname);
        // skip init segment
        if (name == path.basename(init_segment)) return;
        // now only allow mp4 file
        if (!name.endsWith(".mp4")) return;
        let Segment = new Uint8Array(fs.readFileSync(pathname));
        let results = parser.parseMedia(Segment, time);
        // console.log(`${name} 解析完成`);
        for (let i = 0; i < results.length; i++) {
            let result = results[i];
            result.name = name
            if (debug){
                debug_contents.push(JSON.stringify(result, null, 4));
            }
            if (result.nestedCues && result.nestedCues.length > 0){
                loop_nestedCues(lines, result.nestedCues)
            }
            if (result.payload != ""){
                lines.push(result);
            }
        }
    });
    if (debug){
        let content = debug_contents.join("\n-----------------\n");
        fs.writeFileSync(`${path.basename(segments_path)}.log`, content, "utf-8");
        console.log(`write debug log to ${path.basename(segments_path)}.log`)
    }
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
        // 跳过空的行
        let next_line = lines[offset];
        if (line.payload == "") {
            line = next_line;
            continue
        }
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