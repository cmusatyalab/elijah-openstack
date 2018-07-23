# GPU Passthrough Setup and Performance

Many edge workloads require a GPU to meet latency requirements. However, sharing
and virtualizing GPU devices for computation remain a challenge. In below, I
will describe our group's setup to allow multi-tenancy on GPUs.

## Architecture

The figure below represents the architecture. We adopt a containers on top of
virtual machines approach to allow GPU sharing. The GPU device is dedicated to a
particular VM through GPU-passthrough on the host.

![Architecture](https://github.com/cmusatyalab/elijah-openstack/blob/gpu/cloudlet-gateway/docs/GPU-Support-in-Cloudlet.png)

## Setup

### GPU-Passthrough to a libvirt VM

The setup process is automated through Ansible. Please see [repo](https://github.com/junjuew/ansible-dotfiles/) for the
set-up. Use following command to set up your machine.

```bash
ansible-playbook -i hosts-gpu-passthrough gpu-passthrough-playbook.yml
```

### Container Access to GPU

Nvidia-docker enables containers to access GPU easily. See [repo](https://github.com/junjuew/ansible-dotfiles/) for installation.

## Performance

### Container inside VM with GPU Passthrough

#### HW & SW Setup

##### Bare-Metal (cloudlet028.maas)

* NVIDIA Tesla GTX 1080 Ti GPU + 396.37 NVIDIA driver + cuda 9.0 + cudnn 7.1 +
  default computing mode
* Max GPU Clock: 1911 MHz(Graphics), 5505 MHz(Memory)

##### Container Inside a VM with GPU passthrough

* Container Runtime: nvidia-docker 2.0.3 + docker-ce 18.03.1
* 396.37 NVIDIA driver + cuda 9.0 + cudnn 7.1.4

#### Tensorflow Benchmarks:

* Tensorflow Version: 1.9.0
* python3
* Batch Size: 1
* 300 random generated examples, 3 runs.
* [Benchmark script](https://gist.github.com/junjuew/82d3b0d513e3debd2d453ee07505d32e)

| Virtualizaton |   SSD MobileNet V1 (ms)      | SSD Inception V2 (ms)    | Faster-RCNN Inception V2 (ms) | Faster-RCNN ResNet101 (ms)  |
|:-------------:|:----------------------------:|:------------------------:|:-----------------------------:|:---------------------------:|
| bare-metal | 119  +- 5     | 130 +- 7 | 180 +- 6 | 220 +- 5 |
| container inside a VM with GPU passthrough | 108  +- 19     | 114 +- 20 | 168 +- 22 | 225 +- 18 |
| VM with GPU passthrough (gpu exclusive-process mode) | 118  +- 27     | 128 +- 23 | 175 +- 22 | 225 +- 19 |
| VM with GPU passthrough (gpu default mode) | 108  +- 18     | 119 +- 19 | 164 +- 19 | 226 +- 17 |

<!---
Results on cloudlet001 with Tesla K40c
The clock is set to max clock speed: 875MHz(Graphics),3004MHz(Memory)
Software stack should be similar to above.

| Virtualizaton |   SSD MobileNet V1 (ms)      | SSD Inception V2 (ms)    | Faster-RCNN Inception V2 (ms) | Faster-RCNN ResNet101 (ms)  |
|:-------------:|:----------------------------:|:------------------------:|:-----------------------------:|:---------------------------:|
| bare-metal | 117, std 5      | 134, std 4 | 233, std 6 | 428, std 4 |
| container inside a VM with GPU passthrough | 104, std 20     | 128, std 16 | 227, std 16 | 412, std 13 |
-->

# Second-Round Of Test
| Virtualizaton |   SSD MobileNet V1 (ms)      | SSD Inception V2 (ms)    | Faster-RCNN Inception V2 (ms) | Faster-RCNN ResNet101 (ms)  |
|:-------------:|:----------------------------:|:------------------------:|:-----------------------------:|:---------------------------:|
| bare-metal |      |  |  |  |
| VM with GPU passthrough (gpu default mode) | 95 +- 13  | 101 +- 13 |  | |
| container inside a VM with GPU passthrough |    |  | |  |
