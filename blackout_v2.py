import pyautogui
import time
import threading
import tkinter as tk
from tkinter import messagebox, ttk

class PreventSleepApp:
    def __init__(self, root):
        self.root = root
        self.root.title('절전방지v2')
        self.is_running = False
        self.interval = 60
        self.check_interval = 1
        self.inactivity_duration = 30
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
        self.previous_position = pyautogui.position()
        self.inactivity_counter = 0

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

    def check_inactivity(self):
        current_position = pyautogui.position()
        if current_position == self.previous_position:
            self.inactivity_counter += self.check_interval
            if self.inactivity_counter >= self.inactivity_duration and not self.is_running:
                self.start_prevent_sleep()
        else:
            self.inactivity_counter = 0
            if self.is_running:
                self.stop_prevent_sleep()
        self.previous_position = current_position

    def prevent_sleep(self):
        while self.is_running:
            pyautogui.press('shift')
            time.sleep(self.interval)

    def run(self):
        while True:
            self.check_inactivity()
            time.sleep(self.check_interval)

if __name__ == "__main__":
    root = tk.Tk()
    app = PreventSleepApp(root)
    thread = threading.Thread(target=app.run)
    thread.start()
    root.mainloop()
