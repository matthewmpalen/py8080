import logging
import struct
import io8080


class InvalidInstruction(Exception):
    pass


class StackException(Exception):
    pass


MAX_CYCLES = 0x411B

logger = logging.getLogger('cpu')


class CPU:
    VRAM_ADDRESS = 0x2400

    def __init__(self, path):
        self._pc = 0
        self._sp = 0xF000  # Stack Pointer

        # Registers
        self._a = 0  # Accumulator
        self._b = 0
        self._c = 0
        self._d = 0
        self._e = 0
        self._h = 0
        self._l = 0
        self._bc = 0
        self._de = 0
        self._hl = 0

        # Flags
        self._sign = False
        self._zero = False
        self._half_carry = False
        self._parity = False  # odd or even
        self._carry = False
        self._interrupt = False
        self._current_inst = 0  # current instruction

        self._interrupt_alternate = False
        self._count = 0
        self._cycles = 0
        self._instructions = [0] * 0x100
        self.io = io8080.IO()

        self._memory = []
        with open(path, 'rb') as f:
            while True:
                byte = f.read(1)
                if not byte:
                    break

                a, = struct.unpack('c', byte)
                self._memory.append(ord(a))

        # ROM + RAM (work RAM and video RAM) = 16384 0x3fff
        self._memory += [0] * (65536 - len(self._memory))

    @property
    def memory(self):
        return self._memory

    def reset(self):
        """
        Resets registers and flags

        :return:
        """
        self._pc = 0
        self._a = 0
        self.set_bc(0)
        self.set_hl(0)
        self._sign = False
        self._zero = False
        self._half_carry = False
        self._parity = False
        self._carry = False
        self._interrupt = False

    def run(self):
        """
        Starts CPU and runs a given number of cycles per frame in UI

        :return:
        """

        for i in range(MAX_CYCLES):
            self.step()

    def run_cycles(self, cycles):
        """
        Used for debugging

        :param cycles: int
        :return: program counter
        """
        for i in range(cycles):
            self.step()

        return self._pc

    def hack_kill_mobs(self):


        #self._memory[0x20F8] = 9
        #self._memory[0x20F9] = 9


        #self._memory[0x20F1] = 1

        diff = 0x2136 - 0x2100
        self._memory[0x2100:0x2136] = [0] * diff

    def hack_add_lives(self):
        self._memory[0x21FF] = 7

    def flag(self):
        """
        Used for debugging

        :return: byte representation
        """
        value = 0
        if self._carry:
            value += 0x01
        if self._parity:
            value += 0x04
        if self._zero:
            value += 0x40
        if self._sign:
            value += 0x80
        if self._interrupt:
            value += 0x20
        if self._half_carry:
            value += 0x10

        return value

    def step(self):
        """
        Executes an instruction and updates processor state

        :return:
        """

        self._current_inst = self.fetch_rom_next_byte()
        instruction = self._instructions[self._current_inst]
        if instruction is not None:
            instruction()
        else:
            logger.error("Opcode ERROR: " + str(self._current_inst))

        self._count += 1

        # Check interrupt
        if self._cycles >= MAX_CYCLES:
            self._cycles -= MAX_CYCLES
            if self._interrupt:
                if self._interrupt_alternate:
                    self._call_interrupt(0x08)
                else:
                    self._call_interrupt(0x10)
                self._interrupt_alternate = not self._interrupt_alternate

    def _call_interrupt(self, address):
        self._stack_push(self._pc)
        self._pc = address

    def _nop(self):
        """
        Do nothing

        :return:
        """

        self._cycles += 4

    def _unimplemented(self):
        """
        Instructions not yet implemented

        :return:
        """

        raise InvalidInstruction(
            'Instruction={} not implemented'.format(self._current_inst)
        )

    def _jmp(self):
        """
        Group of jump instructions

        :return:
        """

        condition = True
        data_16 = self.fetch_rom_next_2bytes()
        self._cycles += 10

        if self._current_inst == 0xC3:
            # JMP
            self._pc = data_16
            return
        elif self._current_inst == 0xC2:
            # JNZ
            condition = not self._zero
        elif self._current_inst == 0xCA:
            # JZ
            condition = self._zero
        elif self._current_inst == 0xD2:
            # JNC
            condition = not self._carry
        elif self._current_inst == 0xDA:
            # JC
            condition = self._carry
        elif self._current_inst == 0xF2:
            # JP
            condition = not self._sign
        elif self._current_inst == 0xFA:
            # JM
            condition = self._sign

        if condition:
            self._pc = data_16
            self._cycles += 5

    # ==============================
    # Load register pair immediate
    # ==============================

    def _lxi_bc(self):
        self.set_bc(self.fetch_rom_next_2bytes())
        self._cycles += 10

    def _lxi_de(self):
        self.set_de(self.fetch_rom_next_2bytes())
        self._cycles += 10

    def _lxi_hl(self):
        self.set_hl(self.fetch_rom_next_2bytes())
        self._cycles += 10

    def _lxi_sp(self):
        self._sp = self.fetch_rom_next_2bytes()
        self._cycles += 10

    # ===========================
    # Move register to register
    # ===========================

    def _mvi_a(self):
        self._a = self.fetch_rom_next_byte()
        self._cycles += 7

    def _mvi_b(self):
        self.set_b(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_c(self):
        self.set_c(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_d(self):
        self.set_d(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_e(self):
        self.set_e(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_h(self):
        self.set_h(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_l(self):
        self.set_l(self.fetch_rom_next_byte())
        self._cycles += 7

    def _mvi_m(self):
        self.write_byte(self._hl, self.fetch_rom_next_byte())
        self._cycles += 10

    def _call(self):
        """
        Unconditional subroutine call

        :return:
        """

        condition = True
        data_16 = self.fetch_rom_next_2bytes()
        self._cycles += 11

        if self._current_inst == 0xCD:
            # CALL adr	3		(SP-1)<-PC.hi;(SP-2)<-PC.lo;SP<-SP+2;PC=adr
            self._stack_push(self._pc)
            self._pc = data_16
            self._cycles += 6
            return
        elif self._current_inst == 0xC4:
            # if NZ, CALL adr
            condition = not self._zero
        elif self._current_inst == 0xCC:
            condition = self._zero
        elif self._current_inst == 0xD4:
            condition = not self._carry
        elif self._current_inst == 0xDC:
            condition = self._carry

        if condition:
            self._stack_push(self._pc)
            self._pc = data_16
            self._cycles += 7

    def _ret(self):
        """
        Unconditional return from subroutine

        :return:
        """

        condition = True
        self._cycles += 5

        if self._current_inst == 0xC9:
            self._pc = self._stack_pop()
            self._cycles += 5
            return
        elif self._current_inst == 0xC0:
            condition = not self._zero
        elif self._current_inst == 0xC8:
            condition = self._zero
        elif self._current_inst == 0xD0:
            condition = not self._carry
        elif self._current_inst == 0xD8:
            condition = self._carry

        if condition:
            self._pc = self._stack_pop()
            self._cycles += 6

    def _lda(self):
        """
        Load A from memory
        :return:
        """

        if self._current_inst == 0x0A:
            source = self._bc
        elif self._current_inst == 0x1A:
            source = self._de
        elif self._current_inst == 0x3A:
            source = self.fetch_rom_next_2bytes()
            self._cycles += 6
        else:
            raise InvalidInstruction('LDA: {}'.format(self._current_inst))

        self._a = self.read_byte(source)
        self._cycles += 7

    def _push(self):
        """
        Push value onto stack

        :return:

        """
        if self._current_inst == 0xC5:
            value = self._bc
        elif self._current_inst == 0xD5:
            value = self._de
        elif self._current_inst == 0xE5:
            value = self._hl
        elif self._current_inst == 0xF5:
            value = (self._a << 8) + 0x02
            value += 0x80 if self._sign else 0
            value += 0x40 if self._zero else 0
            value += 0x10 if self._half_carry else 0
            value += 0x04 if self._parity else 0
            value += 0x01 if self._carry else 0
        else:
            raise InvalidInstruction('Push: {}'.format(self._current_inst))

        self._stack_push(value)
        self._cycles += 11

    # ==============================
    # Pop register pair from stack
    # ==============================

    def _pop_bc(self):
        self.set_bc(self._stack_pop())
        self._cycles += 10

    def _pop_de(self):
        self.set_de(self._stack_pop())
        self._cycles += 10

    def _pop_hl(self):
        self.set_hl(self._stack_pop())
        self._cycles += 10

    def _pop_flags(self):
        value = self._stack_pop()
        self._a = value >> 8
        self._sign = True if (value & 0x80) > 0 else False
        self._zero = True if (value & 0x40) > 0 else False
        self._half_carry = True if (value & 0x10) > 0 else False
        self._parity = True if (value & 0x04) > 0 else False
        self._carry = True if (value & 0x01) > 0 else False
        self._cycles += 10

    def _mov_hl(self):
        """
        Move to HL

        :return:
        """

        if self._current_inst == 0x77:
            self.write_byte(self._hl, self._a)
        elif self._current_inst == 0x70:
            self.write_byte(self._hl, self._b)
        elif self._current_inst == 0x71:
            self.write_byte(self._hl, self._c)
        elif self._current_inst == 0x72:
            self.write_byte(self._hl, self._d)
        elif self._current_inst == 0x73:
            self.write_byte(self._hl, self._e)
        elif self._current_inst == 0x74:
            self.write_byte(self._hl, self._h)
        elif self._current_inst == 0x75:
            self.write_byte(self._hl, self._l)

        self._cycles += 7

    def _mov(self):
        """
        Move register to register

        :return:
        """

        if self._current_inst == 0x7F:
            self._a = self._a
        elif self._current_inst == 0x78:
            self._a = self._b
        elif self._current_inst == 0x79:
            self._a = self._c
        elif self._current_inst == 0x7A:
            self._a = self._d
        elif self._current_inst == 0x7B:
            self._a = self._e
        elif self._current_inst == 0x7C:
            self._a = self._h
        elif self._current_inst == 0x7D:
            self._a = self._l
        elif self._current_inst == 0x7E:
            self._a = self.read_byte(self._hl)
            self._cycles += 2

        elif self._current_inst == 0x47:
            self.set_b(self._a)
        elif self._current_inst == 0x40:
            self._b = self._b
        elif self._current_inst == 0x41:
            self.set_b(self._c)
        elif self._current_inst == 0x42:
            self.set_b(self._d)
        elif self._current_inst == 0x43:
            self.set_b(self._e)
        elif self._current_inst == 0x44:
            self.set_b(self._h)
        elif self._current_inst == 0x45:
            self.set_b(self._l)
        elif self._current_inst == 0x46:
            self.set_b(self.read_byte(self._hl))
            self._cycles += 2

        elif self._current_inst == 0x4F:
            self.set_c(self._a)
        elif self._current_inst == 0x48:
            self.set_c(self._b)
        elif self._current_inst == 0x49:
            self._c = self._c
        elif self._current_inst == 0x4A:
            self.set_c(self._d)
        elif self._current_inst == 0x4B:
            self.set_c(self._e)
        elif self._current_inst == 0x4C:
            self.set_c(self._h)
        elif self._current_inst == 0x4D:
            self.set_c(self._l)
        elif self._current_inst == 0x4E:
            self.set_c(self.read_byte(self._hl))
            self._cycles += 2

        elif self._current_inst == 0x57:
            self.set_d(self._a)
        elif self._current_inst == 0x50:
            self.set_d(self._b)
        elif self._current_inst == 0x51:
            self.set_d(self._c)
        elif self._current_inst == 0x52:
            self._d = self._d
        elif self._current_inst == 0x53:
            self.set_d(self._e)
        elif self._current_inst == 0x54:
            self.set_d(self._h)
        elif self._current_inst == 0x55:
            self.set_d(self._l)
        elif self._current_inst == 0x56:
            self.set_d(self.read_byte(self._hl))
            self._cycles += 2

        elif self._current_inst == 0x5F:
            self.set_e(self._a)
        elif self._current_inst == 0x58:
            self.set_e(self._b)
        elif self._current_inst == 0x59:
            self.set_e(self._c)
        elif self._current_inst == 0x5A:
            self.set_e(self._d)
        elif self._current_inst == 0x5B:
            self._e = self._e
        elif self._current_inst == 0x5C:
            self.set_e(self._h)
        elif self._current_inst == 0x5D:
            self.set_e(self._l)
        elif self._current_inst == 0x5E:
            self.set_e(self.read_byte(self._hl))
            self._cycles += 2

        elif self._current_inst == 0x67:
            self.set_h(self._a)
        elif self._current_inst == 0x60:
            self.set_h(self._b)
        elif self._current_inst == 0x61:
            self.set_h(self._c)
        elif self._current_inst == 0x62:
            self.set_h(self._d)
        elif self._current_inst == 0x63:
            self.set_h(self._e)
        elif self._current_inst == 0x64:
            self._h = self._h
        elif self._current_inst == 0x65:
            self.set_h(self._l)
        elif self._current_inst == 0x66:
            self.set_h(self.read_byte(self._hl))
            self._cycles += 2

        elif self._current_inst == 0x6F:
            self.set_l(self._a)
        elif self._current_inst == 0x68:
            self.set_l(self._b)
        elif self._current_inst == 0x69:
            self.set_l(self._c)
        elif self._current_inst == 0x6A:
            self.set_l(self._d)
        elif self._current_inst == 0x6B:
            self.set_l(self._e)
        elif self._current_inst == 0x6C:
            self.set_l(self._h)
        elif self._current_inst == 0x6D:
            self._l = self._l
        elif self._current_inst == 0x6E:
            self.set_l(self.read_byte(self._hl))
            self._cycles += 2
        else:
            raise InvalidInstruction('MOV: {}'.format(self._current_inst))

        self._cycles += 5

    def _inx(self):
        """
        Increment register pair

        :return:
        """

        if self._current_inst == 0x03:
            self.set_bc(self._bc + 1)
        elif self._current_inst == 0x13:
            self.set_de(self._de + 1)
        elif self._current_inst == 0x23:
            self.set_hl(self._hl + 1)
        elif self._current_inst == 0x33:
            self._sp = (self._sp + 1) & 0xFF

        self._cycles += 6

    # ======================================
    # Add register pair to HL (16-bit add)
    # ======================================

    def _dad_bc(self):
        self.add_hl(self._bc)
        self._cycles += 11

    def _dad_de(self):
        self.add_hl(self._de)
        self._cycles += 11

    def _dad_hl(self):
        self.add_hl(self._hl)
        self._cycles += 11

    def _dad_sp(self):
        self.add_hl(self._sp)
        self._cycles += 11

    def _dcx(self):
        """
        Decrement register pair

        :return:
        """

        if self._current_inst == 0x0B:
            self.set_bc(self._bc - 1)
        elif self._current_inst == 0x1B:
            self.set_de(self._de - 1)
        elif self._current_inst == 0x2B:
            self.set_hl(self._hl - 1)
        elif self._current_inst == 0x3B:
            self._sp = (self._sp - 1) & 0xFF
        else:
            raise InvalidInstruction('DCX: {}'.format(self._current_inst))

        self._cycles += 6

    def _dcr(self):
        """
        Decrement register

        :return:
        """

        if self._current_inst == 0x3D:
            self._a = self._decr(self._a)
        elif self._current_inst == 0x05:
            self.set_b(self._decr(self._b))
        elif self._current_inst == 0x0D:
            self.set_c(self._decr(self._c))
        elif self._current_inst == 0x15:
            self.set_d(self._decr(self._d))
        elif self._current_inst == 0x1D:
            self.set_e(self._decr(self._e))
        elif self._current_inst == 0x25:
            self.set_h(self._decr(self._h))
        elif self._current_inst == 0x2D:
            self.set_l(self._decr(self._l))
        elif self._current_inst == 0x35:
            self.write_byte(self._hl, self._decr(self.read_byte(self._hl)))
            self._cycles += 5
        else:
            raise InvalidInstruction('DEC: {}'.format(self._current_inst))

        self._cycles += 5

    def _inr(self):
        """
        Increment register

        :return:
        """

        if self._current_inst == 0x3C:
            self._a = self._incr(self._a)
        elif self._current_inst == 0x04:
            self.set_b(self._incr(self._b))
        elif self._current_inst == 0x0C:
            self.set_c(self._incr(self._c))
        elif self._current_inst == 0x14:
            self.set_d(self._incr(self._d))
        elif self._current_inst == 0x1C:
            self.set_e(self._incr(self._e))
        elif self._current_inst == 0x24:
            self.set_h(self._incr(self._h))
        elif self._current_inst == 0x2C:
            self.set_l(self._incr(self._l))
        elif self._current_inst == 0x34:
            self.write_byte(self._hl, self._incr(self.read_byte(self._hl)))
            self._cycles += 5

        self._cycles += 5

    def _ana(self):
        """
        AND register

        :return:
        """

        if self._current_inst == 0xA7:
            self._and(self._a)
        elif self._current_inst == 0xA0:
            self._and(self._b)
        elif self._current_inst == 0xA1:
            self._and(self._c)
        elif self._current_inst == 0xA2:
            self._and(self._d)
        elif self._current_inst == 0xA3:
            self._and(self._e)
        elif self._current_inst == 0xA4:
            self._and(self._h)
        elif self._current_inst == 0xA5:
            self._and(self._l)
        elif self._current_inst == 0xA6:
            self._and(self.read_byte(self._hl))
            self._cycles += 3

        self._cycles += 4

    def _ani(self):
        """
        AND immediate

        :return:
        """

        self._and(self.fetch_rom_next_byte())
        self._cycles += 7

    def _xra(self):
        """
        Exclusive OR with register

        :return:
        """
        if self._current_inst == 0xAF:
            self._xor(self._a)
        elif self._current_inst == 0xA8:
            self._xor(self._b)
        elif self._current_inst == 0xA9:
            self._xor(self._c)
        elif self._current_inst == 0xAA:
            self._xor(self._d)
        elif self._current_inst == 0xAB:
            self._xor(self._e)
        elif self._current_inst == 0xAC:
            self._xor(self._h)
        elif self._current_inst == 0xAD:
            self._xor(self._l)
        elif self._current_inst == 0xAE:
            self._xor(self.read_byte(self._hl))
            self._cycles += 3
        elif self._current_inst == 0xEE:
            self._xor(self.fetch_rom_next_byte())
            self._cycles += 3

        self._cycles += 4

    def _xri(self):
        """
        Exclusive OR immediate

        :return:
        """

        self._xor(self.fetch_rom_next_byte())
        self._cycles += 7

    def _ora(self):
        """
        OR register

        :return:
        """

        if self._current_inst == 0xB7:
            self._or(self._a)
        elif self._current_inst == 0xB0:
            self._or(self._b)
        elif self._current_inst == 0xB1:
            self._or(self._c)
        elif self._current_inst == 0xB2:
            self._or(self._d)
        elif self._current_inst == 0xB3:
            self._or(self._e)
        elif self._current_inst == 0xB4:
            self._or(self._h)
        elif self._current_inst == 0xB5:
            self._or(self._l)
        elif self._current_inst == 0xB6:
            self._or(self.read_byte(self._hl))
            self._cycles += 3

        self._cycles += 4

    def _ori(self):
        """
        OR immediate

        :return:
        """

        self._or(self.fetch_rom_next_byte())
        self._cycles += 7

    def _add(self):
        """
        Add register

        :return:
        """

        if self._current_inst == 0x87:
            self.__add(self._a)
        elif self._current_inst == 0x80:
            self.__add(self._b)
        elif self._current_inst == 0x81:
            self.__add(self._c)
        elif self._current_inst == 0x82:
            self.__add(self._d)
        elif self._current_inst == 0x83:
            self.__add(self._e)
        elif self._current_inst == 0x84:
            self.__add(self._h)
        elif self._current_inst == 0x85:
            self.__add(self._l)
        elif self._current_inst == 0x86:
            self.__add(self.read_byte(self._hl))
            self._cycles += 3
        elif self._current_inst == 0xC6:
            self.__add(self.fetch_rom_next_byte())
            self._cycles += 3

        self._cycles += 4

    def _adc(self):
        """
        Add register to A with carry

        :return:
        """

        carry = 1 if self._carry else 0
        if self._current_inst == 0x8F:
            self.__add(self._a, carry)
        elif self._current_inst == 0x88:
            self.__add(self._b, carry)
        elif self._current_inst == 0x89:
            self.__add(self._c, carry)
        elif self._current_inst == 0x8A:
            self.__add(self._d, carry)
        elif self._current_inst == 0x8B:
            self.__add(self._e, carry)
        elif self._current_inst == 0x8C:
            self.__add(self._h, carry)
        elif self._current_inst == 0x8D:
            self.__add(self._l, carry)
        elif self._current_inst == 0x8E:
            self.__add(self.read_byte(self._hl), carry)
            self._cycles += 3
        elif self._current_inst == 0xCE:
            self.__add(self.fetch_rom_next_byte(), carry)
            self._cycles += 3

        self._cycles += 4

    def _sub(self):
        """
        Subtract register from A

        :return:
        """

        if self._current_inst == 0x97:
            self.__sub(self._a)
        elif self._current_inst == 0x90:
            self.__sub(self._b)
        elif self._current_inst == 0x91:
            self.__sub(self._c)
        elif self._current_inst == 0x92:
            self.__sub(self._d)
        elif self._current_inst == 0x93:
            self.__sub(self._e)
        elif self._current_inst == 0x94:
            self.__sub(self._h)
        elif self._current_inst == 0x95:
            self.__sub(self._l)
        elif self._current_inst == 0x96:
            self.__sub(self.read_byte(self._hl))
            self._cycles += 3
        elif self._current_inst == 0xD6:
            self.__sub(self.fetch_rom_next_byte())
            self._cycles += 3

        self._cycles += 4

    def _sbbi(self):
        """
        Subtract immediate with borrow

        :return:
        """

        data = self.fetch_rom_next_byte()
        carry = 1 if self._carry else 0
        self.__sub(data, carry=carry)
        self._cycles += 7

    def _cmp(self):
        """
        Compare register

        :return:
        """

        if self._current_inst == 0xBF:
            value = self._a
        elif self._current_inst == 0xB8:
            value = self._b
        elif self._current_inst == 0xB9:
            value = self._c
        elif self._current_inst == 0xBA:
            value = self._d
        elif self._current_inst == 0xBB:
            value = self._e
        elif self._current_inst == 0xBC:
            value = self._h
        elif self._current_inst == 0xBD:
            value = self._l
        elif self._current_inst == 0xBE:
            value = self.read_byte(self._hl)
            self._cycles += 3
        elif self._current_inst == 0xFE:
            value = self.fetch_rom_next_byte()
            self._cycles += 3
        else:
            raise InvalidInstruction('CMP: {}'.format(self._current_inst))

        self._cmp_sub(value)

        self._cycles += 4

    def _xchg(self):
        """
        Exchange DE with HL

        :return:
        """

        temp = self._hl
        self.set_hl(self._de)
        self.set_de(temp)
        self._cycles += 4

    def _xthl(self):
        """
        Swap HL with top word on stack

        :return:
        """

        temp = self._h
        self.set_h(self.read_byte(self._sp + 1))
        self.write_byte(self._sp + 1, temp)

        temp = self._l
        self.set_l(self.read_byte(self._sp))
        self.write_byte(self._sp, temp)

        self._cycles += 4

    def _outp(self):
        """
        Write A to output port

        :return:
        """

        port = self.fetch_rom_next_byte()
        self.io.output(port, self._a)
        self._cycles += 10

    def _inp(self):
        """
        Read input port into A

        :return:
        """

        port = self.fetch_rom_next_byte()
        self._a = self.io.input(port)
        if self._a > 255:
            raise InvalidInstruction('INP: {}'.format(self._current_inst))

        self._cycles += 10

    def _pchl(self):
        """
        Jump to address in HL

        :return:
        """

        self._pc = self._hl
        self._cycles += 4

    def _rst(self):
        """
        Restart

        :return:
        """

        address = 0
        if self._current_inst == 0xC7:
            address = 0x00
        elif self._current_inst == 0xCF:
            address = 0x08
        elif self._current_inst == 0xD7:
            address = 0x10
        elif self._current_inst == 0xDF:
            address = 0x18
        elif self._current_inst == 0xE7:
            address = 0x20
        elif self._current_inst == 0xEF:
            address = 0x28
        elif self._current_inst == 0xF7:
            address = 0x30
        elif self._current_inst == 0xFF:
            address = 0x38

        self._stack_push(self._pc)
        self._pc = address

        self._cycles += 11

    def _rlc(self):
        """
        Rotate A left

        :return:
        """

        self._carry = True if (self._a >> 7) == 1 else False
        self._a = ((self._a << 1) & 0xFF) + (self._a >> 7)
        self._cycles += 4

    def _ral(self):
        """
        Rotate A left through carry

        :return:
        """

        temp = self._a
        self._a = (self._a << 1) & 0xFF
        self._a += 1 if self._carry else 0
        self._carry = True if (temp & 0x80) > 0 else False
        self._cycles += 4

    def _rrc(self):
        """
        Rotate A right

        :return:
        """

        self._carry = True if (self._a & 0x01) == 1 else False
        self._a = ((self._a >> 1) & 0xFF) + ((self._a << 7) & 0xFF)
        self._cycles += 4

    def _rar(self):
        """
        Rotate A right through carry
        :return:
        """

        temp = self._a
        self._a = (self._a >> 1)
        self._a += 0x80 if self._carry else 0
        self._carry = True if (temp & 0x01) > 0 else False
        self._cycles += 4

    def _sta(self):
        """
        Stora A to memory
        :return:
        """

        if self._current_inst == 0x02:
            self.write_byte(self._bc, self._a)
        elif self._current_inst == 0x12:
            self.write_byte(self._de, self._a)
        elif self._current_inst == 0x32:
            self.write_byte(self.fetch_rom_next_2bytes(), self._a)
            self._cycles += 6
        else:
            raise InvalidInstruction('STA: {}'.format(self._current_inst))

        self._cycles += 7

    def _di(self):
        """
        Disable interrupts

        :return:
        """

        self._interrupt = False
        self._cycles += 4

    def _ei(self):
        """
        Enable interrupts
        
        :return:
        """

        self._interrupt = True
        self._cycles += 4

    def _stc(self):
        """
        Set carry flag

        :return:
        """

        self._carry = True
        self._cycles += 4

    def _cmc(self):
        """
        Complement carry flag
        :return:
        """

        self._carry = not self._carry
        self._cycles += 4

    def _lhld(self):
        """
        Load HL from memory

        :return:
        """

        self.set_hl(self.read_2bytes(self.fetch_rom_next_2bytes()))
        self._cycles += 16

    def _shld(self):
        """
        Store HL to memory

        :return: 
        """

        self.write_2bytes(self.fetch_rom_next_2bytes(), self._hl)
        self._cycles += 16

    def _daa(self):
        """
        Decimal adjust accumulator

        :return:
        """

        if (self._a & 0x0F) > 9 or self._half_carry:
            self._a += 0x06
            self._half_carry = True

        if (self._a > 0x9F) or self._carry:
            self._a += 0x60
            self._carry = True

        self._zero = True if self._a == 0 else False
        self._sign = True if (self._a & 0x80) > 0 else False
        self._parity = True if self._a % 2 == 0 else False
        self._cycles += 4

    def _cma(self):
        """
        Complement A

        :return:
        """

        self._a = (~self._a) & 0xFF
        self._cycles += 4

    @staticmethod
    def _hlt():
        logger.info('HLT')
        exit(0)

    def set_b(self, data):
        self._b = data & 0xFF
        self._bc = (self._b << 8) + self._c

    def set_c(self, data):
        self._c = data & 0xFF
        self._bc = (self._b << 8) + self._c

    def set_d(self, data):
        self._d = data & 0xFF
        self._de = (self._d << 8) + self._e

    def set_e(self, data):
        self._e = data & 0xFF
        self._de = (self._d << 8) + self._e

    def set_h(self, data):
        self._h = data & 0xFF
        self._hl = (self._h << 8) + self._l

    def set_l(self, data):
        self._l = data & 0xFF
        self._hl = (self._h << 8) + self._l

    def set_bc(self, data):
        self._bc = data & 0xFFFF
        self._b = self._bc >> 8
        self._c = self._bc & 0xFF

    def set_de(self, data):
        self._de = data & 0xFFFF
        self._d = self._de >> 8
        self._e = self._de & 0xFF

    def set_hl(self, data):
        self._hl = data & 0xFFFF
        self._h = self._hl >> 8
        self._l = self._hl & 0xFF

    def add_hl(self, data):
        value = self._hl + data
        self.set_hl(value)
        if value > 0xFFFF:
            self._carry = True

    def _incr(self, data):
        # i++

        value = (data + 1) & 0xFF
        self._zero = True if value == 0 else False
        self._sign = True if (value & 0x80) > 0 else False
        self._half_carry = True if data == 0x0F else False
        self._parity = True if value % 2 == 0 else False
        return value

    def _decr(self, data):
        # i--

        value = (data - 1) & 0xFF
        self._half_carry = True if (data & 0x0F) == 0 else False
        self._sign = True if (value & 0x80) > 0 else False
        self._zero = True if value == 0 else False
        self._parity = True if value % 2 == 0 else False
        return value

    def _and(self, value):
        if value > 0x0FF:
            raise ValueError('{} is not a valid value for _and'.format(value))

        self._a = (self._a & value) & 0xFF
        self._carry = False
        self._zero = True if self._a == 0 else False
        self._sign = True if self._a & 0x80 > 0 else False
        self._parity = True if self._a % 2 == 0 else False

    def _xor(self, value):
        self._a = self._a ^ value
        self._carry = False
        self._zero = True if self._a == 0 else False
        self._sign = True if self._a & 0x80 > 0 else False
        self._parity = True if self._a % 2 == 0 else False

    def _or(self, value):
        self._a = self._a | value
        self._carry = False
        self._zero = True if self._a == 0 else False
        self._sign = True if self._a & 0x80 > 0 else False
        self._parity = True if self._a % 2 == 0 else False

    def __add(self, in_value, carry=0):
        value = self._a + in_value + carry

        if (((self._a ^ value) ^ in_value) & 0x10) > 0:
            self._half_carry = True
        else:
            self._half_carry = False

        self._a = value & 0xFF
        self._carry = True if value > 255 or value < 0 else False
        self._sign = True if self._a & 0x80 > 0 else False
        self._zero = True if self._a == 0 else False
        self._parity = True if self._a % 2 == 0 else False

    def __sub(self, in_value, carry=0):
        value = self._a - in_value + carry
        x = value & 0xFF

        if ((self._a ^ value) ^ in_value) & 0x10 > 0:
            self._half_carry = True
        else:
            self._half_carry = False

        self._carry = True if value > 255 or value < 0 else  False
        self._a = value & 0xFF
        self._sign = True if x & 0x80 > 0 else False
        self._zero = True if x == 0 else False
        self._parity = True if x % 2 == 0 else False

    def _cmp_sub(self, in_value):
        value = self._a - in_value
        self._carry = True if value >= 255 or value < 0 else False
        if ((self._a ^ value) ^ in_value) & 0x10 > 0:
            self._half_carry = True
        else:
            self._half_carry = False

        self._zero = True if value & 0xFF == 0 else False
        self._sign = True if (value & 0x80) > 0 else False
        self._parity = True if value % 2 == 0 else False

    def _stack_push(self, data):
        if data > 0xFFFF:
            raise StackException(
                'Push error: data={}, count={}'.format(data, self._count))

        self._sp -= 2
        self.write_2bytes(self._sp, data)

    def _stack_pop(self):
        address = self.read_2bytes(self._sp)
        self._sp += 2
        return address

    def read_byte(self, address):
        byte_ = self._memory[address]
        if byte_ > 0xFF:
            raise ValueError(
                '{} is not a valid byte at {}'.format(byte_, address))

        return byte_

    def read_2bytes(self, address):
        return (self._memory[address + 1] << 8) + self._memory[address]

    def write_byte(self, address, data):
        self._memory[address] = data & 0xFF

    def write_2bytes(self, address, data):
        self._memory[address + 1] = data >> 8
        self._memory[address] = data & 0xFF

    def fetch_rom_next_byte(self):
        # Read next 8 bits
        data = self._memory[self._pc]
        self._pc += 1
        return data

    def fetch_rom_next_2bytes(self):
        # Read next 16 bits (notice endian)
        data = (self._memory[self._pc + 1] << 8) + self._memory[self._pc]
        self._pc += 2
        return data

    def init_instruction_table(self):
        self._instructions[0x00] = self._nop
        self._instructions[0x01] = self._lxi_bc
        self._instructions[0x02] = self._sta
        self._instructions[0x03] = self._inx
        self._instructions[0x04] = self._inr
        self._instructions[0x05] = self._dcr
        self._instructions[0x06] = self._mvi_b
        self._instructions[0x07] = self._rlc
        self._instructions[0x08] = self._unimplemented
        self._instructions[0x09] = self._dad_bc
        self._instructions[0x0A] = self._lda
        self._instructions[0x0B] = self._dcx
        self._instructions[0x0C] = self._inr
        self._instructions[0x0D] = self._dcr
        self._instructions[0x0E] = self._mvi_c
        self._instructions[0x0F] = self._rrc

        self._instructions[0x10] = self._unimplemented
        self._instructions[0x11] = self._lxi_de
        self._instructions[0x12] = self._sta
        self._instructions[0x13] = self._inx
        self._instructions[0x14] = self._inr
        self._instructions[0x15] = self._dcr
        self._instructions[0x16] = self._mvi_d
        self._instructions[0x17] = self._ral
        self._instructions[0x18] = self._unimplemented
        self._instructions[0x19] = self._dad_de
        self._instructions[0x1A] = self._lda
        self._instructions[0x1B] = self._dcx
        self._instructions[0x1C] = self._inr
        self._instructions[0x1D] = self._dcr
        self._instructions[0x1E] = self._mvi_e
        self._instructions[0x1F] = self._rar

        self._instructions[0x20] = self._unimplemented
        self._instructions[0x21] = self._lxi_hl
        self._instructions[0x22] = self._shld
        self._instructions[0x23] = self._inx
        self._instructions[0x24] = self._inr
        self._instructions[0x25] = self._dcr
        self._instructions[0x26] = self._mvi_h
        self._instructions[0x27] = self._daa
        self._instructions[0x28] = self._unimplemented
        self._instructions[0x29] = self._dad_hl
        self._instructions[0x2A] = self._lhld
        self._instructions[0x2B] = self._dcx
        self._instructions[0x2C] = self._inr
        self._instructions[0x2D] = self._dcr
        self._instructions[0x2E] = self._mvi_l
        self._instructions[0x2F] = self._cma

        self._instructions[0x30] = self._unimplemented
        self._instructions[0x31] = self._lxi_sp
        self._instructions[0x32] = self._sta
        self._instructions[0x33] = self._inx
        self._instructions[0x34] = self._inr
        self._instructions[0x35] = self._dcr
        self._instructions[0x36] = self._mvi_m
        self._instructions[0x37] = self._stc
        self._instructions[0x38] = self._unimplemented
        self._instructions[0x39] = self._dad_sp
        self._instructions[0x3A] = self._lda
        self._instructions[0x3B] = self._dcx
        self._instructions[0x3C] = self._inr
        self._instructions[0x3D] = self._dcr
        self._instructions[0x3E] = self._mvi_a
        self._instructions[0x3F] = self._cmc

        self._instructions[0x40] = self._mov
        self._instructions[0x41] = self._mov
        self._instructions[0x42] = self._mov
        self._instructions[0x43] = self._mov
        self._instructions[0x44] = self._mov
        self._instructions[0x45] = self._mov
        self._instructions[0x46] = self._mov
        self._instructions[0x47] = self._mov
        self._instructions[0x48] = self._mov
        self._instructions[0x49] = self._mov
        self._instructions[0x4A] = self._mov
        self._instructions[0x4B] = self._mov
        self._instructions[0x4C] = self._mov
        self._instructions[0x4D] = self._mov
        self._instructions[0x4E] = self._mov
        self._instructions[0x4F] = self._mov

        self._instructions[0x50] = self._mov
        self._instructions[0x51] = self._mov
        self._instructions[0x52] = self._mov
        self._instructions[0x53] = self._mov
        self._instructions[0x54] = self._mov
        self._instructions[0x55] = self._mov
        self._instructions[0x56] = self._mov
        self._instructions[0x57] = self._mov
        self._instructions[0x58] = self._mov
        self._instructions[0x59] = self._mov
        self._instructions[0x5A] = self._mov
        self._instructions[0x5B] = self._mov
        self._instructions[0x5C] = self._mov
        self._instructions[0x5D] = self._mov
        self._instructions[0x5E] = self._mov
        self._instructions[0x5F] = self._mov

        self._instructions[0x60] = self._mov
        self._instructions[0x61] = self._mov
        self._instructions[0x62] = self._mov
        self._instructions[0x63] = self._mov
        self._instructions[0x64] = self._mov
        self._instructions[0x65] = self._mov
        self._instructions[0x66] = self._mov
        self._instructions[0x67] = self._mov
        self._instructions[0x68] = self._mov
        self._instructions[0x69] = self._mov
        self._instructions[0x6A] = self._mov
        self._instructions[0x6B] = self._mov
        self._instructions[0x6C] = self._mov
        self._instructions[0x6D] = self._mov
        self._instructions[0x6E] = self._mov
        self._instructions[0x6F] = self._mov

        self._instructions[0x70] = self._mov_hl
        self._instructions[0x71] = self._mov_hl
        self._instructions[0x72] = self._mov_hl
        self._instructions[0x73] = self._mov_hl
        self._instructions[0x74] = self._mov_hl
        self._instructions[0x75] = self._mov_hl
        self._instructions[0x76] = self._hlt
        self._instructions[0x77] = self._mov_hl
        self._instructions[0x78] = self._mov
        self._instructions[0x79] = self._mov
        self._instructions[0x7A] = self._mov
        self._instructions[0x7B] = self._mov
        self._instructions[0x7C] = self._mov
        self._instructions[0x7D] = self._mov
        self._instructions[0x7E] = self._mov
        self._instructions[0x7F] = self._mov

        self._instructions[0x80] = self._add
        self._instructions[0x81] = self._add
        self._instructions[0x82] = self._add
        self._instructions[0x83] = self._add
        self._instructions[0x84] = self._add
        self._instructions[0x85] = self._add
        self._instructions[0x86] = self._add
        self._instructions[0x87] = self._add
        self._instructions[0x88] = self._adc
        self._instructions[0x89] = self._adc
        self._instructions[0x8A] = self._adc
        self._instructions[0x8B] = self._adc
        self._instructions[0x8C] = self._adc
        self._instructions[0x8D] = self._adc
        self._instructions[0x8E] = self._adc
        self._instructions[0x8F] = self._adc

        self._instructions[0x90] = self._sub
        self._instructions[0x91] = self._sub
        self._instructions[0x92] = self._sub
        self._instructions[0x93] = self._sub
        self._instructions[0x94] = self._sub
        self._instructions[0x95] = self._sub
        self._instructions[0x96] = self._sub
        self._instructions[0x97] = self._sub
        self._instructions[0x98] = self._unimplemented
        self._instructions[0x99] = self._unimplemented
        self._instructions[0x9A] = self._unimplemented
        self._instructions[0x9B] = self._unimplemented
        self._instructions[0x9C] = self._unimplemented
        self._instructions[0x9D] = self._unimplemented
        self._instructions[0x9E] = self._unimplemented
        self._instructions[0x9F] = self._unimplemented

        self._instructions[0xA0] = self._ana
        self._instructions[0xA1] = self._ana
        self._instructions[0xA2] = self._ana
        self._instructions[0xA3] = self._ana
        self._instructions[0xA4] = self._ana
        self._instructions[0xA5] = self._ana
        self._instructions[0xA6] = self._ana
        self._instructions[0xA7] = self._ana
        self._instructions[0xA8] = self._xra
        self._instructions[0xA9] = self._xra
        self._instructions[0xAA] = self._xra
        self._instructions[0xAB] = self._xra
        self._instructions[0xAC] = self._xra
        self._instructions[0xAD] = self._xra
        self._instructions[0xAE] = self._xra
        self._instructions[0xAF] = self._xra

        self._instructions[0xB0] = self._ora
        self._instructions[0xB1] = self._ora
        self._instructions[0xB2] = self._ora
        self._instructions[0xB3] = self._ora
        self._instructions[0xB4] = self._ora
        self._instructions[0xB5] = self._ora
        self._instructions[0xB6] = self._ora
        self._instructions[0xB7] = self._ora
        self._instructions[0xB8] = self._cmp
        self._instructions[0xB9] = self._cmp
        self._instructions[0xBA] = self._cmp
        self._instructions[0xBB] = self._cmp
        self._instructions[0xBC] = self._cmp
        self._instructions[0xBD] = self._cmp
        self._instructions[0xBE] = self._cmp
        self._instructions[0xBF] = self._cmp

        self._instructions[0xC0] = self._ret
        self._instructions[0xC1] = self._pop_bc
        self._instructions[0xC2] = self._jmp
        self._instructions[0xC3] = self._jmp
        self._instructions[0xC4] = self._call
        self._instructions[0xC5] = self._push
        self._instructions[0xC6] = self._add
        self._instructions[0xC7] = self._rst
        self._instructions[0xC8] = self._ret
        self._instructions[0xC9] = self._ret
        self._instructions[0xCA] = self._jmp
        self._instructions[0xCB] = self._unimplemented
        self._instructions[0xCC] = self._call
        self._instructions[0xCD] = self._call
        self._instructions[0xCE] = self._adc
        self._instructions[0xCF] = self._rst

        self._instructions[0xD0] = self._ret
        self._instructions[0xD1] = self._pop_de
        self._instructions[0xD2] = self._jmp
        self._instructions[0xD3] = self._outp
        self._instructions[0xD4] = self._call
        self._instructions[0xD5] = self._push
        self._instructions[0xD6] = self._sub
        self._instructions[0xD7] = self._rst
        self._instructions[0xD8] = self._ret
        self._instructions[0xD9] = self._unimplemented
        self._instructions[0xDA] = self._jmp
        self._instructions[0xDB] = self._inp
        self._instructions[0xDC] = self._call
        self._instructions[0xDD] = self._unimplemented
        self._instructions[0xDE] = self._sbbi
        self._instructions[0xDF] = self._rst

        self._instructions[0xE0] = self._unimplemented
        self._instructions[0xE1] = self._pop_hl
        self._instructions[0xE2] = self._unimplemented
        self._instructions[0xE3] = self._xthl
        self._instructions[0xE4] = self._unimplemented
        self._instructions[0xE5] = self._push
        self._instructions[0xE6] = self._ani
        self._instructions[0xE7] = self._rst
        self._instructions[0xE8] = self._unimplemented
        self._instructions[0xE9] = self._pchl
        self._instructions[0xEA] = self._unimplemented
        self._instructions[0xEB] = self._xchg
        self._instructions[0xEC] = self._unimplemented
        self._instructions[0xED] = self._unimplemented
        self._instructions[0xEE] = self._xri
        self._instructions[0xEF] = self._rst

        self._instructions[0xF0] = self._unimplemented
        self._instructions[0xF1] = self._pop_flags
        self._instructions[0xF2] = self._jmp
        self._instructions[0xF3] = self._di
        self._instructions[0xF4] = self._unimplemented
        self._instructions[0xF5] = self._push
        self._instructions[0xF6] = self._ori
        self._instructions[0xF7] = self._rst
        self._instructions[0xF8] = self._unimplemented
        self._instructions[0xF9] = self._unimplemented
        self._instructions[0xFA] = self._jmp
        self._instructions[0xFB] = self._ei
        self._instructions[0xFC] = self._unimplemented
        self._instructions[0xFD] = self._nop
        self._instructions[0xFE] = self._cmp
        self._instructions[0xFF] = self._rst
