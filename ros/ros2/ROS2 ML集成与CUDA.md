# ROS2 ML 集成与 CUDA

> 把深度学习 / 强化学习模型嵌入 ROS2 节点：ONNX Runtime、TensorRT、CUDA stream 同步、零拷贝、gym-ros2。

---

## 一、推理框架选型

| 框架 | 优势 | 劣势 |
|------|------|------|
| **ONNX Runtime** | 跨平台、CPU/GPU/CUDA/TensorRT EP | 上手快但极致优化弱 |
| **TensorRT** | 极致 GPU 推理，FP16/INT8 | 仅 NVIDIA、构建复杂 |
| **PyTorch (libtorch)** | 训练-推理一致 | 体积大、依赖 |
| **OpenVINO** | Intel CPU/GPU/iGPU/VPU 优化 | 仅 Intel |
| **MNN / NCNN** | 移动/嵌入式 | 算子覆盖窄 |
| **TFLite** | 移动 | C++ API 一般 |

ROS2 节点常见组合：
- 自动驾驶感知：TensorRT（CenterPoint/YOLO）
- 服务机器人：ONNX Runtime（CUDA + CPU 兜底）
- 端侧：TFLite / NCNN

---

## 二、ONNX Runtime 节点

```cpp
#include <onnxruntime_cxx_api.h>

class YoloNode : public rclcpp::Node {
public:
    YoloNode() : Node("yolo"), env_(ORT_LOGGING_LEVEL_WARNING, "yolo") {
        Ort::SessionOptions opts;
        opts.SetIntraOpNumThreads(2);
        // CUDA EP
        OrtCUDAProviderOptions cuda_opts{};
        cuda_opts.device_id = 0;
        opts.AppendExecutionProvider_CUDA(cuda_opts);
        session_ = std::make_unique<Ort::Session>(env_, "yolov8.onnx", opts);
        sub_ = create_subscription<sensor_msgs::msg::Image>(
            "image", rclcpp::SensorDataQoS(),
            std::bind(&YoloNode::on_image, this, std::placeholders::_1));
        pub_ = create_publisher<vision_msgs::msg::Detection2DArray>("detections", 10);
    }
private:
    void on_image(sensor_msgs::msg::Image::ConstSharedPtr msg) {
        cv::Mat img = cv_bridge::toCvShare(msg, "bgr8")->image;
        auto blob = preprocess(img);     // -> NCHW float32
        auto inputs = make_input_tensors(blob);
        auto outputs = session_->Run(Ort::RunOptions{nullptr},
            input_names_.data(), inputs.data(), inputs.size(),
            output_names_.data(), output_names_.size());
        auto detections = postprocess(outputs);
        pub_->publish(detections);
    }
    Ort::Env env_;
    std::unique_ptr<Ort::Session> session_;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
    rclcpp::Publisher<vision_msgs::msg::Detection2DArray>::SharedPtr pub_;
};
```

---

## 三、TensorRT 工程化

构建：
```bash
trtexec --onnx=yolov8.onnx --saveEngine=yolov8.engine --fp16
```

C++ runtime：
```cpp
auto runtime = nvinfer1::createInferRuntime(logger_);
auto engine = runtime->deserializeCudaEngine(buf.data(), buf.size());
auto context = engine->createExecutionContext();

cudaStream_t stream; cudaStreamCreate(&stream);
context->enqueueV2(buffers, stream, nullptr);
cudaStreamSynchronize(stream);
```

要点：
- INT8 校准：用代表性数据集生成 cache；
- 输入预处理也搬 GPU（`cv::cuda::*` / `cv::Mat -> cudaMemcpyAsync`）；
- 严禁在每帧 `cudaMalloc`，预分配。

---

## 四、CUDA Stream + ROS2 回调

```
回调线程 → cudaMemcpyHostToDeviceAsync(stream)
          → enqueueV2(stream)
          → cudaMemcpyDeviceToHostAsync(stream)
          → cudaStreamSynchronize(stream)   ← 必要时阻塞
          → 发布消息
```

或更激进：注册 `cudaLaunchHostFunc` 在 stream 完成时回调发布，避免 sync。

实时建议：
- 每个推理节点独占 stream；
- 多模型并发用多 stream；
- `cudaEventRecord` 测量延迟；
- `MultiThreadedExecutor + ReentrantCallbackGroup` 让多帧并行入队。

---

## 五、零拷贝图像/点云

避免 `image -> cv::Mat -> cuda` 拷贝两次。方案：
- 驱动直接 GPU 上输出（GMSL Camera + V4L2 + DMABUF）；
- 用 NVIDIA **Isaac ROS** 的 `nitros` framework — Type-Adapter + GXF，跨节点零拷贝；
- iceoryx + Cyclone：CPU 内存零拷贝（不是 GPU）。

`nitros` 简介：
- 用 GXF graph 描述节点流；
- 节点间共享 cuda memory pool；
- 与 ROS2 message 互译（`nitros_image` 类型）。

---

## 六、训练数据 & bag

- 用 `rosbag2` 录制 mcap，含图像 / 雷达 / GT；
- `rosbag2 -> mcap -> dataset` 转换脚本（mcap 官方 Python API）；
- ROS2 与 PyTorch DataLoader 结合：
  ```python
  from rosbags.highlevel import AnyReader
  with AnyReader([Path('train.bag')]) as reader:
      for con, ts, raw in reader.messages():
          msg = reader.deserialize(raw, con.msgtype)
  ```

---

## 七、强化学习与仿真

- **gym-ros2** / **stable_baselines3** + Gazebo / Isaac Sim：
  - Env 封装为 ROS2 service：`reset` / `step`；
  - reward / observation 通过 topic；
- **Isaac Lab**（NVIDIA）：GPU 并行 RL，支持 ROS2 桥；
- 部署：训练后导出 ONNX，推理节点跑 ONNX Runtime / TensorRT。

---

## 八、生命周期 + 模型切换

把模型加载放 Lifecycle Node 的 `on_configure`：
- `inactive` → 模型已加载，未推理；
- `active` → 订阅启用，开始推理；
- `deactivate` → 停推理但模型保留；
- `cleanup` → 卸模型。

支持运行时通过 service 切换模型（A/B 测试 / OTA 模型更新）。

---

## 九、性能监控

| 工具 | 用途 |
|------|------|
| `nsys profile ros2 run my_pkg infer` | NVIDIA NSight Systems，看 stream/kernel timeline |
| `nvprof / ncu` | Kernel 级 profile |
| `tegrastats` (Jetson) | 实时 GPU/CPU/EMC 占用 |
| `tracetools_analysis` | ROS2 callback 时延 |
| Prometheus + GPU exporter | 长期监控 |

---

## 十、面试速记

- 推理：ONNX Runtime（跨平台）/ TensorRT（NVIDIA 极致）
- 严禁回调内 `cudaMalloc`；预分配 + 复用 stream
- ROS2 多线程 Executor + Reentrant group 让推理流水化
- 跨节点 GPU 零拷贝：**NVIDIA Isaac ROS NITROS**
- 部署 lifecycle：`on_configure` 加载模型，运行时支持热切
- 训练数据走 **rosbag2 mcap + rosbags Python**
- 性能用 **nsys / tegrastats / tracetools** 三件套
