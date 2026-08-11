# mp4slides

English | [日本語](README_ja.md)

`mp4slides` is a Docker-oriented CLI that converts presentation videos into slide images, transcripts, and PPTX/PDF documents.

Core components:

- FFmpeg: video metadata and 16 kHz mono WAV extraction
- OpenCV: ROI analysis, frame differences, and stable-scene detection
- faster-whisper: speech transcription
- python-pptx: PPTX generation with slide images and Speaker Notes
- ReportLab: direct PDF generation without LibreOffice

## Slide detection strategy

Instead of relying on a simple scene-change detector, `mp4slides` combines:

1. Analysis within a configurable ROI
2. Masks for ignored rectangles
3. Difference from the previous sampled frame
4. Difference from the current slide reference image
5. High/low hysteresis thresholds
6. A minimum stable duration
7. Post-processing that merges adjacent low-change segments
8. Absorption of extremely short segments into neighboring slides

For progressive bullet reveals and similar animations, small changes below `merge_threshold` are merged and the later representative frame is kept as the final slide image.

## Docker build

```bash
docker build -t mp4slides .
```

The Dockerfile uses a CUDA 12/cuDNN 9 runtime compatible with the GPU setup recommended for faster-whisper.

## Basic usage

```bash
docker run --rm --gpus all \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  -v "$PWD/models:/models" \
  mp4slides \
  /input/presentation.mp4 \
  --format both
```

On the first run, the Whisper model is downloaded into `/models`. Keeping the model cache in a volume avoids downloading it again on later runs.

## ROI configuration

ROI coordinates are normalized to the full video frame, from 0 to 1.

```bash
mp4slides /input/presentation.mp4 \
  --roi 0.05,0.05,0.75,0.85 \
  --ignore 0.00,0.90,1.00,0.10 \
  --ignore 0.85,0.00,0.15,0.15
```

`--ignore` may be specified multiple times. It is useful for excluding changing regions such as subtitles, clocks, or presenter cameras.

The default `--image-region roi` places the analysis ROI in the generated document.

Use `--capture-roi` when the analysis area and the final captured image area should differ. `--capture-roi` does not affect page-boundary detection.

```bash
mp4slides /input/presentation.mp4 \
  --roi 0.10,0.10,0.70,0.75 \
  --capture-roi 0.03,0.03,0.94,0.90
```

Use `--image-region full` to analyze only the ROI while placing the full video frame in the output. In this mode, `--capture-roi` is ignored.

## YAML configuration

```bash
mp4slides /input/presentation.mp4 \
  --config /input/config.yaml \
  --output-dir /output
```

Copy `config.example.yaml` as a starting point. CLI options override values loaded from YAML.

`config.example.yaml` is a reference configuration that explicitly lists every built-in default. Tests verify both value equality with the built-in defaults and completeness of the configuration keys.

## Output

For `presentation.mp4` with `--format both`, the output is typically:

```text
/output/
  presentation.pptx
  presentation.pdf
  presentation.segments.json
  presentation.transcript.json
  presentation.detection_scores.csv
  presentation.audio.wav
  slides/
    presentation_slide_0001.png
    presentation_slide_0002.png
    ...
```

`presentation.audio.wav` is retained only when `keep_intermediate: true`.

Without `--format`, the built-in output format is `pptx`.

### PPTX

Each slide contains one representative frame image. The transcript for the corresponding time range is stored in Speaker Notes, for example:

```text
[12.400 - 38.700]
transcript text...
```

### PDF

PDF files are generated directly with ReportLab rather than converted from PPTX. The default mode is `side-by-side`: the slide image is placed on the left and the complete transcript for that slide interval is placed on the right.

Available modes:

- `side-by-side`: slide on the left, full transcript on the right (default)
- `below`: transcript below the slide image
- `notes-page`: add a transcript page after each slide page
- `none`: slide image only

If the transcript does not fit in the right column, the renderer first reduces the font size down to `pdf_min_font_size`. If the text still does not fit, continuation pages are created with the same slide image repeated on the left. Transcript text is not truncated.

Transcript newlines can be normalized at render time without modifying the original text stored in `segments.json`:

- `space`: replace newlines with spaces (PDF default)
- `preserve`: preserve newlines
- `paragraph`: collapse single newlines to spaces while preserving blank-line paragraph breaks

PPTX Speaker Notes use `preserve` by default and can be configured independently.

```bash
mp4slides /input/presentation.mp4 \
  --format pdf \
  --pdf-transcript-mode side-by-side \
  --pdf-transcript-newline-mode space \
  --pdf-transcript-ratio 0.42 \
  --pdf-font-size 10 \
  --pdf-min-font-size 8
```

Use `--pptx-notes-newline-mode space` to normalize PPTX notes in the same way. In `side-by-side` mode, `pdf_transcript_ratio` controls the fraction of content width allocated to the transcript column. `pdf_margin_pt`, `pdf_gap_pt`, `pdf_page_width_in`, and `pdf_page_height_in` can also be configured through YAML or CLI options.

Japanese PDF text uses a ReportLab Japanese CID font by default. To embed a TrueType font, specify a TTF file with `output.pdf_font_path` or `--pdf-font-path`.

```bash
mp4slides /input/presentation.mp4 \
  --format pdf \
  --pdf-font-path /fonts/NotoSansJP-Regular.ttf
```

When running in Docker, mount the font file into the container and specify its container path.

## Re-rendering without repeating slide detection or transcription

The `presentation.segments.json` file created by the first run stores the `start`, `end`, `representative_time`, and `transcript` values for each slide.

With `--reuse-segments`, `mp4slides` skips both slide detection and Whisper transcription and treats the saved JSON as the authoritative segmentation data. Representative frames are re-extracted from the original video, making it inexpensive to adjust capture regions and output layouts repeatedly.

```bash
mp4slides /input/presentation.mp4 \
  --reuse-segments /output/presentation.segments.json \
  --capture-roi 0.04,0.06,0.92,0.86 \
  --format both \
  --pdf-transcript-mode side-by-side \
  --pdf-transcript-newline-mode space \
  --pdf-transcript-ratio 0.45
```

The following values are preserved during re-rendering:

- Slide count and page boundaries (`start` / `end`)
- Representative frame time (`representative_time`)
- Transcript for each page (`transcript`)
- Existing metadata such as `merged_count`

The following values may still be changed:

- `--capture-roi`: output image crop
- `--image-region`: ROI image or full frame
- PPTX/PDF output selection
- PDF column ratio, font size, margins, gap, and page size
- PDF transcript newline handling (`preserve` / `space` / `paragraph`)
- PPTX notes newline handling (`preserve` / `space` / `paragraph`)
- PPTX slide dimensions

You may also edit `segments.json` manually before reusing it. This allows you to correct a page boundary, choose another `representative_time`, or proofread the transcript and then re-render the output while keeping those edits fixed.

To change the analysis ROI and detect page boundaries again, omit `--reuse-segments` and run the normal pipeline.

## CPU-only usage

The pipeline can also run on CPU:

```bash
docker run --rm \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  -v "$PWD/models:/models" \
  mp4slides \
  /input/presentation.mp4 \
  --device cpu \
  --compute-type int8
```

To test slide detection and PPTX/PDF generation without transcription:

```bash
mp4slides /input/presentation.mp4 --skip-transcript --format both
```

## Threshold tuning

The built-in values are intended as starting points for typical presentation videos and may need tuning for individual recordings.

- `threshold_high`: detects large changes from the previous sampled frame
- `threshold_low`: determines when a changing period has ended
- `reference_threshold`: detects accumulated change from the current slide reference image
- `stable_seconds`: required stable duration before a new state becomes a slide
- `merge_threshold`: maximum small change for merging adjacent finalized segments
- `min_slide_seconds`: threshold for absorbing very short segments into neighboring slides

`presentation.detection_scores.csv` records `frame_delta` and `reference_delta` for each sampled timestamp and can be used when tuning thresholds.

If progressive reveals are split into too many slides, try increasing `merge_threshold` first:

```bash
mp4slides /input/presentation.mp4 --merge-threshold 0.025
```

If distinct slides are incorrectly merged, decrease it:

```bash
mp4slides /input/presentation.mp4 --merge-threshold 0.010
```

## Dependency versions

`requirements.txt` pins versions verified for this project as of August 2026. The CUDA base follows the CUDA 12/cuDNN 9 setup used by the faster-whisper GPU Docker example.

## Tests

Run the test suite in a local Python environment with:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
pytest -q
```

## License

The source code authored for this repository is licensed under the MIT License.
See [`LICENSE`](LICENSE).

Third-party software used by the project keeps its own license. This repository
does **not** distribute prebuilt Docker images, FFmpeg/CUDA binaries, Python
dependency wheels, or speech-recognition model weights. The `Dockerfile` is a
build recipe; dependencies installed while building it are not relicensed under
MIT.

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for dependency and runtime licensing notes.

If you redistribute a built container image or another bundled environment, perform a separate license review for the exact FFmpeg, CUDA, Ubuntu, Python-package, and model artifacts included in that distribution.
