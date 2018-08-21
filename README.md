# py8080

![Screenshot](https://i.imgur.com/vo2DaeX.png "Screenshot")

Intel 8080 emulator written in Python.

## Usage

```bash
python main.py --filename <filename>

# or load a save state

python main.py --state saves/<state file>
```

If no filename is provided, defaults to Space Invaders demo.

## Controls

1. Press `c` key to insert coin
2. Press `1` key to choose player 1
3. Press arrow keys to move
4. Press `Space` to shoot
5. Press `6` to save state

### Notes

1. Still contains unimplemented instructions
2. Rendered using [Pygame](https://www.pygame.org/wiki/GettingStarted)
