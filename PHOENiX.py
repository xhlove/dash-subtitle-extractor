
    @staticmethod
    def merge_segmented_wvtt(data: bytes, period_start: float = 0.) -> tuple[CaptionList, Optional[str]]:
        """
        Convert Segmented DASH WebVTT cues into a pycaption Caption List.
        Also returns an ISO 639-2 alpha-3 language code if available.

        Code ported originally by xhlove to Python from shaka-player.
        Has since been improved upon by rlaphoenix using pymp4 and
        pycaption functions.
        """
        captions = CaptionList()

        # init:
        saw_wvtt_box = False
        timescale = None
        language = None

        # media:
        # > tfhd
        default_duration = None
        # > tfdt
        saw_tfdt_box = False
        base_time = 0
        # > trun
        saw_trun_box = False
        samples = []

        def flatten_boxes(box: Container) -> Iterable[Container]:
            for child in box:
                if hasattr(child, "children"):
                    yield from flatten_boxes(child.children)
                    del child["children"]
                if hasattr(child, "entries"):
                    yield from flatten_boxes(child.entries)
                    del child["entries"]
                # some boxes (mainly within 'entries') uses format not type
                child["type"] = child.get("type") or child.get("format")
                yield child

        for box in flatten_boxes(MP4.parse_stream(BytesIO(data))):
            # init
            if box.type == b"mdhd":
                timescale = box.timescale
                language = box.language

            if box.type == b"wvtt":
                saw_wvtt_box = True

            # media
            if box.type == b"styp":
                # essentially the start of each segment
                # media var resets
                # > tfhd
                default_duration = None
                # > tfdt
                saw_tfdt_box = False
                base_time = 0
                # > trun
                saw_trun_box = False
                samples = []

            if box.type == b"tfhd":
                if box.flags.default_sample_duration_present:
                    default_duration = box.default_sample_duration

            if box.type == b"tfdt":
                saw_tfdt_box = True
                base_time = box.baseMediaDecodeTime

            if box.type == b"trun":
                saw_trun_box = True
                samples = box.sample_info

            if box.type == b"mdat":
                if not timescale:
                    raise ValueError("Timescale was not found in the Segmented WebVTT.")
                if not saw_wvtt_box:
                    raise ValueError("The WVTT box was not found in the Segmented WebVTT.")
                if not saw_tfdt_box:
                    raise ValueError("The TFDT box was not found in the Segmented WebVTT.")
                if not saw_trun_box:
                    raise ValueError("The TRUN box was not found in the Segmented WebVTT.")

                vttc_boxes = MP4.parse_stream(BytesIO(box.data))
                current_time = base_time + period_start

                for sample, vttc_box in zip(samples, vttc_boxes):
                    duration = sample.sample_duration or default_duration
                    if sample.sample_composition_time_offsets:
                        current_time += sample.sample_composition_time_offsets

                    start_time = current_time
                    end_time = current_time + (duration or 0)
                    current_time = end_time

                    if vttc_box.type == b"vtte":
                        # vtte is a vttc that's empty, skip
                        continue

                    layout: Optional[Layout] = None
                    nodes: list[CaptionNode] = []

                    for cue_box in MP4.parse_stream(BytesIO(vttc_box.data)):
                        cue_data = cue_box.data.decode("utf8")
                        if cue_box.type == b"sttg":
                            layout = Layout(webvtt_positioning=cue_data)
                        elif cue_box.type == b"payl":
                            nodes.extend([
                                node
                                for line in cue_data.split("\n")
                                for node in [
                                    CaptionNode.create_text(WebVTTReader()._decode(line)),
                                    CaptionNode.create_break()
                                ]
                            ])
                            nodes.pop()

                    if nodes:
                        caption = Caption(
                            start=start_time * timescale,  # as microseconds
                            end=end_time * timescale,
                            nodes=nodes,
                            layout_info=layout
                        )
                        p_caption = captions[-1] if captions else None
                        if p_caption and caption.start == p_caption.end and str(caption.nodes) == str(p_caption.nodes):
                            # it's a duplicate, but lets take its end time
                            p_caption.end = caption.end
                            continue
                        captions.append(caption)

        return captions, language
