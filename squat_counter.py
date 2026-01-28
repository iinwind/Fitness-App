import cv2
import mediapipe as mp
import numpy as np
import time
import win32com.client
import threading
import os


class SquatCounter:
    def __init__(self):
        """初始化深蹲计数器"""
        # 初始化MediaPipe
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_pose = mp.solutions.pose

        # 初始化语音引擎
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.speaker.Rate = 0

        # 打开摄像头
        self.cap = cv2.VideoCapture(0)

        # 创建窗口
        cv2.namedWindow('Squat Counter', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Squat Counter', 1280, 720)

        # 计数变量
        self.squat_counter = 0
        self.stage = None
        self.last_spoken_count = 0

        # 状态变量
        self.status = "waiting"
        self.countdown_value = 3
        self.countdown_start_time = 0
        self.last_announced_number = -1

        # 显示控制
        self.current_display_text = ""
        self.current_voice_text = ""
        self.display_start_time = 0
        self.display_duration = 1.0
        self.speak_complete = True

        # 角度阈值
        self.squat_down_angle = 90
        self.squat_up_angle = 160

    def speak_and_display(self, display_text, voice_text=None, duration=1.0):
        """同时设置显示文字和语音播报"""
        if voice_text is None:
            voice_text = display_text

        self.current_display_text = display_text
        self.current_voice_text = voice_text
        self.display_start_time = time.time()
        self.display_duration = duration
        self.speak_complete = False

        # 开始语音播报
        def _speak():
            self.is_speaking = True
            try:
                self.speaker.Speak(self.current_voice_text)
            except:
                pass
            finally:
                self.is_speaking = False
                self.speak_complete = True

        thread = threading.Thread(target=_speak)
        thread.daemon = True
        thread.start()

    def clear_display(self):
        """清除显示"""
        self.current_display_text = ""
        self.display_start_time = 0

    def should_display(self):
        """检查是否应该显示当前文字"""
        if not self.current_display_text:
            return False

        # 检查显示时间是否超过持续时间
        if self.display_start_time > 0:
            elapsed = time.time() - self.display_start_time
            return elapsed < self.display_duration

        return True

    def speak_count(self):
        """播报当前计数"""
        if self.squat_counter > self.last_spoken_count:
            voice_text = f"第{self.squat_counter}个"

            def _speak():
                try:
                    self.speaker.Speak(voice_text)
                except:
                    pass

            thread = threading.Thread(target=_speak)
            thread.daemon = True
            thread.start()

            self.last_spoken_count = self.squat_counter

    @staticmethod
    def calculate_angle(a, b, c):
        """计算三个点之间的角度"""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)

        ba = a - b
        bc = c - b

        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(cosine_angle)
        angle = np.degrees(angle)

        return angle

    def check_standing(self, angle):
        """检查是否站立"""
        return angle > 160

    def process_frame(self, image, results):
        """处理一帧图像，进行深蹲计数"""
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            height, width, _ = image.shape

            # 获取左腿关键点坐标
            hip = [landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].x * width,
                   landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].y * height]

            knee = [landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].x * width,
                    landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].y * height]

            ankle = [landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].x * width,
                     landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].y * height]

            # 计算膝盖角度
            angle = self.calculate_angle(hip, knee, ankle)

            # 状态机
            if self.status == "waiting":
                # 等待阶段：显示和播报"Please stand straight" / "请站直"
                if self.current_display_text == "":
                    self.speak_and_display("Please stand straight", "请站直", duration=999)

                # 检测是否站立，并且等待语音播报完成
                if self.speak_complete and self.check_standing(angle):
                    self.status = "ready"
                    self.clear_display()
                    self.speak_and_display("Ready", "准备", duration=1.0)

            elif self.status == "ready":
                # 准备阶段：等待"准备"播报完成并且显示时间结束
                if self.speak_complete and not self.should_display():
                    self.status = "countdown"
                    self.countdown_start_time = time.time()
                    self.last_announced_number = -1

            elif self.status == "countdown":
                # 倒计时阶段
                elapsed = time.time() - self.countdown_start_time
                remaining = self.countdown_value - int(elapsed)

                if remaining > 0:
                    # 播报和显示倒计时数字
                    if remaining != self.last_announced_number:
                        display_text = f"{remaining}"
                        chinese_numbers = {3: "三", 2: "二", 1: "一"}
                        voice_text = chinese_numbers.get(remaining, str(remaining))
                        self.clear_display()
                        self.speak_and_display(display_text, voice_text, duration=1.0)
                        self.last_announced_number = remaining
                else:
                    # 倒计时结束
                    self.status = "start"
                    self.clear_display()
                    self.speak_and_display("Start!", "开始", duration=1.0)

            elif self.status == "start":
                # 开始阶段：等待"开始"播报完成并且显示时间结束
                if self.speak_complete and not self.should_display():
                    self.status = "counting"
                    self.clear_display()

                    # 发送开始信号给主程序
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    signal_file = os.path.join(base_dir, "data", ".start_signal")
                    try:
                        with open(signal_file, "w") as f:
                            f.write("start")
                    except:
                        pass

            elif self.status == "counting":
                # 计数阶段
                if angle > self.squat_up_angle:
                    if self.stage == "down":
                        self.squat_counter += 1
                        self.speak_count()
                    self.stage = "up"
                elif angle < self.squat_down_angle:
                    self.stage = "down"

            # 绘制骨架
            self.mp_drawing.draw_landmarks(
                image, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(155, 247, 255), thickness=2, circle_radius=2),
                self.mp_drawing.DrawingSpec(color=(160, 145, 246), thickness=2, circle_radius=2)
            )

        return image

    def display_info(self, image):
        """在图像上显示信息"""
        height, width, _ = image.shape

        # 显示当前文字
        if self.should_display() and self.current_display_text:
            text = self.current_display_text

            # 根据文字内容调整位置和大小
            if text == "Please stand straight":
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 2, 3)[0]
                x = (width - text_size[0]) // 2
                y = height // 2
                cv2.putText(image, text, (x, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (155, 247, 255), 3)

            elif text == "Ready":
                # 显示Ready
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_TRIPLEX, 3, 5)[0]
                x = (width - text_size[0]) // 2
                y = height // 2
                cv2.putText(image, text, (x, y),
                            cv2.FONT_HERSHEY_TRIPLEX, 3, (155, 247, 255), 8)

            elif text == "Start!":
                # 显示Start!
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_TRIPLEX, 4, 8)[0]
                x = (width - text_size[0]) // 2
                y = height // 2
                cv2.putText(image, text, (x, y),
                            cv2.FONT_HERSHEY_TRIPLEX, 4, (155, 247, 255), 8)

            elif text.isdigit() and len(text) == 1:
                # 显示倒计时数字
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_TRIPLEX, 8, 15)[0]
                x = (width - text_size[0]) // 2
                y = height // 2
                cv2.putText(image, text, (x, y),
                            cv2.FONT_HERSHEY_TRIPLEX, 8, (160, 145, 246), 15)

        # 在计数阶段显示计数信息
        if self.status == "counting":
            cv2.putText(image, f'Squats: {self.squat_counter}',
                        (50, 100), cv2.FONT_HERSHEY_TRIPLEX, 2, (155, 247, 255), 4)

            if self.stage:
                status_text = "up" if self.stage == "up" else "down"
                cv2.putText(image, f'Status: {status_text}',
                            (50, 150), cv2.FONT_HERSHEY_TRIPLEX, 1, (255, 255, 255), 2)

        return image

    def run(self):
        """运行深蹲计数器主循环"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        count_file = os.path.join(data_dir, "squat_count.txt")
        stop_signal_file = os.path.join(data_dir, ".stop_signal")
        flag_path = os.path.join(data_dir, "reset.flag")
        

        with self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while self.cap.isOpened():
                if os.path.exists(stop_signal_file):
                    try:
                        with open(count_file, 'w') as f:
                            f.write(str(self.squat_counter))
                        print(f"计数已保存: {self.squat_counter}")
                    except Exception as e:
                        print(f"保存计数失败: {e}")
                    break

                if cv2.getWindowProperty('Squat Counter', cv2.WND_PROP_VISIBLE) < 1:
                    break

                ret, frame = self.cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                frame = cv2.resize(frame, (1280, 720))
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                results = pose.process(image)
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                image = self.process_frame(image, results)
                image = self.display_info(image)

                cv2.imshow('Squat Counter', image)

                key = cv2.waitKey(10)
                if key & 0xFF == ord('q'):
                    # 退出前保存计数
                    try:
                        with open(count_file, 'w') as f:
                            f.write(str(self.squat_counter))
                    except Exception as e:
                        print(f"保存计数失败: {e}")
                    break
                elif key & 0xFF == ord('r'):
                    # 等效的重置逻辑
                    self.squat_counter = 0
                    self.stage = None
                    self.last_spoken_count = 0
                    self.status = "waiting"
                    self.current_display_text = ""
                    self.current_voice_text = ""
                    self.last_announced_number = -1
                    self.display_start_time = 0
                    self.speak_complete = True

                if os.path.exists(flag_path):
                    self.squat_counter = 0
                    self.stage = None
                    self.last_spoken_count = 0
                    self.status = "waiting"
                    self.current_display_text = ""
                    self.current_voice_text = ""
                    self.last_announced_number = -1
                    self.display_start_time = 0
                    self.speak_complete = True
                    try:
                        os.remove(flag_path)
                    except Exception:
                        pass
        # 程序结束前确保保存计数
        try:
            with open(count_file, 'w') as f:
                f.write(str(self.squat_counter))
        except Exception as e:
            print(f"保存计数失败: {e}")

        self.cap.release()
        cv2.destroyAllWindows()


def main():
    """主函数"""
    print("深蹲计数器启动")

    squat_counter = SquatCounter()
    try:
        squat_counter.run()
    except Exception as e:
        print(f"程序出错: {e}")
    finally:
        if squat_counter.cap.isOpened():
            squat_counter.cap.release()
        cv2.destroyAllWindows()

    print("程序结束")

if __name__ == "__main__":
    main()