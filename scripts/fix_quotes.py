"""
The original templates used ASCII double-quotes as Jinja2 string delimiters,
with curly double-quotes and an em-dash INSIDE as the fallback display value.
fix_quotes.py's replacement of curly double-quotes broke those by turning the
inner closing curly-quote into a second ASCII close-quote, producing '""' at
the end. This script removes the spurious extra quote to restore valid Jinja2.

Broken pattern (bytes): b'"\xc3\xa2\xe2\x82\xac""'   -> {ASCII-open}"a-euro"{ASCII}{ASCII}
Fixed pattern  (bytes): b'"-"'                          -> clean hyphen fallback
"""
import glob

# The broken sequence: ASCII-quote + ae-euro bytes + two ASCII-quotes
BROKEN = b'"\xc3\xa2\xe2\x82\xac""'
FIXED  = b'"-"'

total = 0
for path in glob.glob("app/templates/**/*.html", recursive=True):
    data = open(path, "rb").read()
    if BROKEN in data:
        count = data.count(BROKEN)
        open(path, "wb").write(data.replace(BROKEN, FIXED))
        print(f"Fixed {count} occurrence(s) in {path}")
        total += count

print(f"\nTotal: {total} fixes applied.")
