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

`--image-region roi`が既定なので、資料にはROIを切り出した画像が入ります。解析だけROIにして出力画像を動画全体にしたい場合は`--image-region full`を使います。

## YAML設定

```bash
mp4slides /input/presentation.mp4 \
  --config /input/config.yaml \
  --output-dir /output
```

`config.example.yaml`をコピーして使えます。CLIで指定した項目はYAMLを上書きします。

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

PPTXから変換せず、ReportLabで直接生成します。

- `below`: スライド画像の下に文字起こしを表示
- `notes-page`: スライドページの次に文字起こしページを追加
- `none`: スライド画像のみ

```bash
mp4slides /input/presentation.mp4 \
  --format pdf \
  --pdf-transcript-mode notes-page
```

日本語PDFはReportLabの日本語CIDフォントを既定で使用します。TrueTypeフォントを埋め込みたい場合は`output.pdf_font_path`でTTFファイルを指定できます。

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
