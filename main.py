from argparse import ArgumentParser

from emulator import Emulator


def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--filename', help='ROM file')
    arg_parser.add_argument('--state', help='Save state file')
    args = arg_parser.parse_args()


    filename = args.filename if args.filename else 'invaders.rom'
    state = args.state

    if state:
        emu = Emulator.load(state)
    else:
        emu = Emulator(path=filename)

    emu.run()

if __name__ == '__main__':
    main()
