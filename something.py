import cv2 ##basically does everything for me
import tkinter as tk # creates the screen
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading # for efficient processing
import queue
import time
import numpy as np #maths

# Full luminance gradient with ASCII + block + Braille
ASCII_CHARS = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$▓▒░█"

# Braille mapping helper
def pixels_to_braille(block):
    """Convert 2x4 pixel block (list of 8 luminance values 0-1) to a Braille char."""
    value = 0
    for i, p in enumerate(block):
        if p > 0.5:  # threshold for “on”
            value |= (1 << i)
    return chr(0x2800 + value)

class ASCIICamApp:
    def __init__(self, master, cam_index=1, ascii_width=160): ##default init
        self.master = master
        self.master.title("Ultra HD Colored ASCII Webcam")

        self.ascii_width = ascii_width
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = True

        # open camera
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            tk.Label(master, text="Error: Cannot open camera").pack()
            return

        # tkinter canvas for display
        self.canvas = tk.Canvas(master)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.photo = None

        # fonts
        self.font = ImageFont.load_default()

        # start capture + processing thread
        self.thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.thread.start()

        ##GUI update loop
        self.update_frame()
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def frame_to_ascii_image(self, frame):
        # 1. Boost Saturation for more vibrant colors
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # Multiply saturation by a factor greater than 1.0 (e.g., 1.5 for 50% more vibrant)
        s = cv2.multiply(s, 1.5)
        
        # Merge back and convert to BGR
        hsv = cv2.merge([h, s, v])
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # 2. Optional: Boost contrast slightly (alpha = contrast [1.0-3.0], beta = brightness [-127-127])
        # frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)

        h, w, _ = frame.shape
        aspect_ratio = w / h
        new_height = int(self.ascii_width / aspect_ratio * 0.55)

        # resize frame
        resized = cv2.resize(frame, (self.ascii_width, new_height))
        char_w, char_h = 6, 10
        img_width = self.ascii_width * char_w
        img_height = new_height * char_h

        img = Image.new("RGB", (img_width, img_height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        # convert each pixel to the ascii stuff
        for y in range(new_height):
            for x in range(self.ascii_width):
                b, g, r = resized[y, x]
                lum = int(0.2126*r + 0.7152*g + 0.0722*b)
                char_index = int(lum / 255 * (len(ASCII_CHARS)-1))
                char = ASCII_CHARS[char_index]
                draw.text((x*char_w, y*char_h), char, fill=(r, g, b), font=self.font)

        return img

    def capture_loop(self):
        """Thread: continuously capture frames and convert to ASCII image."""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            img = self.frame_to_ascii_image(frame)
            if not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()  # discard old frame
                except queue.Empty:
                    pass
            self.frame_queue.put(img)
            time.sleep(0.01)  # tiny sleep to prevent CPU hog

    def update_frame(self):
        """Tkinter GUI update loop: display latest frame."""
        if not self.frame_queue.empty():
            img = self.frame_queue.get()
            self.photo = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
            self.canvas.config(width=img.width, height=img.height)
            self.master.geometry(f"{img.width}x{img.height}")

        if self.running:
            self.master.after(15, self.update_frame)  # ~60 FPS GUI refresh

    def on_close(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.master.destroy()


def main():
    root = tk.Tk()
    ASCIICamApp(root, cam_index=1, ascii_width=160)  # uses a virtual camera, if your using a normal camera change 1 to 0 i think??
    root.mainloop()


if __name__ == "__main__":
    main()