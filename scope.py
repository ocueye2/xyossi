import math
import struct
import sys
import wave
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import os
import time
import random

scopeframe = False

# Settings
x_ch = 1
y_ch = 0
x_inv = 1
y_inv = 1
samples_per_frame = 1000  # adjust for resolution/speed

# Globals
sample_rate = 48000
num_channels = 2
bits_per_sample = 16
max_sample_value = (2 ** 15) - 1
w = None
prev_x = 0
prev_y = 0

def open_wav(f):
    global w, sample_rate, bits_per_sample, max_sample_value, num_channels
    w = wave.open(f, 'rb')
    sample_rate = w.getframerate()
    num_channels = w.getnchannels()
    sample_width = w.getsampwidth()
    bits_per_sample = sample_width * 8

    if bits_per_sample == 8:
        max_sample_value = 127  # unsigned 8-bit
    elif bits_per_sample == 16:
        max_sample_value = (2 ** 15) - 1
    elif bits_per_sample == 24:
        max_sample_value = (2 ** 23) - 1
    elif bits_per_sample == 32:
        max_sample_value = (2 ** 31) - 1
    else:
        raise Exception(f'Unsupported bit depth: {bits_per_sample}')

def unpack_sample(data, bits):
    if bits == 8:
        return struct.unpack('<' + 'B' * len(data), data)  # unsigned
    elif bits == 16:
        return struct.unpack('<' + 'h' * (len(data) // 2), data)
    elif bits == 24:
        samples = []
        for i in range(0, len(data), 3):
            b = data[i:i+3]
            val = int.from_bytes(b + (b'\x00' if b[2] < 128 else b'\xFF'), byteorder='little', signed=True)
            samples.append(val)
        return samples
    elif bits == 32:
        return struct.unpack('<' + 'i' * (len(data) // 4), data)
    else:
        raise Exception('Unsupported bits per sample')

def read_data_samples(start_sample, num_samples):
    try:
        w.setpos(start_sample)
        return w.readframes(num_samples)
    except:
        return b''

def create_window():
    glutInit(sys.argv)
    width, height = 1024, 1024
    pygame.init()
    pygame.display.set_mode((width, height), OPENGL | DOUBLEBUF)
    glClear(GL_COLOR_BUFFER_BIT)
    glEnable(GL_BLEND)


def react_to_wav_parameters():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(-max_sample_value * x_inv, max_sample_value * x_inv,
               -max_sample_value * y_inv, max_sample_value * y_inv)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

def fade_image():
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.0, 0.0, 0.0, 0.99)
    glBegin(GL_QUADS)
    glVertex3f(-max_sample_value,  max_sample_value, 0.0)
    glVertex3f( max_sample_value,  max_sample_value, 0.0)
    glVertex3f( max_sample_value, -max_sample_value, 0.0)
    glVertex3f(-max_sample_value, -max_sample_value, 0.0)
    glEnd()

def draw_samples(data):
    global prev_x, prev_y,scopeartifacts, r, g, b, linewidth, scopeframe
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glLineWidth(linewidth)
    if scopeartifacts:
        if scopeframe:
            scopeframe = False
            glBegin(GL_POINTS)
        else:
            scopeframe = True
            glBegin(GL_LINES)
    else:
        glBegin(GL_LINES)

    bytes_per_sample = bits_per_sample // 8
    frame_size = bytes_per_sample * num_channels
    num_frames = len(data) // frame_size

    for i in range(num_frames):
        frame = data[i * frame_size:(i + 1) * frame_size]
        if len(frame) < frame_size:
            continue
        channels = unpack_sample(frame, bits_per_sample)
        if bits_per_sample == 8:
            x = channels[x_ch] - 128
            y = channels[y_ch] - 128
        else:
            x = channels[x_ch]
            y = channels[y_ch]

        line_len = math.sqrt(((x - prev_x) ** 2) + ((y - prev_y) ** 2))
        fraction_of_long_line = line_len / (4 * max_sample_value)
        color_factor = (1 - fraction_of_long_line) ** 100
        glColor4f(r * color_factor, g * color_factor , b * color_factor,1)
        glVertex3f(prev_y, prev_x, 0.0)
        glVertex3f(y, x, 0.0)
        prev_x = x
        prev_y = y

    glEnd()

def end_image():
    pygame.display.flip()

def main(wavfile):
    create_window()
    open_wav(wavfile)
    react_to_wav_parameters()
    clock = pygame.time.Clock()

    start_time = time.time()
    quit = False

    while True:
        for e in pygame.event.get():
            if e.type == QUIT or (e.type == KEYDOWN and e.key in (pygame.K_q, pygame.K_x)):
                quit = True
        if quit:
            break

        seconds_played = time.time() - start_time
        current_sample = int(seconds_played * sample_rate)

        fade_image()
        data = read_data_samples(current_sample, samples_per_frame)
        if not data:
            break
        draw_samples(data)
        end_image()

        clock.tick(120)  # Target 120 FPS



if __name__ == '__main__':
    from PIL import ImageColor
    import configparser
    config = configparser.ConfigParser()
    config.read('scope.conf')
    if config['Config']['scopeartifiacts'] == "True":
        scopeartifacts = True
    else:
        scopeartifacts = False

    if config['Config']['playaudio'] == "True":
        playaudo = True
    else:
        playaudo = False

    linewidth = int(config['Config']['linewidth'])
    

    r, g, b = [i/256 for i in ImageColor.getrgb(config['Config']['color'])]
    print(config['Config']['scopeartifiacts'])
    print(scopeartifacts)

    try:
        if config['Config']['wavfile'] == "":
            wavfile = input("wav file:")
        else:
            wavfile = config['Config']['wavfile']

        if playaudo:
            os.system(f'mpv --no-video "{wavfile}" & > /dev/null')
        main(wavfile)
    finally:
        os.system('killall mpv')
