#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/22 15:36
# @file:utils.py
from moviepy.editor import VideoFileClip
from enum import Enum


def get_video_length(video_path):
    video = VideoFileClip(video_path)

    # 获取视频的总时长（秒）
    video_duration_sec = video.duration

    # 计算小时，分钟和秒
    hours = int(video_duration_sec // 3600)
    minutes = int((video_duration_sec % 3600) // 60)
    seconds = int(video_duration_sec % 60)

    # 格式化为 HH:MM:SS,MS
    # 由于不需要日期，所以不需要使用 strftime 方法
    video_duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d},000"
    return video_duration_formatted


class TaskStatus(str, Enum):
    pending = "待处理"
    in_progress = "处理中"
    completed = "已完成"
    failed = "异常"
