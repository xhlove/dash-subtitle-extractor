goog.module('parser');

require("google-closure-library");
goog.require("shaka.text.Mp4VttParser");
const fs = require("fs");
const path = require('path');
const args = require('args-parser')(process.argv);

console.info(`args => ${JSON.stringify(args)}`);

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

try {
    let parser = new shaka.text.Mp4VttParser();
    
    let vttInitSegment = new Uint8Array(fs.readFileSync(init_segment));
    parser.parseInit(vttInitSegment);
    let time = { periodStart: 0, segmentStart: 0, segmentEnd: 0 };
    let count = 0;
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
            console.log(`${count} ${name} ${result.startTime} ${result.endTime} ${result.payload}`);
            count += 1;
        }
    })
} catch (err) {
    console.trace(err);
}

// node parser_compiled.js --init-segment=path/to/init.mp4 --segments-path=path/to/segments/folder
// node parser_compiled.js --init-segment=test/dashvtt_subtitle_WVTT_zh-TW/init.mp4 --segments-path=test/dashvtt_subtitle_WVTT_zh-TW