#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/22 11:35
# @file:chatgpt.py
import os
from openai import OpenAI

from check import check_json
from conf import Config
from utils import get_video_length


class Chat:

    def __init__(
        self, api_key=Config.api_key, base_url=Config.base_url, model=Config.model
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def chat(self, srt_path, video_path, param, depth=1):
        if depth > 10:
            # 递归超过10层，抛出致命错误
            raise Exception("递归超过10层，请检查代码逻辑")
        video_duration_formatted = get_video_length(video_path)
        with open(srt_path, "r", encoding="utf-8") as f:
            prompt = f.read()
        with open("init_prompt.txt", "r", encoding="utf-8") as f1:
            messages = [
                {
                    "role": "system",
                    "content": f1.read()
                    + "\n"
                    + "## 视频总长度"
                    + "\n"
                    + video_duration_formatted
                    + "\n"
                    + "## 内容"
                    + "\n"
                    + prompt
                    + "\n"
                    + "## 风格",
                }
            ]
        msg = messages + [
            {
                "role": "user",
                "content": param,
            }
        ]
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=msg,
            temperature=0.3,
        )
        result = completion.choices[0].message.content
        result = result.replace("```json", "").replace("```", "")
        if check_json(result, video_duration_formatted):
            return result
        else:
            return self.chat(srt_path, video_path, param, depth + 1)
