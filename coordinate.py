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
    subtitle_path,
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
        f"[blurredv]subtitles='{subtitle_path}':force_style='Alignment=2,Fontsize=12,MarginV={MarginV}'[v]",  # 添加字幕，并调整字幕位置
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
    subtitle_path="test.srt",
    start_time=0,
    end_time=5,
    blur_height=185,
    blur_y=1413,
    MarginV=57,
)
