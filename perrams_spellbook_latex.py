#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import collections
import fnmatch
import logging
import sys

import bs4

logger = logging.getLogger("psl")

#
# HTML and Data Model
#

Spell = collections.namedtuple("Spell", ["title", "attributes", "description", "source"])

def parse_spells(in_stream):
    spells = []
    # html.parser seems to stop half-way, maybe it can't handle the huge line length?
    soup = bs4.BeautifulSoup(in_stream, "lxml")
    open_spell = None
    spell_attributes = None
    description_parts = None
    source_attribution = None
    last_description_text_was_break = None
    for div in filter(lambda x: "pageBreak" not in x["class"] , soup.body.find_all("div", recursive=False)):
        title_candidate = div.h1.get_text()
        if "(Continued)" in title_candidate or "- [Table " in title_candidate:
            assert open_spell is not None, "Continued spell without an open spell: {title_candidate}".format(**locals())
            assert title_candidate.startswith(open_spell), "Continued spell doesn't match open spell: {title_candidate} {open_spell}".format(**locals())
        else:
            # Wrap up open spell, and open this new one
            if open_spell is not None:
                spells.append(Spell(open_spell, spell_attributes, description_parts, source_attribution))
            open_spell = title_candidate
            spell_attributes = collections.OrderedDict()
            description_parts = []
            last_description_text_was_break = True

            # All new spell cards will have a list of attributes
            spell_attribute_soup = div.find("div", {"class": "spellAttributes"})
            assert spell_attribute_soup is not None, "Newly opened spell contains no attributes: {open_spell}".format(**locals())
            key = None
            for text_node in spell_attribute_soup.p.children:
                if text_node.name == "strong":
                    assert key is None, "Two keys defined in sequence: {key} {text_node} ".format(**locals())
                    key = text_node.get_text(strip=True)
                elif str(text_node) in ("<br/>", " "):
                    pass
                elif key is not None:
                    spell_attributes[key] = str(text_node).strip(";")
                    key = None
                else:
                    assert False, "Unknown attribute component: {text_node}".format(**locals())

            # All new spell cards will have a source attribution
            card_note_soup = div.find("div", {"class": "cardNote"})
            assert card_note_soup is not None, "Newly opened spell contains no card note: {open_spell}".format(**locals())
            source_attribution = str(card_note_soup.contents[0]).strip()
            assert source_attribution.startswith("Source: "), "Newly opened spell contains no source attribution: {open_spell}".format(**locals())
            source_attribution = source_attribution[8:]

        # All cards contain a description or a table
        spell_description_soup = div.find("div", {"class": "spellDescription"})
        if spell_description_soup is None:
            table_soup = div.find("table")
            assert table_soup is not None, "Spell card doesn't contain a description or a table: {title_candidate} {open_spell}".format(**locals())
            # We're assuming that all tables are simple: one header row at top,
            # data in columns underneath each header. If that assumption is
            # wrong, then we will need to actually model how the tables are
            # structured and styled.
            table = []
            description_parts.append(table)
            for row_soup in table_soup.find_all("tr", recursive=False):
                row = []
                table.append(row)
                for item_soup in row_soup.children:
                    row.append(item_soup.get_text(strip=True))
        else:
            for text_node in spell_description_soup.p.children:
                text = str(text_node).strip()
                if text in ("<br/>", ""):
                    # The card pagination may have split a single paragraph between two cards
                    last_description_text_was_break = True
                else:
                    if last_description_text_was_break:
                        description_parts.append(text)
                    else:
                        description_parts[-1] += " " + text
                    last_description_text_was_break = False
    return spells

#
# LaTeX
#

def format_spells(spells, out_stream):
    for spell in spells:
        out_stream.write(r"\section*{")
        out_stream.write(spell.title)
        out_stream.write("}\n")

        out_stream.write(r"\begin{description}")
        out_stream.write("\n")
        for k,v in spell.attributes.items():
            out_stream.write(r"\item [{")
            out_stream.write(k.replace(" ", "~"))
            out_stream.write("}] ")
            out_stream.write(v)
            out_stream.write("\n")
        out_stream.write(r"\end{description}")
        out_stream.write("\n")

        for description in spell.description:
            if isinstance(description, list):
                out_stream.write(r"\begin{table}[ht]")
                out_stream.write("\n")
                out_stream.write(r"\centering")
                out_stream.write("\n")
                out_stream.write(r"\caption{")
                out_stream.write(spell.title)
                out_stream.write("}\n")
                out_stream.write(r"\label{t_sim}")
                out_stream.write("\n")
                out_stream.write(r"\begin{tabular}{")
                out_stream.write("l" * len(description[0]))
                out_stream.write("}\n")
                out_stream.write(r"\toprule")
                out_stream.write("\n")
                initial = True
                for header in description[0]:
                    if not initial:
                        out_stream.write(" & ")
                    initial = False
                    out_stream.write(r"\thead{")
                    out_stream.write(header)
                    out_stream.write("}")
                out_stream.write(r" \\")
                out_stream.write("\n")
                out_stream.write(r"\midrule")
                out_stream.write("\n")
                for row in description[1:]:
                    initial = True
                    for datum in row:
                        if not initial:
                            out_stream.write(" & ")
                        initial = False
                        out_stream.write(datum)
                    out_stream.write(r" \\")
                    out_stream.write("\n")
                out_stream.write(r"\bottomrule")
                out_stream.write("\n")
                out_stream.write(r"\end{tabular}")
                out_stream.write("\n")
                out_stream.write(r"\end{table}")
                out_stream.write("\n")
            else:
                out_stream.write(description)
                out_stream.write("\n")
            out_stream.write("\n")

        out_stream.write(r"\hfill Source: ")
        out_stream.write(spell.source)
        out_stream.write("\n\n")

#
# Conversion
#

def spell_glob_filter(patterns, spells, case_insensitive=True):
    if case_insensitive:
        patterns = [(t, p.lower()) for t,p in patterns]
    for spell in spells:
        drop = False
        # Could do this more efficiently if only one pattern per attribute were allowed.
        for attr_name, attr_value in spell.attributes.items():
            for target, pattern in patterns:
                if attr_name == target:
                    if case_insensitive:
                        attr_value = attr_value.lower()
                    if fnmatch.fnmatch(attr_value, pattern):
                        drop = True
                        break
            if drop:
                break
        if not drop:
            yield spell

def html_to_latex(in_stream, out_stream, patterns):
    spells = parse_spells(in_stream)
    format_spells(spell_glob_filter(patterns, spells), out_stream)
    #print(list(spell_glob_filter(patterns, spells)))

class OpenOrNone(object):
    def __init__(self, path):
        self.path = path
        self.f = None
    def __enter__(self):
        if self.path is not None:
            self.f = open(self.path, "r")
        return self.f
    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.f is not None:
            self.f.close()

def htmlfile_to_latexfile(in_file, out_file, template, patterns):
    with OpenOrNone(template) as tin, open(in_file, "r") as fin,  open(out_file, "w") as fout:
        if tin is not None:
            for line in tin:
                fout.write(line)
                if line == "\\begin{document}\n":
                    break
        html_to_latex(fin, fout, patterns)
        if tin is not None:
            for line in tin:
                fout.write(line)

#
# Main
#

def create_argparser():
    parser = argparse.ArgumentParser(description="Convert HTML spellcards from Perram's Spellbook into LaTeX source")

    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-t", "--template", help="Fill in a copy of this LaTeX document with the generated syntax, sending the copy to the output specified by --output")
    parser.add_argument("-i", "--input", help="Read from a file instead of stdin", default="/dev/stdin")
    parser.add_argument("-o", "--output", help="Write into a file instead of stdout", default="/dev/stdout")
    parser.add_argument("-e", "--exclude", action="append", help="Exclude spells by applying one or more case-insensitive glob pattern to attribute values. Ex: -e 'School=*evil*' -e 'School=*lawful*'", default=[])

    return parser

def setup_logging(debug):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(name)s: %(message)s",
    )

def main(args):
    parser = create_argparser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args(args)
    setup_logging(args.debug)

    # Parse exclusion pattern(s)
    patterns = []
    for exclude in args.exclude:
        attribute_name, pattern = exclude.split("=", 1)
        patterns.append((attribute_name, pattern))

    htmlfile_to_latexfile(args.input, args.output, args.template, patterns)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
