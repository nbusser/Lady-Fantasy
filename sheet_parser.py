import parsimonious
import tune

import repeat_mode as rm

grammar = parsimonious.grammar.Grammar(
    r"""
    entry = trash declarative? trash sheet trash
    declarative = "DECLARE:" trash declare_tune+ trash
    declare_tune = new_tune_name hs ":=" hs anonym_tune trash

    sheet = "BEGIN:" trash tune+

    tune = (anonym_tune / named_tune) trash

    named_tune = name trash
    anonym_tune = block / sound
    new_tune_name = name trash

    block = opening_block trash tune* trash "}" trash repeater?
    opening_block = "{"
    repeater = "*" trash (simple_repeat_counter / random_repeat)
    simple_repeat_counter = ~"\d+"

    random_repeat = "(" trash min_random_counter trash "-" trash max_random_counter trash base_repeat? ")"
    min_random_counter = ~"\d+"
    max_random_counter = ~"\d+"

    base_repeat = "base" trash base_repeat_counter
    base_repeat_counter = ~"\d+"

    sound = note / silence

    note = pitch hs duration hs sleep_time? trash
    pitch = pitch_label accidental? octave
    pitch_label = pitch_italian_label / pitch_german_label
    pitch_italian_label = "DO" / "RE" / "MI" / "FA" / "SOL" / "LA" / "SI"
    pitch_german_label = "A" / "B" / "C" / "D" / "E" / "F" / "G"
    accidental = "#" / "b"
    octave = ~"\d+"

    silence = "s"? hs sleep_time
    duration = ~"\d+"
    sleep_time = ~"\d*.\d+"

    comment = comment_sign ~".+"
    comment_sign = "//" / "𝅘𝅥𝅮"
    trash = ((comment / hs)* newline?)*

    name = ~"[A-Z 0-9 _ -]+"i
    ws = ~"\s*"
    hs = ~"[\t\ ]*"
    newline = ~"[\r\n]"
    """
)

class SheetVisitor(parsimonious.nodes.NodeVisitor):
    def __init__(self):
        self.allfather_block = tune.Pattern()
        self.blocks = [self.allfather_block]

        self.current_name = None
        self.new_tune_name = None

        self.current_tune = None

        self.declarations = {}

        self.current_pitch_label = None
        self.current_pitch_accidental = None
        self.current_pitch_octave = None
        self.current_pitch_freq = None

        self.current_pitch = None
        self.current_pitch_duration = None
        self.current_pitch_sleep_time = None

        self.min_random_counter = None
        self.max_random_counter = None
        self.base_repeat_counter = None

    def get_current_block(self):
        if self.blocks == []:
            return None
        return self.blocks[-1]

    def generic_visit(self, node, children):
        pass

    def visit_name(self, node, children):
        self.current_name = node.text.strip()

    def visit_opening_block(self, node, children):
        new_block = tune.Pattern()
        self.blocks.append(new_block)

    def visit_new_tune_name(self, node, children):
        self.new_tune_name = self.current_name
        self.current_name = None

    def visit_declare_tune(self, node, children):
        self.declarations[self.new_tune_name] = self.current_tune

        self.new_tune_name = None
        self.current_tune = None

    def visit_simple_repeat_counter(self, node, children):
        repeat_mode = rm.SimpleRepeatMode(int(node.text))
        self.get_current_block().set_repeat_mode(repeat_mode)

    def visit_min_random_counter(self, node, children):
        self.min_random_counter = int(node.text)

    def visit_max_random_counter(self, node, children):
        self.max_random_counter = int(node.text)

    def visit_base_repeat_counter(self, node, children):
        self.base_repeat_counter = int(node.text)

    def visit_random_repeat(self, node, children):
        if self.base_repeat_counter is None:
            self.base_repeat_counter = 1

        repeat_mode = rm.RandomRepeatMode(self.min_random_counter, self.max_random_counter, self.base_repeat_counter)
        self.get_current_block().set_repeat_mode(repeat_mode)

        self.min_random_counter = None
        self.max_random_counter = None
        self.base_repeat_counter = None

    def visit_block(self, node, children):
        closed_block = self.blocks.pop()
        self.current_tune = closed_block

    def visit_pitch_label(self, node, children):
        self.current_pitch_label = tune.PitchLabelDict[node.text]

    def visit_accidental(self, node, children):
        self.current_pitch_accidental = tune.PitchAccidental(node.text)

    def visit_octave(self, node, children):
        self.current_pitch_octave = int(node.text)

    def visit_pitch(self, node, children):
        if self.current_pitch_accidental is None:
            self.current_pitch_accidental = tune.PitchAccidental.NATURAL

        self.current_pitch = tune.Pitch(self.current_pitch_label, self.current_pitch_octave, self.current_pitch_accidental)

        self.current_pitch_label = None
        self.current_pitch_accidental = None
        self.current_pitch_octave = None

    def visit_duration(self, node, children):
        self.current_note_duration = int(node.text)

    def visit_sleep_time(self, node, children):
        self.current_pitch_sleep_time = float(node.text)

    def visit_named_tune(self, node, children):
        if self.current_name not in self.declarations:
            raise Exception("Tune {} never been declared".format(node.text))

        self.current_tune = self.declarations[self.current_name]

        self.current_name = None

    def visit_tune(self, node, children):
        current_block = self.get_current_block()
        current_block.add_tune(self.current_tune)

        self.current_tune = None

    def visit_note(self, node, children):
        local_pattern = tune.Pattern()

        note = tune.Note(self.current_pitch, self.current_note_duration)
        local_pattern.add_tune(note)

        if self.current_pitch_sleep_time is not None:
            silence = tune.Silence(self.current_pitch_sleep_time)
            local_pattern.add_tune(silence)

        self.current_tune = local_pattern

        self.current_pitch = None
        self.current_pitch_duration = None
        self.current_pitch_sleep_time = None

    def visit_silence(self, node, children):
        local_pattern = tune.Pattern()
        local_pattern.add_tune(tune.Silence(self.current_pitch_sleep_time))

        self.current_tune = local_pattern
        self.current_pitch_sleep_time = None

def parse_sheet(sheet):
    tree = grammar.parse(sheet)
    sv = SheetVisitor()
    sv.visit(tree)
    return sv.allfather_block
