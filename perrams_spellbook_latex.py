#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import collections
import logging
import sys

import bs4

logger = logging.getLogger("psl")

#
# HTML and Data Model
#

Spell = collections.namedtuple("Spell", ["title", "attributes", "description"])

def parse_spells(in_stream):
    spells = []
    # html.parser seems to stop half-way, maybe it can't handle the huge line length?
    soup = bs4.BeautifulSoup(in_stream, "lxml")
    open_spell = None
    spell_attributes = None
    description_parts = None
    last_description_text_was_break = None
    for div in filter(lambda x: "pageBreak" not in x["class"] , soup.body.find_all("div", recursive=False)):
        title_candidate = div.h1.get_text()
        if "(Continued)" in title_candidate or "- [Table " in title_candidate:
            assert open_spell is not None, "Continued spell without an open spell: {title_candidate}".format(**locals())
            assert title_candidate.startswith(open_spell), "Continued spell doesn't match open spell: {title_candidate} {open_spell}".format(**locals())
        else:
            # Wrap up open spell, and open this new one
            if open_spell is not None:
                spells.append(Spell(open_spell, spell_attributes, description_parts))
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



#
# Conversion
#

def html_to_latex(in_stream, out_stream):
    spells = parse_spells(in_stream)
    # TODO
    print(spells)

def htmlfile_to_latexfile(in_file, out_file):
    with open(in_file, "r") as fin,  open(out_file, "w") as fout:
        html_to_latex(fin, fout)

#
# Main
#

def create_argparser():
    parser = argparse.ArgumentParser(description="Convert HTML spellcards from Perram's Spellbook into LaTeX source")

    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-i", "--input", help="Read from a file instead of stdin", default="/dev/stdin")
    parser.add_argument("-o", "--output", help="Write into a file instead of stdout", default="/dev/stdout")

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
    htmlfile_to_latexfile(args.input, args.output)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
