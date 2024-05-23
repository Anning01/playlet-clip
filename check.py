# !/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/07 18:06
# @file:check_json.py
import json
import re

from utils import get_video_length
from datetime import datetime

# 正确时间格式的正则表达式
time_pattern = re.compile(r"^\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}$")


def compare_time_strings(time1, time2):
    time_format = "%H:%M:%S,%f"
    t1 = datetime.strptime(time1, time_format)
    t2 = datetime.strptime(time2, time_format)

    if t1 >= t2:
        return True
    else:
        return False


# 验证时间是否正确
def is_valid_time(video_duration_formatted, time_str):
    if not time_pattern.match(time_str):
        return False
    start_time, end_time = time_str.split(" --> ")
    if not all(
        is_valid_individual_time(video_duration_formatted, t)
        for t in [start_time, end_time]
    ):
        return False
    if not compare_time_strings(end_time, start_time):
        return False
    return True


# 验证单个时间是否合法
def is_valid_individual_time(video_duration_formatted, individual_time):
    hours, minutes, seconds = individual_time.split(":")
    seconds, milliseconds = seconds.split(",")
    if int(minutes) >= 60 or int(seconds) >= 60:
        return False
    return compare_time_strings(video_duration_formatted, individual_time)


def check_json(content, video_duration_formatted, video_path=None):
    # video_duration_formatted = get_video_length(video_path)
    try:
        data = json.loads(content)
        previous_end_time = None
        for item in data:
            if "type" not in item or "time" not in item:
                print("文件错误，缺少必要的字段")
                return False
            if item["type"] not in ["解说", "video"]:
                print("文件错误，type字段只能是'解说'或'video'")
                return False
            if not is_valid_time(video_duration_formatted, item["time"]):
                print("文件错误，时间格式不正确")
                return False
            start_time, end_time = item["time"].split(" --> ")
            if previous_end_time and not compare_time_strings(
                end_time, previous_end_time
            ):
                print("文件错误，下一段的开始时间必须大于或等于上一段的结束时间")
                return False
            previous_end_time = end_time
            if item["type"] == "解说" and "content" not in item:
                print("文件错误，缺少content字段")
                return False
    except json.JSONDecodeError:
        print("文件错误，内容不是有效的JSON格式")
        return False
    except Exception as e:
        print(f"文件错误，发生未知错误：{e}")
        return False
    return True


if __name__ == "__main__":
    path = (
        "/Users/anning/PycharmProjects/untitled/playlet/测试文件/合并视频/merged_1.mp4"
    )
    data = """
    [
                {
                    "type": "解说",
                    "content": "跟我来，让我来带你们走进我的世界。",
                    "time": "00:00:00,000 --> 00:00:03,000"
                },
                {
                    "type": "video",
                    "time": "00:00:00,166 --> 00:00:05,132"
                },
                {
                    "type": "解说",
                    "content": "在这充满变化的时代，我手中的针，既是救赎也是毁灭。",
                    "time": "00:00:07,566 --> 00:00:10,532"
                },
                {
                    "type": "video",
                    "time": "00:00:10,533 --> 00:00:15,999"
                },
                {
                    "type": "解说",
                    "content": "但在所有的头衔中，我最自豪的是成为张甜甜的伴侣。",
                    "time": "00:00:16,400 --> 00:00:17,831"
                },
                {
                    "type": "video",
                    "time": "00:00:24,100 --> 00:00:36,199"
                },
                {
                    "type": "解说",
                    "content": "看，这就是生活，利益，权力，感情纠葛，如此这般。",
                    "time": "00:00:36,500 --> 00:00:38,264"
                },
                {
                    "type": "video",
                    "time": "00:00:38,333 --> 00:00:49,265"
                },
                {
                    "type": "解说",
                    "content": "张甜甜，这个名字，曾是我生命中的阳光。",
                    "time": "00:00:49,400 --> 00:00:50,099"
                },
                {
                    "type": "video",
                    "time": "00:00:52,333 --> 00:01:08,789"
                },
                {
                    "type": "解说",
                    "content": "爱情，婚姻，如同商场上的谈判，总有失败的一方。",
                    "time": "00:01:09,025 --> 00:01:10,955"
                },
                {
                    "type": "video",
                    "time": "00:01:14,124 --> 00:01:29,855"
                },
                {
                    "type": "解说",
                    "content": "时光如水，有些事，选择结束，也是另一种开始。",
                    "time": "00:01:30,092 --> 00:01:30,655"
                },
                {
                    "type": "video",
                    "time": "00:01:52,924 --> 00:02:57,906"
                },
                {
                    "type": "解说",
                    "content": "而这，或许只是另一个新的起点。",
                    "time": "00:02:58,000 --> 00:03:03,000"
                }
            ]
    """
    print(check_json(data, path))
