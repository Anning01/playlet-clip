#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/22 11:32
# @file:main.py
import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta

import requests

from char2voice import create_voice_srt_new2
from chatgpt import Chat
from conf import Config
from mutagen.mp3 import MP3
from random import sample


class Playlet:

    def sort_by_number(self, filename):
        numbers = re.findall(r"\d+", filename)
        if numbers:
            return [int(num) for num in numbers]
        else:
            return filename

    def run(self):
        for style in Config.style_list:
            path_ = os.path.join(
                os.path.dirname(Config.srt_path),
                os.path.basename(Config.srt_path).split(".")[0],
            )
            txt_path = os.path.join(path_, style.split("：")[0] + ".txt")
            out_path = os.path.join(path_, style.split("：")[0] + ".mp4")
            os.makedirs(path_, exist_ok=True)
            if not os.path.exists(txt_path):
                result = Chat().chat(Config.srt_path, Config.video_path, style)
                with open(
                    txt_path,
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(result)
            else:
                with open(txt_path, "r", encoding="utf-8") as f:
                    result = f.read()
            data = json.loads(result)
            end_time = "00:00:00.000"
            if os.path.exists(out_path):
                continue
            # 先将所有解说转成声音
            for k, v in enumerate(data):
                if os.path.exists(f"{k}.mp4"):
                    continue
                start_time = v["time"].split(" --> ")[0]
                end_time_ = v["time"].split(" --> ")[-1]
                res = self.calculate_time_difference_srt(f"{end_time} --> {start_time}")
                if res[0] == "-":
                    start_time = end_time
                if v["type"] == "解说":
                    self.generate_speech(v["content"], str(k))
                    duration = self.get_mp3_length_formatted(f"{k}.mp3")
                    result = str(self.add_seconds_to_time(start_time, duration))
                    if "." in result:
                        result = result.replace(".", ",")[:-3]
                    else:
                        result = result + ",000"
                    end_time = result
                else:
                    duration = self.calculate_time_difference_srt(
                        f"{start_time} --> {end_time_}"
                    )
                if duration[0] == "-" or duration == "00:00:00.000":
                    continue

                start_time = start_time.replace(",", ".")
                if not os.path.exists(f"{k}.mp4"):
                    self.trim_video(Config.video_path, f"{k}.mp4", start_time, duration, Config.lz_path)
                if v["type"] == "解说":
                    self.process_video(
                        f"{k}.mp4", f"{k}.mp3", f"{k}.srt", f"out{k}.mp4"
                    )
            # 合成视频
            self.concat_videos(
                [
                    f"{i_}.mp4"
                    for i_, v in enumerate(data)
                    if os.path.exists(f"{i_}.mp4")
                ],
                out_path,
            )

    def calculate_time_difference_srt(self, srt_timestamp):
        """
        计算SRT时间戳之间的差值，并以标准的时间格式返回。

        参数：
        srt_timestamp (str): 形式为 "hh:mm:ss.sss --> hh:mm:ss.sss" 或 "hh:mm:ss --> hh:mm:ss" 的时间戳字符串。

        返回：
        formatted_difference (str): 时间差，格式为 "hh:mm:ss.sss" 或 "hh:mm:ss"。
        """
        # 解析开始和结束时间
        start_time_str, end_time_str = srt_timestamp.replace(",", ".").split(" --> ")

        # 定义时间格式
        if "." in start_time_str:  # 检查时间戳是否包含毫秒
            time_format = "%H:%M:%S.%f"
        else:
            time_format = "%H:%M:%S"

        # 将字符串转换为datetime对象
        start_time = datetime.strptime(start_time_str, time_format)
        end_time = datetime.strptime(end_time_str, time_format)

        # 计算时间差
        time_difference = end_time - start_time

        # 计算差异的总秒数
        total_seconds = time_difference.total_seconds()

        # 计算小时、分钟、秒和可选的毫秒
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)

        # 根据输入是否包含毫秒来决定输出格式
        if "." in start_time_str:
            formatted_difference = (
                f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
            )
        else:
            formatted_difference = f"{hours:02}:{minutes:02}:{seconds:02}"

        return formatted_difference

    def generate_speech(
        self,
        text,
        file_name,
        p_voice=Config.voice,
        p_rate=Config.rate,
        p_volume=Config.volume,
    ):
        if not os.path.exists(f"{file_name}.mp3"):
            # 将文本转成语音并且保存
            asyncio.run(
                create_voice_srt_new2(file_name, text, "./", p_voice, p_rate, p_volume)
            )

    def get_mp3_length_formatted(self, file_path):
        """
        获取MP3文件的长度，并将其格式化为 "hh:mm:ss.sss" 格式。

        参数：
        file_path (str): MP3文件的路径。

        返回：
        formatted_length (str): 音频长度，格式化为 "hh:mm:ss.sss"。
        """
        audio = MP3(file_path)
        total_seconds = audio.info.length

        # 计算小时、分钟、秒和毫秒
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)

        # 格式化时间长度为字符串，确保小时、分钟、秒都是双位数字，毫秒是三位数字
        formatted_length = f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

        return formatted_length

    def add_seconds_to_time(self, time_str, seconds_to_add):
        seconds_to_add = seconds_to_add.replace(".", ",")
        # 定义时间格式
        time_format = "%H:%M:%S,%f"

        try:
            # 解析时间字符串
            time_obj = datetime.strptime(time_str, time_format)

            # 解析要添加的秒数（时间间隔）
            interval_obj = datetime.strptime(seconds_to_add, time_format)
            total_seconds_to_add = (
                interval_obj.hour * 3600
                + interval_obj.minute * 60
                + interval_obj.second
                + interval_obj.microsecond / 1000000
            )

            # 添加秒数
            new_time_obj = time_obj + timedelta(seconds=total_seconds_to_add)

            # 返回结果
            return new_time_obj.time()

        except ValueError:
            return "Invalid time format"


    def get_video(self, path):
        list_ = []
        for file_name in os.listdir(path):
            if file_name == r'Thumbs.db': continue
            list_.append(path + '/' + file_name)
        return list_

    def trim_video(
        self, input_path, output_path, start_time, duration, lz_path=None, log_level="error"
    ):
        """
        使用FFmpeg截取视频的指定时间段。

        参数：
        input_path (str): 原视频文件的路径。
        output_path (str): 输出视频文件的路径。
        start_time (str): 开始时间，格式应为 "hh:mm:ss" 或 "ss"。
        duration (str): 截取的持续时间，格式同上。
        """
        if lz_path is None:
            
            # 构建FFmpeg命令
            command = [
                "ffmpeg",
                "-v",
                log_level,  # 设置日志级别
                "-i",
                input_path,  # 输入文件
                "-ss",
                start_time,  # 开始时间
                "-t",
                duration,  # 持续时间
                # '-c', 'copy',  # 使用相同的编码进行复制
                "-ac",
                str(2),
                "-ar",
                str(24000),
                output_path,  # 输出文件
            ]
        else:
            fbl_lz1_path = os.path.join(sample(self.get_video(os.path.join(lz_path)), 1)[0])
            # 构建FFmpeg命令
            command = [
                'ffmpeg',
                "-v",
                log_level,  # 设置日志级别
                '-i', input_path,  # 输入文件
                '-i', fbl_lz1_path,  # 输入文件
                '-ss', start_time,  # 开始时间
                '-t', duration,  # 持续时间
                # '-c', 'copy',  # 使用相同的编码进行复制
                "-filter_complex",
                "[1:v]format=yuva444p,colorchannelmixer=aa=0.001[valpha];[0:v][valpha]overlay=(W-w):(H-h)",
                "-ac", str(2), 
                "-ar", str(24000),
                output_path  # 输出文件
            ]

        # 执行命令
        subprocess.run(command)

    def process_video(
        self,
        video_path,
        audio_path,
        subtitle_path,
        output_path,
        blur_height=Config.blur_height,
        blur_y=Config.blur_y,
        MarginV=Config.MarginV,
        log_level="error",
    ):

        subtitle_path = subtitle_path.replace("\\", "/")
        command = [
            "ffmpeg",
            "-v",
            log_level,  # 设置日志级别
            "-y",
            "-i",
            video_path,  # 输入视频文件
            "-i",
            audio_path,  # 输入音频文件
            "-filter_complex",
            f"[0:v]crop=iw:{blur_height}:{blur_y}[gblur];"  # 裁剪出底部用于模糊的区域
            f"[gblur]gblur=sigma=20[gblurred];"  # 对裁剪出的区域应用高斯模糊
            f"[0:v][gblurred]overlay=0:{blur_y}[blurredv];"  # 将模糊区域覆盖回原视频
            f"[blurredv]subtitles='{subtitle_path}':force_style='Alignment=2,Fontsize=12,MarginV={MarginV}'[v];"  # 添加字幕，并调整字幕位置
            f"[1:a]aformat=channel_layouts=stereo[a]",  # 确保音频为立体声
            "-map",
            "[v]",  # 映射处理过的视频流
            "-map",
            "[a]",  # 映射处理过的音频流
            "-c:v",
            "libx264",  # 视频使用x264编码
            "-c:a",
            "aac",  # 音频使用AAC编码
            "-strict",
            "experimental",  # 如果需要，使用实验性功能
            "-preset",
            "fast",  # 选择预设以平衡编码速度和质量
            output_path,  # 输出文件路径
        ]

        subprocess.run(command, check=True)
        os.replace(output_path, video_path)  # 用输出文件替换原始文件

        # 完成后删除subtitle_path字幕文件
        os.remove(subtitle_path)
        os.remove(audio_path)

    def concat_videos(self, video_files, output_file, log_level="error"):
        # 创建一个临时文件列表
        with open("filelist.txt", "w", encoding="utf-8") as file:
            for video in video_files:
                file.write(f"file '{video}'\n")

        # 构建FFmpeg命令
        command = [
            "ffmpeg",
            "-loglevel",
            log_level,
            "-y",
            "-f",
            "concat",  # 使用concat格式
            "-safe",
            "0",  # 允许非安全文件名
            "-i",
            "filelist.txt",  # 使用文件列表
            "-c",
            "copy",  # 视频流直接复制
            output_file,
        ]

        # 调用FFmpeg
        subprocess.run(command)

        # 删除临时文件
        os.remove("filelist.txt")
        # 删除所有视频文件
        for video in video_files:
            os.remove(video)

    def reported(self, server_url, id, status):
        response = requests.post(
            f"{server_url}/tasks/{id}/update", json={"status": status}
        )
        return response

    def client(self, server_url):
        if not server_url.startswith("http://") and not server_url.startswith(
            "https://"
        ):
            server_url = "http://" + server_url
        config = requests.get(f"{server_url}/config").json()
        while True:
            try:
                # 从服务器获取下一个任务
                response = requests.get(f"{server_url}/tasks/next")
                if response.status_code == 200:
                    task = response.json()
                    print(f"Processing task {task['id']}")
                    try:
                        path_ = os.path.join(
                            os.path.dirname(task["srt_path"]),
                            os.path.basename(task["srt_path"]).split(".")[0],
                        )
                        txt_path = os.path.join(
                            path_, task["style"].split("：")[0] + ".txt"
                        )
                        out_path = os.path.join(
                            path_, task["style"].split("：")[0] + ".mp4"
                        )
                        os.makedirs(path_, exist_ok=True)
                        if not os.path.exists(txt_path):
                            result = Chat(
                                config["api_key"], config["base_url"], config["model"]
                            ).chat(task["srt_path"], task["video_path"], task["style"])
                            with open(
                                txt_path,
                                "w",
                                encoding="utf-8",
                            ) as f:
                                f.write(result)
                        else:
                            with open(txt_path, "r", encoding="utf-8") as f:
                                result = f.read()
                        data = json.loads(result)
                        end_time = "00:00:00.000"
                        if os.path.exists(out_path):
                            self.reported(server_url, task["id"], "已完成")
                            continue
                        # 先将所有解说转成声音
                        for k, v in enumerate(data):
                            if os.path.exists(f"{k}.mp4"):
                                continue
                            start_time = v["time"].split(" --> ")[0]
                            end_time_ = v["time"].split(" --> ")[-1]
                            res = self.calculate_time_difference_srt(
                                f"{end_time} --> {start_time}"
                            )
                            if res[0] == "-":
                                start_time = end_time
                            if v["type"] == "解说":
                                self.generate_speech(
                                    v["content"],
                                    str(k),
                                    config["voice"],
                                    config["rate"],
                                    config["volume"],
                                )
                                duration = self.get_mp3_length_formatted(f"{k}.mp3")
                                result = str(
                                    self.add_seconds_to_time(start_time, duration)
                                )
                                if "." in result:
                                    result = result.replace(".", ",")[:-3]
                                else:
                                    result = result + ",000"
                                end_time = result
                            else:
                                duration = self.calculate_time_difference_srt(
                                    f"{start_time} --> {end_time_}"
                                )
                            if duration[0] == "-" or duration == "00:00:00.000":
                                continue

                            start_time = start_time.replace(",", ".")
                            if not os.path.exists(f"{k}.mp4"):
                                self.trim_video(
                                    task["video_path"], f"{k}.mp4", start_time, duration, config["lz_path"]
                                )
                            if v["type"] == "解说":
                                self.process_video(
                                    f"{k}.mp4",
                                    f"{k}.mp3",
                                    f"{k}.srt",
                                    f"out{k}.mp4",
                                    task["blur_height"],
                                    task["blur_y"],
                                    task["MarginV"],
                                )
                        # 合成视频
                        self.concat_videos(
                            [
                                f"{i_}.mp4"
                                for i_, v in enumerate(data)
                                if os.path.exists(f"{i_}.mp4")
                            ],
                            out_path,
                        )
                        # 任务完成后上报服务器
                        self.reported(server_url, task["id"], "已完成")
                    except Exception as e:
                        print(f"Failed to process task {task['id']}: {e}")
                        # 处理失败后上报服务器
                        self.reported(server_url, task["id"], "异常")
                else:
                    print("No pending tasks available. Sleeping for 10 seconds.")
                    time.sleep(10)  # 如果没有任务，休眠10秒

            except Exception as e:
                print(f"Error fetching task: {e}")
                time.sleep(10)  # 发生错误时休眠10秒


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "client":
        if len(sys.argv) != 3:
            print("Usage: python main.py client <server_url>")
            sys.exit(1)
        server_url = sys.argv[2]
        Playlet().client(server_url)
    else:
        Playlet().run()
