# Fitness App 智能健身计数系统

本项目是一个基于MediaPipe姿态检测的智能健身计数系统，可以为用户提供便捷、准确的深蹲与俯卧撑计数功能。

##  功能特性
-  **深蹲计数** - 基于膝盖角度检测，自动识别深蹲动作
-  **俯卧撑计数** - 自动校准手臂角度，精准计数俯卧撑
-  **语音播报** - 中文语音实时播报计数和指导
-  **背景音乐** - 支持自定义训练时背景音乐的播放
-  **训练计时** - 支持倒计时和不限时两种模式
-  **重置功能** - 可随时重置计数重新开始

##  项目结构
```
fitness_app/
├── main.py              # 主程序 GUI 界面
├── squat_counter.py     # 深蹲计数器模块
├── pushup_counter.py    # 俯卧撑计数器模块
├── assets/
│   ├── audio/           # 音频资源
│   │   ├── squat_music.mp3
│   │   └── pushup_music.mp3
│   └── images/          # 图片资源
│       ├── icon.png
│       ├── squat.png
│       └── pushup.png
└── data/
    ├── pushup_count.txt # 俯卧撑计数记录
    └── squat_count.txt  # 深蹲计数记录
```

##  环境要求
- Python 3.8+
- Windows 10/11 操作系统（语音功能依赖 Windows SAPI）
- 摄像头
- 音频输出设备

##  安装部署

### 1. 克隆项目
```bash
git clone <项目地址>
cd fitness-app
```

### 2. 创建虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install opencv-python mediapipe numpy pygame pillow pywin32
```

### 4. 准备资源文件
确保 `assets` 文件夹中包含所需的图片和音频文件：
- `icon.png` - 应用图标
- `squat.png` - 深蹲按钮图标
- `pushup.png` - 俯卧撑按钮图标
- `squat_music.mp3` - 深蹲背景音乐
- `pushup_music.mp3` - 俯卧撑背景音乐

### 5. 运行程序
```bash
python main.py
```

##  使用说明

### 深蹲训练
1. 点击「深蹲训练」按钮
2. 站在摄像头前，保持站直姿势
3. 等待语音提示「准备」和倒计时
4. 开始做深蹲动作，系统自动计数

### 俯卧撑训练
1. 点击「俯卧撑训练」按钮
2. 摆好俯卧撑起始姿势（手臂伸直）
3. 保持稳定 3 秒完成校准
4. 校准完成后开始训练，系统自动计数

##  配置说明

### 训练时长设置
- **倒计时模式**：选择分钟和秒数，时间到自动结束
- **不限时模式**：勾选「不限时」，显示正计时

### 音乐设置
- 可开启/关闭背景音乐
- 滑动条调节音量 
