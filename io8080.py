class IOException(Exception):
    pass


class IO:
    """
    Input and output ports for 8080
    """

    def __init__(self):
        self.out_port2 = 0
        self.out_port3 = 0
        self.out_port4_low = 0
        self.out_port4_high = 0
        self.out_port5 = 0
        self.in_port1 = 0
        self.in_port2 = 0

    def output(self, port, value):
        if port == 2:
            self.out_port2 = value
        elif port == 3:
            self.out_port3 = value
        elif port == 4:
            self.out_port4_low = self.out_port4_high
            self.out_port4_high = value
        elif port == 5:
            self.out_port5 = value

    def input(self, port):
        if port == 1:
            result = self.in_port1
            self.in_port1 &= 0xFE
        elif port == 2:
            result = (self.in_port2 & 0x8F) | (self.in_port2 & 0x70)
        elif port == 3:
            result = ((((self.out_port4_high << 8) | self.out_port4_low) << self.out_port2) >> 8) & 0xFF

        if result > 255:
            raise IOException('Invalid result={}'.format(result))

        return result
