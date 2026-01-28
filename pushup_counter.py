import cv2
import mediapipe as mp
import numpy as np
import time
from queue import Queue
import threading
import winsound
import pythoncom
import win32com.client
import os


class AutoCalibrationPushupCounter:
    """自动校准俯卧撑计数器"""

    def __init__(self):
        # 基本计数器
        self.counter = 0
        self.stage = None

        # 校准状态
        self.calibration_state = "waiting"  
        self.calibration_start_time = None
        self.calibration_hold_time = 3.0  
        self.calibration_progress = 0  

        # 角度阈值
        self.up_threshold = 160  
        self.down_threshold = 90  
        self.calibration_margin = 10
        self.min_depth_for_count = 40  
        self.min_depth_for_detection = 20

        # 动作检测状态
        self.was_down = False 
        self.rep_start_angle = None

        # 稳定性检测
        self.stable_angles_buffer = [] 
        self.buffer_size = 15
        self.stability_threshold = 5.0

        # 显示信息
        self.feedback = "Get into pushup starting position"
        self.performance_quality = "Waiting for calibration"

        # 校准数据
        self.calibration_data = {
            'calibrated_up_angle': None,
            'calibrated_down_angle': None,
            'calibration_time': None,
            'calibration_stability': None
        }

        # 防误触保护
        self.min_calibration_angle = 140

        # 语音线程
        self.speech_queue = Queue()
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()

    def calculate_angle(self, a, b, c):
        """计算三点之间的角度"""
        a, b, c = np.array(a), np.array(b), np.array(c)
        ba, bc = a - b, c - b
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
        return np.degrees(np.arccos(cosine_angle))

    def analyze_posture(self, landmarks):
        """分析姿势，返回手臂角度（平均、左、右）"""
        # 获取关键点坐标
        left_shoulder = [
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value].y
        ]
        right_shoulder = [
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value].y
        ]
        left_elbow = [
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_ELBOW.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_ELBOW.value].y
        ]
        right_elbow = [
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_ELBOW.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_ELBOW.value].y
        ]
        left_wrist = [
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_WRIST.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.LEFT_WRIST.value].y
        ]
        right_wrist = [
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_WRIST.value].x,
            landmarks[mp.solutions.pose.PoseLandmark.RIGHT_WRIST.value].y
        ]

        # 计算左右手臂角度
        left_arm_angle = self.calculate_angle(left_shoulder, left_elbow, left_wrist)
        right_arm_angle = self.calculate_angle(right_shoulder, right_elbow, right_wrist)
        avg_arm_angle = (left_arm_angle + right_arm_angle) / 2
        return avg_arm_angle, left_arm_angle, right_arm_angle

    def check_stability(self, current_angle):
        """检查姿势是否稳定"""
        self.stable_angles_buffer.append(current_angle)
        if len(self.stable_angles_buffer) > self.buffer_size:
            self.stable_angles_buffer.pop(0)
        if len(self.stable_angles_buffer) < self.buffer_size:
            return False
        return max(self.stable_angles_buffer) - min(self.stable_angles_buffer) < self.stability_threshold

    def update_calibration_state(self, current_angle):
        """更新校准状态机"""
        # 等待校准
        if self.calibration_state == "waiting":
            if current_angle > self.min_calibration_angle:
                if self.check_stability(current_angle):
                    self.calibration_state = "calibrating"
                    self.calibration_start_time = time.time()
                    self.feedback = "Hold still... Calibrating"
                    return False
            else:
                self.feedback = f"Extend arms more!"
            return False

        # 正在校准
        elif self.calibration_state == "calibrating":
            if not self.check_stability(current_angle):
                self.calibration_state = "waiting"
                self.calibration_start_time = None
                self.stable_angles_buffer.clear()
                self.feedback = "Movement detected. Calibration canceled."
                self.calibration_progress = 0
                return False

            hold_time = time.time() - self.calibration_start_time
            self.calibration_progress = min(100, int((hold_time / self.calibration_hold_time) * 100))
            self.feedback = f"Calibrating... {self.calibration_progress}% ({hold_time:.1f}s/{self.calibration_hold_time}s)"

            if hold_time >= self.calibration_hold_time:
                self.complete_calibration(current_angle)
                return True
            return False

        # 校准完成
        elif self.calibration_state == "done":
            if abs(current_angle - self.calibration_data['calibrated_up_angle']) > 30:
                self.feedback = "Pose changed significantly. Consider recalibrating."
            return True
        return False

    def detect_pushup(self, current_angle):
        """检测俯卧撑动作"""
        if self.calibration_state != "done":
            return None

        # 初始化动作周期变量
        if not hasattr(self, 'min_angle_in_rep'):
            self.min_angle_in_rep = current_angle
        if self.rep_start_angle is None:
            self.rep_start_angle = current_angle
        if current_angle < self.min_angle_in_rep:
            self.min_angle_in_rep = current_angle

        calibrated_up = self.calibration_data['calibrated_up_angle']
        is_down_position = current_angle < (calibrated_up - 30)
        is_up_position = current_angle > (calibrated_up - 15)

        # 确定当前阶段
        current_stage = None
        if is_up_position:
            current_stage = "up"
        elif is_down_position:
            current_stage = "down"
            self.was_down = True

        # 状态转换：开始下降
        if self.stage == "up" and current_stage == "down":
            self.rep_start_angle = current_angle
            self.min_angle_in_rep = current_angle
            self.stage = "down"
            self.feedback = "Going down..."

        # 状态转换：完成上升，判断计数
        elif self.stage == "down" and current_stage == "up":
            actual_depth = calibrated_up - self.min_angle_in_rep

            if actual_depth >= self.min_depth_for_detection:
                if self.was_down:
                    if actual_depth >= self.min_depth_for_count:
                        self.counter += 1
                        self.feedback = f"Good! Pushup #{self.counter}"
                        self.performance_quality = "Good form"
                        self.speak(f"第{self.counter}个")
                        try:
                            winsound.Beep(1000, 150)
                        except Exception:
                            pass
                    else:
                        self.feedback = f"Too shallow!"
                        self.performance_quality = "Shallow - bend more"
                        self.speak(f"试着再低一点")
                else:
                    self.feedback = f"Partial movement!"
                    self.performance_quality = "Incomplete"
            else:
                self.feedback = f"Minimal movement!"
                self.performance_quality = "Minimal"

            # 重置状态
            self.stage = "up"
            self.min_angle_in_rep = calibrated_up
            self.was_down = False
            self.rep_start_angle = None

        # 初始状态判断
        elif self.stage is None:
            self.stage = "up" if current_angle > (calibrated_up - 15) else "down"

        # 下降过程中的实时反馈
        elif self.stage == "down":
            current_depth = calibrated_up - current_angle
            target_depth = self.min_depth_for_count
            if current_depth < 20:
                self.feedback = "Start bending..."
            elif current_depth < target_depth:
                self.feedback = f"Bending... "
            else:
                self.feedback = f"Good depth! "

        return current_stage

    def complete_calibration(self, calibrated_angle):
        """完成校准过程"""
        # 记录校准数据
        self.calibration_data['calibrated_up_angle'] = calibrated_angle
        self.calibration_data['calibrated_down_angle'] = calibrated_angle - 55 
        self.calibration_data['calibration_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.calibration_data['calibration_stability'] = max(self.stable_angles_buffer) - min(self.stable_angles_buffer)
        
        # 设置计数阈值
        self.up_threshold = calibrated_angle - 15
        self.down_threshold = calibrated_angle - 30

        self.calibration_state = "done"
        self.feedback = f"Calibration complete! "
        self.performance_quality = "Ready for pushups"
        self.speak("校准完成")
        self.stable_angles_buffer.clear()

        # 发送开始信号
        base_dir = os.path.dirname(os.path.abspath(__file__))
        signal_file = os.path.join(base_dir, "data", ".start_signal")
        try:
            with open(signal_file, "w") as f:
                f.write("start")
        except:
            pass

    def draw_calibration_display(self, image, current_angle, left_angle=None, right_angle=None):
        """绘制校准状态显示"""
        h, w, _ = image.shape
        FONT_TYPE = cv2.FONT_HERSHEY_TRIPLEX
        TEXT_COLOR = (155, 247, 255)
        status_colors = {"waiting": (160, 145, 246), "calibrating": (125, 0, 255), "done": TEXT_COLOR}
        status_color = status_colors.get(self.calibration_state, (255, 255, 255))

        # 绘制状态文本
        cv2.putText(image, f"Status: {self.calibration_state.upper()}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2, cv2.LINE_AA)

        # 绘制计数器
        if self.calibration_state == "done":
            cv2.putText(image, f"Pushups: {self.counter}", (w - 540, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, TEXT_COLOR, 5, cv2.LINE_AA)
    
        # 绘制反馈信息
        cv2.putText(image, self.feedback, (10, h - 80), FONT_TYPE, 1.2, TEXT_COLOR, 2, cv2.LINE_AA)

       # 绘制反馈信息
        cv2.putText(image, self.feedback, (10, h - 80), FONT_TYPE, 1.2, TEXT_COLOR, 2, cv2.LINE_AA)

        # 绘制校准进度条
        if self.calibration_state == "calibrating":
            bar_width, bar_height = 400, 20
            bar_x, bar_y = w // 2 - bar_width // 2, 150
            cv2.rectangle(image, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
            progress_width = int(bar_width * self.calibration_progress / 100)
            cv2.rectangle(image, (bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height), TEXT_COLOR, -1)

    def _speech_worker(self):
        """后台语音播放线程"""
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice.Rate, voice.Volume = -1, 100

        # 尝试设置中文语音
        try:
            zh_voices = voice.GetVoices("Language=804")
            if zh_voices.Count > 0:
                voice.Voice = zh_voices.Item(0)
        except Exception:
            pass

        while True:
            text = self.speech_queue.get()
            try:
                voice.Speak(text) 
            except Exception as e:
                print(f"TTS error: {e}")
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
                time.sleep(0.1)
                pythoncom.CoInitialize()
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Rate = -1
                voice.Volume = 100
            finally:
                self.speech_queue.task_done()

    def speak(self, text):
        """将要播报的文本加入队列"""
        if text:
            self.speech_queue.put(text)


def main():
    """主函数"""
    print("俯卧撑计数器启动")

    # 定义文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    count_file = os.path.join(data_dir, "pushup_count.txt")
    stop_signal_file = os.path.join(data_dir, ".stop_signal")
    flag_path = os.path.join(data_dir, "reset.flag")

    # 初始化计数器
    counter = AutoCalibrationPushupCounter()
    counter.speak("准备校准，请伸直手臂并保持稳定")

    # 初始化MediaPipe
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    # 初始化摄像头和窗口
    cap = cv2.VideoCapture(0)
    TARGET_WIDTH, TARGET_HEIGHT = 1280, 720
    WINDOW_NAME = 'Pushup Counter'
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, TARGET_WIDTH, TARGET_HEIGHT)

    with mp_pose.Pose(min_detection_confidence=0.7,min_tracking_confidence=0.7) as pose:
        while cap.isOpened():
            # 检查停止信号
            if os.path.exists(stop_signal_file):
                try:
                    with open(count_file, 'w') as f:
                        f.write(str(counter.counter))
                except Exception as e:
                    print(f"保存计数失败: {e}")
                break

            # 检查窗口是否被关闭
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

            # 读取并处理视频帧
            success, image = cap.read()
            if not success:
                continue
            image = cv2.resize(image, (TARGET_WIDTH, TARGET_HEIGHT))
            image = cv2.flip(image, 1)

             # 姿势检测
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = pose.process(image_rgb)
            image_rgb.flags.writeable = True
            image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

            # 处理检测结果
            try:
                if results.pose_landmarks:
                    mp_drawing.draw_landmarks(
                        image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=(155, 247, 255), thickness=2, circle_radius=2),
                        mp_drawing.DrawingSpec(color=(160, 145, 246), thickness=2, circle_radius=2)
                    )
                    avg_angle, left_angle, right_angle = counter.analyze_posture(
                        results.pose_landmarks.landmark
                    )
                    counter.update_calibration_state(avg_angle)
                    if counter.calibration_state == "done":
                        counter.detect_pushup(avg_angle)
                    counter.draw_calibration_display(image, avg_angle, left_angle, right_angle)
            except Exception as e:
                print(f"Error: {e}")

            # 处理外部重新校准请求
            if os.path.exists(flag_path):
                counter.calibration_state = "waiting"
                counter.counter = 0
                counter.stage = None
                counter.feedback = "Manual recalibration triggered"
                counter.stable_angles_buffer.clear()
                counter.speak("重新校准，请伸直手臂并保持稳定")
                try:
                    os.remove(flag_path)
                except Exception:
                    pass
            
            cv2.imshow(WINDOW_NAME, image)

            # 按键控制
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                try:
                    with open(count_file, 'w') as f:
                        f.write(str(counter.counter))
                except Exception as e:
                    print(f"保存计数失败: {e}")
                break
            elif key == ord('r'):
                counter.calibration_state = "waiting"
                counter.counter = 0
                counter.stage = None
                counter.feedback = "Manual recalibration triggered"
                counter.stable_angles_buffer.clear()

    # 清理资源
    cap.release()
    cv2.destroyAllWindows()

    # 保存计数
    try:
        with open(count_file, 'w') as f:
            f.write(str(counter.counter))
    except Exception as e:
        print(f"保存计数失败: {e}")

    print("程序结束")


if __name__ == "__main__":
    main()