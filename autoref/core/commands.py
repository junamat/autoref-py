"""Command dataclass and built-in COMMANDS registry."""
from dataclasses import dataclass, field as _field


@dataclass
class Command:
    name: str                              # primary name without prefix, e.g. "undo"
    aliases: list[str] = _field(default_factory=list)
    desc: str = ""
    usage: str = ""                        # argument hint, e.g. "<map>" or "[secs]"
    section: str = "misc"                  # UI grouping
    scope: str = "ref"                     # "ref" | "anyone"
    noprefix: bool = False                 # True for !panic-style commands
    bracket_only: bool = False             # hidden in qualifiers view

    def to_dict(self) -> dict:
        prefix = "" if self.noprefix else ">"
        label = f"{prefix}{self.name}"
        if self.aliases:
            label += f" / {prefix}{self.aliases[0]}"
        if self.usage:
            label += f" {self.usage}"
        return {
            "name": self.name, "aliases": self.aliases,
            "label": label, "desc": self.desc,
            "section": self.section, "scope": self.scope,
            "noprefix": self.noprefix, "bracket_only": self.bracket_only,
        }


COMMANDS: list[Command] = [
    # flow
    Command("undo",          ["u"],      "undo last pick/ban/protect",              section="flow"),
    Command("abort",         ["ab"],     "abort map and replay it",                 section="flow"),
    Command("dismiss",       [],         "discard pending proposal",                section="flow"),
    Command("close",         [],         "end match + save",                        section="flow"),
    Command("close force",   [],         "end match, skip save",                    section="flow"),
    # mode
    Command("mode auto",     [],         "",                                        section="mode"),
    Command("mode assisted", [],         "",                                        section="mode"),
    Command("mode off",      [],         "",                                        section="mode"),
    Command("!panic",         [],         "instant OFF, anyone",   noprefix=True,    section="mode",    scope="anyone"),
    # timers & start
    Command("timeout",       [],         "break timer",           usage="[secs]",   section="timers",  scope="anyone"),
    Command("timer",         [],         "start a timer",         usage="<secs|pick|ban>", section="timers"),
    Command("startmap",      [],         "force-start map",       usage="[delay]",  section="timers"),
    # lobby
    Command("setmap",        ["sm"],     "change the map",        usage="<id>",     section="lobby"),
    Command("invite",        ["inv"],    "re-invite all players",                   section="lobby"),
    Command("refresh",       ["rf"],     "fetch !mp settings",                      section="lobby"),
    Command("next",          [],         "confirm step",          usage="<map>",    section="lobby"),
    # info
    Command("status",        ["st"],     "full match status",                       section="info",    scope="anyone"),
    Command("scoreline",     ["sc"],     "score only",                              section="info",    scope="anyone"),
    Command("picks",         ["pk"],     "pick history",                            section="info",    scope="anyone"),
    Command("bans",          ["bn"],     "ban history",                             section="info",    scope="anyone"),
    Command("protects",      ["prot"],   "protect history",                         section="info",    scope="anyone"),
    Command("phase",         [],         "bracket phase info",                      section="info",    scope="anyone"),
    # score override
    Command("setscoreline",  ["ssl"],    "set wins directly",     usage="<s0> <s1>",section="override"),
    # bracket only
    Command("roll",          [],         "set roll ranking",      usage="<t1> <t2>",section="bracket", bracket_only=True),
    Command("order",         [],         "choose scheme",         usage="<n>",      section="bracket", bracket_only=True),
    Command("fp",            [],         "first pick",            usage="<team>",   section="bracket", bracket_only=True),
    Command("fb",            [],         "first ban",             usage="<team>",   section="bracket", bracket_only=True),
    Command("fpro",          [],         "first protect",         usage="<team>",   section="bracket", bracket_only=True),
]
