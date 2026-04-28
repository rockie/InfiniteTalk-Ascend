sudo apt-get update
sudo apt-get install -y \
    build-essential cmake git \
    ffmpeg libavcodec-dev libavfilter-dev libavformat-dev libavutil-dev


git clone --recursive https://github.com/dmlc/decord.git
  tar -czf decord-with-submodules.tar.gz decord/

  # scp 到 NPU host
  scp -P 22 /tmp/decord-with-submodules.tar.gz root@<NPU_HOST_IP>:/tmp/

  # NPU host 上解压 + 编译
  ssh root@<NPU_HOST_IP>
  cd /tmp
  tar -xzf decord-with-submodules.tar.gz
  cd decord
  mkdir -p build && cd build
  cmake .. -DUSE_CUDA=0 -DCMAKE_BUILD_TYPE=Release
  make -j$(nproc)
  cd ../python
  pip install -e . --no-build-isolation
  python -c "from decord import VideoReader, cpu; print('decord OK')"

  pip install misaki[en,zh]
  pip install num2words
  pip install spacy
  pip install phonemizer
  pip install espeakng_loader


conda activate multitalk

  python generate_infinitetalk.py \
    --device npu \
    --ckpt_dir weights/Wan-AI/Wan2.1-I2V-14B-720P \
    --size infinitetalk-480 \
    --infinitetalk_dir weights/MeiGen-AI/InfiniteTalk/single/infinitetalk.safetensors \
    --wav2vec_dir weights/TencentGameMate/chinese-wav2vec2-base \
    --input_json examples/single_example_image.json \
    --save_file out_multitalk.mp4 \
    --mode streaming
    --motion_frame 9