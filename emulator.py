import pygame

import cpu
import pickle
import time

MIN_WIDTH = 256
MIN_HEIGHT = 224


class Emulator:
    """
    Contains 8080 CPU and uses Pygame to display the VRAM

    Controls:
      1. Press 'c' key to insert coin
      2. Press '1' key to choose player 1
      3. Press arrow keys to move
      4. Press 'Space' to shoot

    """

    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    ASPECT_RATIO = MIN_WIDTH / MIN_HEIGHT
    CAPTION_FORMAT = 'Py8080: {}'

    def __init__(self, path=None, width=MIN_WIDTH):
        if path:
            self._cpu = cpu.CPU(path)
            self._cpu.init_instruction_table()
        else:
            self._cpu = None

        self._path = path
        self._width = max(MIN_WIDTH, width)
        self._height = round(self._width / self.ASPECT_RATIO)
        self._display_size = self._height, self._width
        self._px_array = None
        self._fps = 60

    def _refresh(self):
        """
        Update the pixel array

        :return:
        """

        j_range = int(self._width * 0.125)
        k_range = j_range // 4

        for i in range(self._height):
            index = self._cpu.VRAM_ADDRESS + (i << 5)

            for j in range(j_range):
                vram = self._cpu.memory[index]
                index += 1

                for k in range(k_range):
                    y = self._width - 1 - j*k_range - k

                    if (vram & 0x01) == 1:
                        self._px_array[i][y] = self.WHITE
                    else:
                        self._px_array[i][y] = self.BLACK

                    vram >>= 1

    def _handle(self, event):
        if event.type == pygame.QUIT:
            exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                self._cpu.io.in_port1 |= 0x01
            if event.key == pygame.K_1:
                self._cpu.io.in_port1 |= 0x04
            if event.key == pygame.K_SPACE:
                self._cpu.io.in_port1 |= 0x10
            if event.key == pygame.K_LEFT:
                self._cpu.io.in_port1 |= 0x20
            if event.key == pygame.K_RIGHT:
                self._cpu.io.in_port1 |= 0x40
            if event.key == pygame.K_6:
                # Save state
                self.save()

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_c:
                self._cpu.io.in_port1 &= 255 - 0x01
            if event.key == pygame.K_1:
                self._cpu.io.in_port1 &= 255 - 0x04
            if event.key == pygame.K_SPACE:
                self._cpu.io.in_port1 &= 255 - 0x10
            if event.key == pygame.K_LEFT:
                self._cpu.io.in_port1 &= 255 - 0x20
            if event.key == pygame.K_RIGHT:
                self._cpu.io.in_port1 &= 255 - 0x40

    def save(self):
        """
        Save CPU state to disk

        :return:
        """

        timestamp = round(time.time())
        state_path = 'saves/{}_{}.pickle'.format(self._path, timestamp)
        with open(state_path, 'wb') as state_file:
            pickle.dump(self._cpu, state_file)

    @classmethod
    def load(cls, state):
        """
        Load CPU state from disk

        :param state: Pickle file
        :return:
        """

        with open(state, 'rb') as state_file:
            cpu = pickle.load(state_file)

        emu = cls()
        emu._cpu = cpu
        return emu

    def run(self):
        """
        Sets up display and starts game loop

        :return:
        """

        pygame.init()
        surface = pygame.display.set_mode(self._display_size)
        caption = self.CAPTION_FORMAT.format(self._path if self._path else '')
        pygame.display.set_caption(caption)

        surface.fill(self.BLACK)
        self._px_array = pygame.PixelArray(surface)

        pygame.display.update()
        fps_clock = pygame.time.Clock()

        while True:
            for event in pygame.event.get():
                self._handle(event)

            self._cpu.run()
            self._refresh()
            fps_clock.tick(self._fps)
            pygame.display.update()
