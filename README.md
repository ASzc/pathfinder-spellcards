# Pathfinder Spellcards

## Context

I found [Perram's Spellbook](http://www.thegm.org/perramsSpellbook.php) to be useful for generating TCG-style cards for spells cast in the RPG Pathfinder. However, the output is HTML, and so printing them was a bit of a pain, and the layout didn't work quite correctly. So, I've written a Python script to take the Perram's Spellbook HTML and convert it to LaTeX source. From there, LaTeX's superior layout engine can create a nice PDF to print out.

## Workflow

The card creation workflow is:

1. Run Perram's Spellbook with the options you desire, then save the plain HTML source to a file.
2. Run the python script (see `./perrams_spellbook_latex.py -h` for help text) on the saved HTML
3. Copy the generated LaTeX source into the document area of `spellcards.tex`
4. Run `xelatex spellcards.tex`
5. View `spellcards.pdf` with a PDF reader, and print if desired.

As-is the tex source is configured to produce pages 3" wide and 5" high, for printing onto pre-cut index cards of that size. You could change that if desired, LaTeX generally handles that sort of thing quite well. You may also want to change the font selection, if you can't find the default one.

## Printing

I found these print settings worked well for me (I used [evince](https://en.wikipedia.org/wiki/Evince)):

- "Select page size using document page size" checkbox enabled
- Page Scaling: None

The PDF includes 0.17" margins by default. These are the minimum allowed by my printer, a HP LaserJet Pro M203dw.
