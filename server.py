#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2024/05/23 11:36
# @file:server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import sqlite3
from typing import List

from conf import Config
from utils import TaskStatus

app = FastAPI()

DATABASE = "tasks.db"


class Task(BaseModel):
    id: int
    style: str
    video_path: str
    srt_path: str
    blur_height: int
    blur_y: int
    MarginV: int
    status: TaskStatus


class TaskCreate(BaseModel):
    style: str
    video_path: str
    srt_path: str
    blur_height: int
    blur_y: int
    MarginV: int


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        style TEXT NOT NULL,
        video_path TEXT NOT NULL,
        srt_path TEXT NOT NULL,
        blur_height INTEGER NOT NULL,
        blur_y INTEGER NOT NULL,
        MarginV INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    init_db()


@app.post("/tasks/", response_model=List[Task])
def create_tasks_from_json(tasks: List[TaskCreate]):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    created_tasks = []

    for task in tasks:
        cursor.execute(
            "SELECT * FROM tasks WHERE style = ? AND video_path = ?  AND srt_path = ?",
            (task["style"], task["video_path"], task["srt_path"]),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
            INSERT INTO tasks (style, video_path, srt_path, blur_height, blur_y, MarginV, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task.style,
                    task.video_path,
                    task.srt_path,
                    task.blur_height,
                    task.blur_y,
                    task.MarginV,
                    TaskStatus.pending,
                ),
            )
            conn.commit()
            task_id = cursor.lastrowid
            created_tasks.append(
                {**task.model_dump(), "id": task_id, "status": TaskStatus.pending}
            )

    conn.close()
    return created_tasks


@app.get("/tasks/next", response_model=Task)
def get_next_task():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM tasks WHERE status = ? ORDER BY id LIMIT 1",
        (TaskStatus.pending,),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (TaskStatus.in_progress, row[0])
        )
        conn.commit()
        conn.close()
        return {
            "id": row[0],
            "style": row[1],
            "video_path": row[2],
            "srt_path": row[3],
            "blur_height": row[4],
            "blur_y": row[5],
            "MarginV": row[6],
            "status": TaskStatus.in_progress,
        }
    conn.close()
    raise HTTPException(status_code=404, detail="No pending tasks available")


class TaskUpdate(BaseModel):
    status: TaskStatus


@app.post("/tasks/{task_id}/update", response_model=Task)
def update_task_status(task_id: int, task_update: TaskUpdate):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    cursor.execute(
        "UPDATE tasks SET status = ? WHERE id = ?", (task_update.status, task_id)
    )
    conn.commit()
    conn.close()
    return {
        "id": row[0],
        "style": row[1],
        "video_path": row[2],
        "srt_path": row[3],
        "blur_height": row[4],
        "blur_y": row[5],
        "MarginV": row[6],
        "status": task_update.status,
    }


@app.get("/config")
def get_config():
    config = {
        "api_key": Config.api_key,
        "base_url": Config.base_url,
        "model": Config.model,
        "voice": Config.voice,
        "rate": Config.rate,
        "volume": Config.volume,
        "lz_path": Config.lz_path,
    }
    return config


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
