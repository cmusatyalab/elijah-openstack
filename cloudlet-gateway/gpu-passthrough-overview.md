# GPU Passthrough Setup and Performance

Many edge workloads require a GPU to meet latency requirements. However, sharing
and virtualizing GPU devices for computation remain a challenge. In below, I
will describe our group's setup to allow multi-tenancy on GPUs.

## Architecture

The figure below represents the architecture. We adopt a containers on top of
virtual machines approach to allow GPU sharing. The GPU device is dedicated to a
particular VM through GPU-passthrough on the host.

![Architecture](https://github.com/cmusatyalab/elijah-openstack/blob/gpu/cloudlet-gateway/GPU-Support-in-Cloudlet.png)

## Performance

### Container inside VM with GPU Passthrough
Container: nvidia-docker2
GPU: Tesla k40c
Cuda: 9.0
GPU driver: 396.37
GPU Application Clock: 875MHz(Graphics),3004MHz(Memory)

Tensorflow Benchmarks:
Tensorflow Version: 1.9.0
Batch Size: 1
300 random generated examples, 3 runs.

|   SSD MobileNet V1 (ms)      | SSD Inception V2 (ms)    | Faster-RCNN Inception V2 (ms) | Faster-RCNN ResNet101 (ms)  |
|:----------------------------:|:------------------------:|:-----------------------------:|:---------------------------:|
| 104, std 20      | 128, std 16 | 227, std 16 | 412, std 13 |

### Host

|   SSD MobileNet V1 (ms)      | SSD Inception V2 (ms)    | Faster-RCNN Inception V2 (ms) | Faster-RCNN ResNet101 (ms)  |
|:----------------------------:|:------------------------:|:-----------------------------:|:---------------------------:|
| 117, std 5      | 134, std 4 | 233, std 6 | 428, std 4 |