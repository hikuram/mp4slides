# Third-party notices

The source code authored for this repository is licensed under the MIT License.
See `LICENSE`.

This repository does not vendor or redistribute the third-party Python packages,
FFmpeg binaries, CUDA runtime, base container image, or speech-recognition model
weights listed below. They are downloaded or installed separately by the user at
installation, container-build, or runtime. Each component remains subject to its
own license and terms.

This notice is provided as a convenience and is not a replacement for the
license text or notices distributed by each upstream project.

## Direct Python dependencies

| Component | Version used by `requirements.txt` | License | Upstream |
| --- | ---: | --- | --- |
| faster-whisper | 1.2.1 | MIT | https://github.com/SYSTRAN/faster-whisper |
| opencv-python-headless / OpenCV | 5.0.0.93 | Apache-2.0 | https://github.com/opencv/opencv-python / https://github.com/opencv/opencv |
| NumPy | 2.2.6 | BSD-3-Clause (with additional notices for bundled components in binary distributions) | https://github.com/numpy/numpy |
| python-pptx | 1.0.2 | MIT | https://github.com/scanny/python-pptx |
| PyYAML | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| Pillow | 12.3.0 | MIT-CMU | https://github.com/python-pillow/Pillow |
| ReportLab | 5.0.0 | BSD-style license | https://www.reportlab.com/ / https://github.com/MrBitBucket/reportlab-mirror |

## Important transitive dependency

`faster-whisper` uses CTranslate2. CTranslate2 is licensed under the MIT License.
See https://github.com/OpenNMT/CTranslate2.

Other transitive Python dependencies may be installed by package managers. Their
licenses are not changed by this project. Inspect the installed environment when
redistributing an environment or binary bundle.

## FFmpeg

The provided Dockerfile installs FFmpeg from the Ubuntu package repositories.
FFmpeg is not included in this repository. FFmpeg licensing depends on the exact
build configuration and enabled libraries; upstream FFmpeg documents LGPL and
GPL configurations separately. If you redistribute an FFmpeg binary or a
container image containing it, review the license of that exact build.

Upstream legal information: https://ffmpeg.org/legal.html

## NVIDIA CUDA and container base image

The provided Dockerfile references an NVIDIA CUDA base image. No NVIDIA CUDA
binary or NVIDIA container image is distributed in this repository. CUDA and
NVIDIA container components are subject to NVIDIA's applicable license terms and
EULA. If you redistribute a built container image, review those terms separately.

CUDA EULA: https://docs.nvidia.com/cuda/eula/index.html

## Ubuntu packages

The Dockerfile may install Ubuntu packages in a locally built container. Those
packages are not included in this repository and retain their respective
licenses.

## Speech-recognition model weights

Model weights are not distributed by this repository. `faster-whisper` may
download model artifacts at runtime. The license for a model is determined by
the selected model/model repository and can differ from the license of this
project. Check the model card and license before redistributing model weights.

## Generated PPTX and PDF files

The MIT license on this project does not automatically impose the MIT license on
user-provided presentation videos, extracted slide images, transcripts, or
resulting PPTX/PDF documents. Users are responsible for having the rights needed
to process and distribute their input and output content.
