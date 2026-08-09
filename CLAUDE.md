Don't cd into the directory we're already in
Use relative paths by default
Never edit my handwritten todos
The python setup is kind of weird, check for that at the start

If you're writing a long script in a bash quote, put it in a file instead and then run the file.
No line longer than 100 characters
No function longer than 100 lines
No file longer than 1000 lines
If there's a bug add a test that catches it
Write fuzz tests
Don't Repeat Yourself. If there's some technical code make sure it lives in one function, not two different places. If there are some hardcoded values, this data should live in at most one place.
If you need to think for a long time then first think for a short time to make a plan.

Latex
    Do not make weird short lines in latex
        Latex text paragraphs can go all in 1 line
        If you have to decide how long a line should be, target roughly 80 characters (not a hard cap)
        Equations can have one line per align, or even one line for left side, one for right, and one for inline explanation text
    Explanatory text between equations should try to be at least 3 lines (several sentences)
        One option is to swap text and equation blocks
        One option is to inline short text lines into align equations

Equations
    When writing display equations in latex, don't include punctuation between equations or at the end
    When writing algorithms don't include periods for single sentences
    If an equation has 2 or more equalities or complex expressions split it into an {align}
        In rare cases a second equality with somethign small on the other side can stay
    During derivations, display equations should come in blocks of 2-5 if reasonable
    Nobody says "the display" to refer to a display equation. Give it a number if you need to, or say "this".

Diagrams
    Illustrate visually. Don't overuse text. You can give a small caption if appropriate. Boxes with equations or lemma names that point to each other are weak diagrams.
    If a symbol labels part of the diagram and that symbol is defined in the text outside the diagram, it doesn't need to be defined or explained in the diagram
    If you can define diagram labels with a variable and place that variable in the main .tex then it's easier to edit
    Diagrams are code
        Use loops and functions where appropriate
        Magic numbers are necessary for some coordinates but many coordinates can be derived from a few common coordinates
        Labels can be attached to objects instead of placed at coordinates, but it's ok to hardcode fixes when this causes overlap

Always compact at 150k tokens in context or earlier
Do not explain your reasoning and the history of a file in the file. You can explain it in the chat box to me.
Err on the side of shorter explanations, shorter todo items, shorter everything
Do not start responses with "You're right."
Never tell me what not to do. "Leave X unchanged" is a no-op and not worth mentioning.

Write like a human
    Use active language
    Avoid adding adverbs after subj verb obj / ending sentences in 'ly.' like "we arrange the deck cleanly" or "prefer 4.tex clearly".
    Avoid saying "the X" where X is technical jargon we haven't defined
    Avoid excessive/jargony adjectives that don't add to the meaning
