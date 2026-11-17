---
name: web-app-automation
description: Work through a web app in a browser on your own. Use when someone wants a web app tested and the bugs reported, end-to-end tests written for it, or a process with many steps carried out in it (enter records, fill forms, export).
license: Apache-2.0
compatibility: A browser the agent can drive from the shell, for example agent-browser or Playwright with Chromium
metadata:
  version: "1"
  geki-tags: browser, e2e, testing, automation, web-app, playwright
  geki-category: dev
  geki-image: browser
---

# Web app automation

This is advice, not a procedure. How you go through the app is yours to decide. The points below keep the work short and the result true.

## How to work

One click per step is the slow part of this work. Every step costs a round trip, and a long task has hundreds.

- Look around first, briefly: every page once, its address, its forms, and what loads late. A page you know by address needs no clicks to reach.
- Put steps that belong together into one call: fill, fill, click, wait, read.
- The second time you do the same flow (sign in, create a record, go through a wizard), put it into a small script with parameters and call that. Give the script selectors that stay the same after a reload (id, name, label, text), not references from one snapshot.
- Read little. Ask for what you need to know (one text, one table, a count), not the whole page after every step. Open a picture only when text cannot answer the question.
- Wait for a thing (a text, an address, an element), not for a time. After a click that sends a form, wait for its result before you open another page, or the request is cut off.
- A wait for something that never comes costs the full timeout, and so does a selector you guessed. Look at a form's fields once before you write selectors for it. Keep the timeout short on a fast app. When an action can end two ways (saved or refused), wait for something both outcomes show, then read which one it was.

## Check the state, not the message

A success message says what the app believes. What matters is what is stored. This is where bugs stay hidden and where a process goes wrong without anyone noticing.

- After every action that changes data, read the result where a user would look for it: the list, the detail page, the count, the export.
- After you create or edit a record, open it again and compare every field with what you entered, also the fields you did not touch.
- Take the "no" path too: cancel, close, back, dismiss the dialog. Then check that nothing changed.
- When the page states a number (23 items, 3 pages, 4 low in stock), count it yourself over all pages. Compare the same number in every place that shows it.
- Compute sums and derived values yourself, with input that would show a mistake: a quantity other than 1, more than one line, a decimal.
- After a value went into a field that is not a plain text box (date, time, select, a custom widget), read the value back.

## Testing an app and reporting bugs

- Write down the features you found. Go through each with the checks above and with these:
  - Lists: sort every column (numbers such as 9, 10 and 100; text with upper and lower case), search (case, part of a word, no hit), filter, first and last page.
  - Input: empty, only spaces, zero, negative, very long, a duplicate, characters such as `<` and `ä`.
  - Session: after sign-out open an inner page by its address. Open one without signing in.
  - Every link in the navigation and the footer.
- Your own tests change the data. Reset the app, or count what you added, before you judge a number.
- A finding has the steps, what you expected and what happened. Reproduce it once more from a fresh state before you write it down. What you saw once can be your own mistake: an old reference, data of an earlier test, a click that landed elsewhere. Try a "does not work" a second way before you report it.
- The other way round too: do not put a strange result down to your tool without a check. When cancel still deletes, find out whether the app did it or your tool answered the dialog.
- The report puts the worst first and ends with what you tested without a finding and what you did not test.

## Writing end-to-end tests

- Use the test framework the project already has. If there is none, take a common one that drives a real browser.
- Try each flow in the live browser first, then write the test. Find elements the way a user does: role and name, label, text.
- Every test makes its own data with a name of its own and passes alone and in any order.
- Assert the stored state as above. A test that only checks the success message passes on a broken app.
- No fixed sleeps. Wait for the element or the text.
- A full run is slow. While you write, run only the test you work on, and let it stop at the first failure. Run the whole suite once at the end and once more after your last change.
- When a test shows a bug in the app, keep the test for the right behaviour, mark it as an expected failure with one line on the bug, and list the bug in your answer. Do not bend the test to the bug.
- Hand over: the files, one command to install, one command to run, the address and the sign-in data as settings outside the code, and how long a run takes. Run the suite once from a clean copy of what you hand over.

## Carrying out a process

- Read all the input before the first write, and hold it against what the app shows: its lists, its stock, its limits. Find what will not go through: a record that is missing, a name that fits two entries, a value the app will refuse.
- When a person is there, ask once, with all questions together. When nobody can answer (a scheduled run), do the clear cases, leave the unclear ones, and report them. Never guess a record, and do not change a value so that the app accepts it.
- Do the first one step by step and check what was stored. Then script the rest.
- Make it safe to run twice: look whether the record is already there before you create it. When a step fails halfway, find out what was saved before you try again.
- Keep a log while you go: input row, the id the app gave, or the reason it was left out.
- At the end compare both sides: rows in, records created, records left out, and the totals. Report what the app computes wrong. It is not yours to correct.

## The answer

What was done, what was left out and why, what is uncertain, and the files.
