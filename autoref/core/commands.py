"""Command dataclass, built-in COMMANDS registry, and built-in handler table.

A handler is `async def (ref: AutoRef, args: list[str], source: str) -> None`.
The base `AutoRef._dispatch_command` looks up the command keyword in
`BUILTIN_HANDLERS` and awaits the handler. Aliases share the same handler.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field as _field
from typing import Awaitable, Callable, TYPE_CHECKING

from .enums import RefMode

if TYPE_CHECKING:
    from .base import AutoRef


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


# ---------------------------------------------------------------- handlers
# Each handler operates on a live AutoRef instance. Returning is implicit None;
# the dispatcher returns True purely from the dict-lookup hit.

Handler = Callable[["AutoRef", list[str], str], Awaitable[None]]


async def _help(ref: "AutoRef", args: list[str], source: str) -> None:
    trusted = source in ref._trusted_sources()
    if trusted:
        for line in ref._help_ref_lines():
            await ref.lobby.reply(line, source)
    else:
        prefix = ref.ref_prefix
        for c in ref._commands():
            if c.scope == "anyone":
                p = "" if c.noprefix else prefix
                await ref.lobby.say(f"{p}{c.name}  — {c.desc}")


async def _mode(ref: "AutoRef", args: list[str], source: str) -> None:
    if not args:
        return
    try:
        await ref._set_mode(RefMode(args[0].lower()))
        await ref.lobby.say(f"Mode: {ref.mode.value}.")
    except ValueError:
        pass


async def _next(ref: "AutoRef", args: list[str], source: str) -> None:
    if ref._next_future is not None and not ref._next_future.done():
        ref._next_future.set_result(args)


async def _dismiss(ref: "AutoRef", args: list[str], source: str) -> None:
    ref._pending_proposal = None
    await ref._push_state()


async def _timeout(ref: "AutoRef", args: list[str], source: str) -> None:
    duration = 120
    if args:
        try:
            duration = int(args[0])
        except ValueError:
            pass
    asyncio.ensure_future(ref._do_timeout(duration))


async def _scoreline(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref.lobby.say(ref._format_scoreline())


async def _picks(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref.lobby.say(f"picks: {ref._format_step_history('PICK')}")


async def _bans(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref.lobby.say(f"bans: {ref._format_step_history('BAN')}")


async def _protects(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref.lobby.say(f"protects: {ref._format_step_history('PROTECT')}")


async def _status(ref: "AutoRef", args: list[str], source: str) -> None:
    bo = ref.match.ruleset.best_of
    await ref.lobby.say(
        f"[status] BO{bo} | {ref.mode.value} mode | {ref._format_scoreline()}"
    )
    bans = ref._format_step_history("BAN")
    pros = ref._format_step_history("PROTECT")
    pks  = ref._format_step_history("PICK")
    if pros != "none":
        await ref.lobby.say(f"protects: {pros} | bans: {bans}")
    else:
        await ref.lobby.say(f"bans: {bans}")
    await ref.lobby.say(f"picks: {pks}")


async def _setmap(ref: "AutoRef", args: list[str], source: str) -> None:
    if not args:
        return
    try:
        bid = int(args[0])
        gm  = int(args[1]) if len(args) > 1 else ref.match.ruleset.gamemode.value
        await ref.lobby.set_map(bid, gm)
    except (ValueError, IndexError):
        await ref.lobby.say(f"Usage: {ref.ref_prefix}setmap <beatmap_id> [gamemode]")


async def _timer(ref: "AutoRef", args: list[str], source: str) -> None:
    if not args:
        return
    _named = {
        "pick": ref.timers.pick,
        "ban": ref.timers.ban,
        "protect": ref.timers.protect, "pro": ref.timers.protect,
        "ready": ref.timers.ready_up,
        "force": ref.timers.force_start, "fs": ref.timers.force_start,
        "closing": ref.timers.closing,
    }
    raw = args[0].lower()
    seconds = _named.get(raw)
    if seconds is None:
        try:
            seconds = int(args[0])
        except ValueError:
            await ref.lobby.say(
                f"Usage: {ref.ref_prefix}timer <seconds|pick|ban|protect|ready|force|closing>"
            )
            return
    asyncio.ensure_future(ref.lobby.timer(seconds))


async def _startmap(ref: "AutoRef", args: list[str], source: str) -> None:
    delay = ref.timers.force_start
    if args:
        try:
            delay = int(args[0])
        except ValueError:
            pass
    asyncio.ensure_future(ref.lobby.start(delay=delay))


async def _abort(ref: "AutoRef", args: list[str], source: str) -> None:
    if ref._map_in_progress:
        await ref.lobby.abort()
        ref._abort_event.set()
    else:
        await ref.lobby.say("No map in progress.")


async def _undo(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref._undo_last_action()


async def _close(ref: "AutoRef", args: list[str], source: str) -> None:
    force = bool(args) and args[0].lower() == "force"
    if not force:
        ref._save_match()
    ref._close_event.set()
    # Unblock any active wait so the loop reaches the close check.
    ref._mode_event.set()
    ref._timeout_event.set()
    ref._abort_event.set()
    ref._cancel_step()


async def _invite(ref: "AutoRef", args: list[str], source: str) -> None:
    for team in ref.match.teams:
        for player in team.players:
            await ref.lobby.invite(player.username)
    await ref.lobby.say("Invites sent.")


async def _refresh(ref: "AutoRef", args: list[str], source: str) -> None:
    await ref.lobby.fetch_settings()
    await ref._push_state()


# Maps every accepted keyword (primary + alias) to its handler.
BUILTIN_HANDLERS: dict[str, Handler] = {
    # help
    "help": _help, "commands": _help, "cmds": _help, "h": _help,
    # mode / flow
    "mode": _mode,
    "next": _next,
    "dismiss": _dismiss,
    # timeout (also reachable from CLI/web; channel path bypasses ref check)
    "timeout": _timeout, "to": _timeout, "pause": _timeout,
    # informational
    "scoreline": _scoreline, "score": _scoreline, "sc": _scoreline,
    "picks": _picks, "pk": _picks,
    "bans": _bans, "bn": _bans,
    "protects": _protects, "pro": _protects, "prot": _protects,
    "status": _status, "st": _status,
    # lobby control
    "setmap": _setmap, "sm": _setmap, "map": _setmap,
    "timer": _timer, "t": _timer, "ti": _timer,
    "startmap": _startmap, "start": _startmap, "go": _startmap,
    "abort": _abort, "ab": _abort,
    "undo": _undo, "u": _undo,
    "close": _close, "cl": _close,
    "invite": _invite, "inv": _invite,
    "refresh": _refresh, "rf": _refresh,
}
