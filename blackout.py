import pyautogui
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk

class PreventSleepApp:
    def __init__(self, root):
        self.root = root
        self.root.title('절전방지')
        self.is_running = False
        self.interval = 60
        self.status_var = tk.StringVar()
        self.status_var.set("중지됨")

        self.run_button = ttk.Button(self.root, text="시작", command=self.start_prevent_sleep)
        self.run_button.grid(row=0, column=0)

        self.stop_button = ttk.Button(self.root, text="중지", command=self.stop_prevent_sleep)
        self.stop_button.grid(row=0, column=1)

        self.exit_button = ttk.Button(self.root, text="종료", command=self.root.destroy)
        self.exit_button.grid(row=0, column=2)

        self.status_label = ttk.Label(self.root, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, columnspan=3)

    def start_prevent_sleep(self):
        if not self.is_running:
            self.is_running = True
            self.status_var.set("실행중")
            self.status_label.config(background='green')
            self.thread = threading.Thread(target=self.prevent_sleep)
            self.thread.start()

    def stop_prevent_sleep(self):
        if self.is_running:
            self.is_running = False
            self.status_var.set("중지됨")
            self.status_label.config(background='red')

    def prevent_sleep(self):
        while self.is_running:
            pyautogui.press('shift')
            time.sleep(self.interval)

if __name__ == "__main__":
    root = tk.Tk()
    app = PreventSleepApp(root)
    root.mainloop()
