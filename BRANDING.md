# Branding

The mark, the palette, and what to change if you fork this.

---

## The mark

`ui/public/mark.svg` — a **V** drawn as two descending strokes, with audio meter bars nested in
the negative space where the letter narrows.

The idea is that the letter and the waveform are the same shape. A transcription tool's mark
should look like sound, and a V already does: it is a trough, a level meter, a cone.

Geometry sits on a 64-unit grid so it stays crisp at 16, 32 and 64 px without hinting.

```
viewBox   0 0 64 64
ground    #0B0C10   rounded 14
stroke    #66FCF1 → #45A29E   diagonal gradient, 5 units, round caps
bars      #45FC91   3 bars, shortest at centre
```

The bars are deliberately uneven and shortest in the middle — a level meter at rest reads as
dead, and three equal bars read as a logo rather than a signal.

---

## Palette

| Token | Hex | Use |
|---|---|---|
| ground | `#0B0C10` | page and mark background |
| surface | `#1A1E2A` | cards, panels |
| accent | `#66FCF1` | primary action, the mark's light stroke |
| accent-deep | `#45A29E` | the mark's dark stroke, hover states |
| signal | `#45FC91` | the meter bars, success, "recording" |
| muted | `#7A7D85` | secondary text |

Dark-first, because this is a tool people run while doing something else and a bright panel in
a dark editor is hostile.

Cyan reads as instrumentation rather than consumer software, which is the right register for
something whose selling point is that you can verify what it does.

---

## Type

The UI ships **Inter**, subset to Latin and Latin-Extended, self-hosted in the bundle. No font
CDN, because a font request is a network request and this tool's whole claim is that it makes
none.

For Devanagari and other Indic scripts, the browser's system font is used. Bundling Noto for
eight scripts would add several megabytes to serve text that every platform already renders
well.

---

## If you fork this

Change the mark. It is not licensed separately — MIT, like the rest — but a fork carrying
someone else's identity confuses whoever finds it.

```
ui/public/mark.svg          the mark
ui/public/favicon.ico       32 px raster
ui/index.html               <title> and theme-color
ui/tailwind.config.ts       the palette tokens
```

Everything else reads from those.

---

## What is deliberately absent

**No wordmark.** A mark alone travels better — favicon, tray icon, app list — and a fork that
changes the name does not have to redraw type.

**No illustration.** Product screenshots go stale the moment the UI changes; the mark does not.

**No brand voice guide.** Write plainly, say what things do, and do not claim more than the
measurements support. That is the whole of it.
