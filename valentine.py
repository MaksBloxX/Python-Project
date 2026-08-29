import tkinter as tk
import time
import threading
import math
from urllib.request import urlopen

# ---------------- typing effect ----------------
def type_text(widget, text, delay=0.03):
    widget.config(text="")
    for ch in text:
        widget.config(text=widget.cget("text") + ch)
        time.sleep(delay)

def run_lines(lines, delay_between=0.7):
    for line in lines:
        type_text(text_label, line, 0.03)
        time.sleep(delay_between)

# ---------------- heartbeat animation ----------------
pulse_t = 0.0

def heartbeat():
    global pulse_t

    pulse_t += 0.12
    scale = 1.0 + 0.08 * math.sin(pulse_t) + 0.04 * math.sin(2 * pulse_t)

    # clear previous heart
    canvas.delete("heart")

    cx, cy = 215, 120
    w = 140 * scale
    h = 120 * scale

    points = [
        (cx, cy + h*0.35),
        (cx - w*0.50, cy - h*0.05),
        (cx - w*0.45, cy - h*0.45),
        (cx - w*0.15, cy - h*0.55),
        (cx, cy - h*0.35),
        (cx + w*0.15, cy - h*0.55),
        (cx + w*0.45, cy - h*0.45),
        (cx + w*0.50, cy - h*0.05),
    ]

    canvas.create_polygon(points, fill="#ff5a8a", outline="", smooth=True, tags="heart")

    # floating mini hearts
    for i in range(7):
        ox = (i - 3) * 35
        oy = 40 + (i % 2) * 15
        s = 0.35 + 0.08 * math.sin(pulse_t + i)

        canvas.create_text(
            cx + ox, cy + oy,
            text="💓",
            font=("Segoe UI Emoji", int(18*s)+10),
            tags="heart"
        )

    # ONLY ONCE
    root.after(60, heartbeat)

# ---------------- load image from url (NO requests) ----------------
def load_image_from_url(url):
    data = urlopen(url).read()
    return tk.PhotoImage(data=data)

# ---------------- funny exit ----------------
laugh_img = None

def funny_exit():
    def work():
        global laugh_img

        # disable buttons
        try:
            exit_btn.config(state="disabled")
            start_btn.config(state="disabled")
            yes_btn.config(state="disabled")
            no_btn.config(state="disabled")
        except:
            pass

        text_label.config(text="")

        # load image once
        try:
            if laugh_img is None:
                laugh_img = load_image_from_url(
                    "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f602.png"
                )
        except:
            laugh_img = None

        # show image
        if laugh_img:
            big_img_label.config(image=laugh_img)
            big_img_label.place(x=170, y=70)
        else:
            big_img_label.config(text="HAHA!", font=("Segoe UI", 45, "bold"))
            big_img_label.place(x=135, y=80)

        time.sleep(3)
        root.destroy()

    threading.Thread(target=work).start()

# ---------------- app logic ----------------
def show_exit_button():
    exit_btn.place(x=160, y=290, width=110, height=30)

def on_yes():
    def work():
        yes_btn.config(state="disabled")
        no_btn.config(state="disabled")

        lines = [
            "YAYYYYY 😭❤️",
            "Okay... listen 😳✨",
            "You are my favorite person 💖",
            "I promise to keep you smiling 😊",
            "💘 Happy Valentine's Day 💘"
        ]
        run_lines(lines, 0.85)
        show_exit_button()

    threading.Thread(target=work).start()

def on_no():
    def work():
        yes_btn.config(state="disabled")
        no_btn.config(state="disabled")

        lines = [
            "🥺 Oh okay...",
            "No problem...",
            "I still wish you happiness 💙",
            "💖 Happy Valentine's Day 💖"
        ]
        run_lines(lines, 0.85)
        show_exit_button()

    threading.Thread(target=work).start()

def start_question():
    def work():
        start_btn.config(state="disabled")

        lines = [
            "💘 Hey...",
            "I have one question 😳",
            "💍 Will you be my Valentine?"
        ]
        run_lines(lines, 0.85)

        yes_btn.place(x=85, y=250, width=120, height=35)
        no_btn.place(x=225, y=250, width=120, height=35)

    threading.Thread(target=work).start()

# ---------------- GUI ----------------
root = tk.Tk()
root.title("Valentine Love App 💖")
root.geometry("430x320")
root.resizable(False, False)

canvas = tk.Canvas(root, width=430, height=240, highlightthickness=0, bg="#fff0f5")
canvas.place(x=0, y=0)

text_label = tk.Label(
    root,
    text="",
    font=("Segoe UI", 14, "bold"),
    bg="#fff0f5",
    fg="#222",
    wraplength=390,
    justify="center"
)
text_label.place(x=20, y=65, width=390, height=90)

# Big image label (hidden)
big_img_label = tk.Label(root, bg="#fff0f5")

start_btn = tk.Button(root, text="Start 💘", font=("Segoe UI", 12), command=start_question)
start_btn.place(x=165, y=210, width=100, height=35)

yes_btn = tk.Button(root, text="YES ❤️", font=("Segoe UI", 12), command=on_yes)
no_btn  = tk.Button(root, text="NO 💔",  font=("Segoe UI", 12), command=on_no)

exit_btn = tk.Button(root, text="Exit", font=("Segoe UI", 12), command=funny_exit)

heartbeat()
root.mainloop()
