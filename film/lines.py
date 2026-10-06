"""Every spoken line of the film.

speaker:
  narrator  - female TTS voice, flattened to a monotone (the "robotic" narrator)
  employee  - male TTS voice, processed as a low, distorted interview tape
  reveal    - the narrator's own voice with its natural pitch restored (slide 10)
  whisper   - the narrator's natural voice, whispered (end of tape)
"""

LINES = {
    # Intro
    "intro": ("narrator", "This material was produced for the instruction of personnel involved in the "
                          "identification, containment, and interaction with organisms classified as Pasión."),
    # Slide 01
    "s01a": ("narrator", "Pasión is the designation used for organisms of unknown origin, capable of "
                         "exhibiting imitative, adaptive, and affective behavior."),
    "s01b": ("narrator", "Although they present distinct physical characteristics, all observed variants "
                         "have demonstrated one recurring need."),
    "s01c": ("narrator", "Bond."),
    # Slide 02
    "s02a": ("narrator", "Archaeological evidence suggests that Pasión organisms may have existed on Earth "
                         "for approximately forty thousand years."),
    "s02b": ("narrator", "Similar depictions have been identified across different regions and historical periods."),
    "s02c": ("narrator", "The records share one common characteristic."),
    "s02d": ("narrator", "The creature is never alone."),
    # Slide 03
    "s03a": ("narrator", "Identification of possible Pasión individuals remains inconclusive."),
    "s03b": ("narrator", "Some individuals remained close to human communities for decades."),
    "s03c": ("narrator", "In certain cases, their presence was only identified after the disappearance, "
                         "or death, of associated individuals."),
    # Slide 04
    "s04a": ("narrator", "First specimen captured alive."),
    "s04b": ("narrator", "During initial testing, the specimen showed minimal resistance to containment."),
    "s04c": ("narrator", "However, after approximately three minutes of eye contact..."),
    "s04d": ("narrator", "its behavior changed."),
    # Slide 05
    "s05a": ("narrator", "Personnel must understand that the ability to imitate human emotions does not mean "
                         "the organism understands them."),
    "s05b": ("narrator", "Pasión does not love."),
    "s05c": ("narrator", "Pasión learns to love."),
    # Slide 06
    "s06a": ("narrator", "Authorized personnel must follow the procedures below."),
    "r01": ("narrator", "One. Do not remain alone with a specimen."),
    "r02": ("narrator", "Two. Do not establish physical contact without authorization."),
    "r03": ("narrator", "Three. Do not provide personal information."),
    "r04": ("narrator", "Four. Do not mention family members, partners, or emotionally significant persons."),
    "r05": ("narrator", "Five. Do not answer questions related to feelings."),
    "r06": ("narrator", "Six. Do not accept gifts offered by the specimen."),
    "r07": ("narrator", "Seven. Do not promise to return."),
    "s06b": ("narrator", "Under no circumstances."),
    # Slide 07
    "s07a": ("narrator", "In nineteen ninety-seven, an employee violated protocol zero four B."),
    "s07b": ("narrator", "The employee remained with the specimen for four hours."),
    "s07c": ("narrator", "During the subsequent interview, the employee stated..."),
    "s07d": ("employee", "She just wanted to be loved."),
    "s07e": ("narrator", "The employee was removed from the facility."),
    "s07f": ("narrator", "The specimen was removed from the facility."),
    # Slide 08
    "s08a": ("narrator", "The specimen was never located."),
    "s08b": ("narrator", "Neither was the employee."),
    # Slide 10
    "s10a": ("narrator", "If a Pasión individual assumes the appearance of someone you know..."),
    "s10b": ("narrator", "do not try to find out if it is really them."),
    "s10c": ("narrator", "Do not speak to it."),
    "s10d": ("narrator", "Do not touch it."),
    "s10e": ("narrator", "Do not show fear."),
    "s10f": ("narrator", "And, above all..."),
    "s10g": ("reveal", "don't tell her you still love her."),
    # Tail
    "tail": ("whisper", "Do you still love me?"),
}
