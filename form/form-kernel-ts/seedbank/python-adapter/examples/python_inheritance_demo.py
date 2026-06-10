# python_inheritance_demo.py — single inheritance + super() through the
# full Python → Form → native-kernel pipeline.
#
# Closes the inheritance gap named in kernels/PYTHON_PIPELINE_STATUS.md.
# The shape is the smallest healthy subclass relationship:
#   class Animal: with __init__(name) and speak()
#   class Dog(Animal): overrides speak() and chains __init__ via super()
#
# Runs identically under:
#   python3 python_inheritance_demo.py        — CPython
#   kernel-bmf-run <file.py>         — kernel-bmf-run
#   form-kernel-rust python_inheritance_demo.fk — native kernel binary
#
# Pending (each its own breath): multiple inheritance, MRO complexity,
# metaclasses, abstract base classes, __init_subclass__.

class Animal:
    def __init__(self, name, base_sound):
        self.name = name
        self.sound = base_sound

    def speak(self):
        return self.sound

    def signature(self):
        return self.sound + 10


class Dog(Animal):
    def __init__(self, name, energy):
        super().__init__(name, 100)
        self.energy = energy

    def speak(self):
        s = super().speak()
        return s + self.energy

    # signature() is inherited from Animal — dispatch walks __base__ chain.


# Inheritance: Dog instances carry Animal's name + sound, plus their own energy.
d = Dog("Rex", 7)

own_speak    = d.speak()         # super().speak() = 100, + energy 7 = 107
inherited    = d.signature()     # falls through to Animal.signature = 100+10 = 110
field_name   = d.name            # set by Animal.__init__ via super() = "Rex" (len=3)
field_energy = d.energy          # set by Dog.__init__ = 7

# Animal alone still works — sibling parity for the non-inherited path.
a = Animal("Cat", 50)
animal_speak = a.speak()                # 50
animal_sig   = a.signature()            # 60

# Final expression: 107 + 110 + 3 + 7 + 50 + 60 = 337
own_speak + inherited + len(field_name) + field_energy + animal_speak + animal_sig
