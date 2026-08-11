# mp4slides

プレゼン動画から、スライド画像・日本語文字起こし・PPTX/PDFを生成するDocker向けCLIです。

主な構成は以下です。

- FFmpeg: 動画情報取得と16 kHz mono WAV抽出
- OpenCV: ROI解析、フレーム差分、安定区間検出
- faster-whisper: 日本語文字起こし
- python-pptx: スライド画像とSpeaker Notesを含むPPTX生成
- ReportLab: LibreOfficeを使わないPDF直接生成

## 検出方針

単純なシーン切替ではなく、次を組み合わせています。

1. 指定ROIのみ解析
2. 除外矩形をマスク
3. 直前フレーム差分
4. 現在スライドの基準画像との差分
5. high/lowのヒステリシス
6. 一定時間の安定判定
7. 隣接区間の小変化を再結合
8. 極端に短い区間を近い前後スライドへ結合

箇条書きの段階表示などは、`merge_threshold` 以下の小変化なら後ろの代表画像を残して1枚へまとめます。

## Docker build

```bash
docker build -t mp4slides .
```

ベースイメージはfaster-whisperがGPU用途として案内しているCUDA 12/cuDNN 9系です。

## 基本実行

```bash
docker run --rm --gpus all \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  -v "$PWD/models:/models" \
  mp4slides \
  /input/presentation.mp4 \
  --format both
```

初回はWhisperモデルが`/models`へ取得されます。モデルキャッシュをvolumeに残すと2回目以降の再取得を避けられます。

## ROI指定

座標は動画全体に対する0から1の正規化座標です。

```bash
mp4slides /input/presentation.mp4 \
  --roi 0.05,0.05,0.75,0.85 \
  --ignore 0.00,0.90,1.00,0.10 \
  --ignore 0.85,0.00,0.15,0.15
```

`--ignore`は複数指定できます。字幕、時計、発表者カメラなどの更新領域を除外する用途です。

`--image-region roi`が既定なので、通常は解析ROIを切り出した画像が資料に入ります。

解析範囲と出力画像の範囲を分けたい場合は`--capture-roi`を使います。`--capture-roi`はページ判定には影響しません。

```bash
mp4slides /input/presentation.mp4 \
  --roi 0.10,0.10,0.70,0.75 \
  --capture-roi 0.03,0.03,0.94,0.90
```

解析だけROIにして出力画像を動画全体にしたい場合は`--image-region full`を使います。この場合`--capture-roi`は無視されます。

## YAML設定

```bash
mp4slides /input/presentation.mp4 \
  --config /input/config.yaml \
  --output-dir /output
```

`config.example.yaml`をコピーして使えます。CLIで指定した項目はYAMLを上書きします。
`config.example.yaml`はコード内デフォルトを全項目明示したreference configで、pytestでデフォルト値との一致と項目漏れを検証しています。

## 出力

入力が`presentation.mp4`の場合、標準では次を生成します。

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

`audio.wav`は`keep_intermediate: true`の場合のみ残します。

### PPTX

各スライドは代表フレーム画像1枚です。文字起こしはSpeaker Notesへ次の形で格納します。

```text
[12.400 - 38.700]
transcript text...
```

### PDF

PPTXから変換せず、ReportLabで直接生成します。既定は`side-by-side`で、**左にスライド画像、右にそのスライド区間の全文文字起こし**を配置します。

- `side-by-side`: 左にスライド、右に全文文字起こし（既定）
- `below`: スライド画像の下に文字起こしを表示
- `notes-page`: スライドページの次に文字起こしページを追加
- `none`: スライド画像のみ

右欄に入り切らない場合は、まず`pdf_min_font_size`まで自動縮小し、それでも入り切らなければ同じスライド画像を左に再掲した継続ページを生成します。文字起こしは省略しません。

PDFでは文字起こし中の改行をレンダリング時だけ正規化できます。`segments.json`の元テキストは変更しません。

- `space`: 各改行を単純なスペースへ置換（PDF既定）
- `preserve`: 改行をそのまま保持
- `paragraph`: 単一改行はスペース化し、空行による段落区切りは保持

PPTX Speaker Notesは既定で`preserve`です。必要ならPDFとは独立して変更できます。

```bash
mp4slides /input/presentation.mp4 \
  --format pdf \
  --pdf-transcript-mode side-by-side \
  --pdf-transcript-newline-mode space \
  --pdf-transcript-ratio 0.42 \
  --pdf-font-size 10 \
  --pdf-min-font-size 8
```

PPTXノートもスペース化する場合は`--pptx-notes-newline-mode space`を指定します。`pdf_transcript_ratio`は`side-by-side`では右側文字起こし欄の幅比率です。`pdf_margin_pt`、`pdf_gap_pt`、`pdf_page_width_in`、`pdf_page_height_in`もYAMLまたはCLIから調整できます。

日本語PDFはReportLabの日本語CIDフォントを既定で使用します。TrueTypeフォントを埋め込みたい場合は`output.pdf_font_path`または`--pdf-font-path`でTTFファイルを指定できます。

```bash
mp4slides /input/presentation.mp4 \
  --format pdf \
  --pdf-font-path /fonts/NotoSansJP-Regular.ttf
```

Docker内で指定する場合は、フォントファイルをvolumeでマウントし、コンテナ内のパスを指定してください。

## 再実行: ページ分けと文字起こしを保持して見た目だけ変更

初回実行で生成した`presentation.segments.json`には、各ページの`start`、`end`、`representative_time`、`transcript`が保存されています。

`--reuse-segments`を指定すると、**スライド検出とWhisperを実行せず**、そのJSONのページ境界・代表時刻・文字起こしを確定値として再利用します。元MP4から代表フレームだけ再取得するため、キャプチャ範囲やPDFレイアウトを低コストで何度でも変更できます。

```bash
mp4slides /input/presentation.mp4 \
  --reuse-segments /output/presentation.segments.json \
  --capture-roi 0.04,0.06,0.92,0.86 \
  --format both \
  --pdf-transcript-mode side-by-side \
  --pdf-transcript-newline-mode space \
  --pdf-transcript-ratio 0.45
```

この再実行では次を保持します。

- ページ数とページ境界 (`start` / `end`)
- 代表フレーム時刻 (`representative_time`)
- ページごとの文字起こし (`transcript`)
- `merged_count`などの既存メタデータ

一方、次は変更できます。

- `--capture-roi`: 出力画像の切り出し範囲
- `--image-region`: ROI画像か全画面か
- PPTX/PDFの出力有無
- PDFの左右比率、フォントサイズ、余白、カラム間隔、ページサイズ
- PDF文字起こしの改行処理 (`preserve` / `space` / `paragraph`)
- PPTXノートの改行処理 (`preserve` / `space` / `paragraph`)
- PPTXのスライドサイズ

`segments.json`自体をテキストエディタで修正してから再利用することもできます。例えば誤検出した境界を直したり、`representative_time`を変更して別のフレームを採用したり、文字起こしを校正した後、その内容を固定したまま再レンダリングできます。

初回の解析ROIそのものを変えて**ページ分けも再判定**したい場合は、`--reuse-segments`を外して通常実行してください。

## GPUなしで確認

CPUでも動作確認できます。

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

文字起こしを行わず、画像解析とPPTX/PDF生成だけ確認する場合は次です。

```bash
mp4slides /input/presentation.mp4 --skip-transcript --format both
```

## 閾値調整

初期値は一般的なプレゼン動画向けの出発点です。動画によって調整してください。

- `threshold_high`: 直前フレームの大きな変化を検出
- `threshold_low`: 変化終了の判定
- `reference_threshold`: 現在スライドの基準画像からの累積変化を検出
- `stable_seconds`: 新状態をスライドとして確定するまでの静止時間
- `merge_threshold`: 隣接する確定区間を同一スライドへ戻す小変化閾値
- `min_slide_seconds`: 短すぎる区間を前後へ吸収する閾値

`presentation.detection_scores.csv`にはサンプル時刻ごとの`frame_delta`と`reference_delta`が出るので、このCSVを見ながら調整できます。

例えば段階表示が分割されすぎる場合は、まず`merge_threshold`を少し上げます。

```bash
mp4slides /input/presentation.mp4 --merge-threshold 0.025
```

別スライドまで結合される場合は下げます。

```bash
mp4slides /input/presentation.mp4 --merge-threshold 0.010
```

## 依存バージョン

`requirements.txt`は2026-08時点で確認したバージョンに固定しています。CUDAベースはfaster-whisper公式READMEのCUDA 12/cuDNN 9 Docker例に合わせています。

## Tests

ローカルPython環境では次で実行できます。

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

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the dependency and
runtime licensing notes.

If you redistribute a built container image or other bundled environment, perform
a separate license review for the exact FFmpeg, CUDA, Ubuntu, Python-package, and
model artifacts included in that distribution.
