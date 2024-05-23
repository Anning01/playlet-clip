#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/22 18:57
# @file:coordinate.py
import subprocess


def process_video(
    video_path,
    output_path,
    start_time,
    end_time,
    blur_height,
    blur_y,
    MarginV,
    log_level="error",
):
    command = [
        "ffmpeg",
        "-v",
        log_level,  # 设置日志级别
        "-y",
        "-ss",
        str(start_time),  # 设置起始时间
        "-to",
        str(end_time),  # 设置结束时间
        "-i",
        video_path,  # 输入视频文件
        "-filter_complex",
        f"[0:v]crop=iw:{blur_height}:{blur_y}[gblur];"  # 裁剪出底部用于模糊的区域
        f"[gblur]gblur=sigma=20[gblurred];"  # 对裁剪出的区域应用高斯模糊
        f"[0:v][gblurred]overlay=0:{blur_y}[blurredv];"  # 将模糊区域覆盖回原视频
        f"[blurredv]drawtext=text='这是一段测试字幕':fontcolor=white:fontsize=24:x=(w-tw)/2:y=h-th-{MarginV}[v]",  # 添加测试字幕
        "-map",
        "[v]",  # 映射处理过的视频流
        "-c:v",
        "libx264",  # 视频使用x264编码
        "-preset",
        "ultrafast",  # 选择预设以平衡编码速度和质量
        output_path,  # 输出文件路径
    ]

    subprocess.run(command, check=True)


# 示例调用
process_video(
    video_path="merged_1.mp4",
    output_path="output_video.mp4",
    start_time=3,
    end_time=10,
    blur_height=50,
    blur_y=200,
    MarginV=50,
)
