JFR Teamy Mojżesz - README
=====================================================================

import scores, lineups and bidding from PBN files

Overview
========

This piece of software serves as a replacement for Kolektor in the JFR Teamy ecosystem, for when data is read not from BWS files, but from Portable Bridge Notation files.

It was developed specifically for the purpose of importing data from PBN dumps from LoveBridge tablet system (get it? tablets, Moses, funny. why aren't you laughing?), but should be capable of handling PBN files in general.

Prerequsites
============

 * Python 2.7 (sorry)
 * Python MySQL connector
 * python-requests
 * for EXE compilation: PyInstaller 3.6

Usage
=====

```
python src/main.py
```

Configuration
=============

Two main data sources are required to run the script:

 * a PBN file accessible via HTTP(S)
 * a `mojzesz.json` config file in the current (working) directory

Sample config file is provided in the repo. `mysql` and `source` sections should be self-explanatory (`auth` section is not required if PBN is not behind HTTP Auth, and `headers` section is just explicitly forwarded to the HTTP(S) request headers).

As for `settings` section:

 * `pbn_round` is the round in PBN file for which the boards should be read (filtered by `[Round "X"]` fields)
 * `teamy_round` and `teamy_segment` point to the round and segment in JFR Teamy event database into which data is imported
 * `fetch_lineups` enables reading lineups from PBN files, strict comparison of full name + surname is conducted, and players have to be in correct Teamy rosters
 * `lineup_board_no` specifies from which board lineups should be read, if not set, first board of the segment is taken; set to `0` to read from any board
 * `overwrite_scores` enables overwriting existing scores: otherwise, if a score in board points has changed in PBN from the one present in Teamy database, a warning is emitted
 * `info_messages` controls logging verbosity: 0 = warnings and errors, 1 = info messages, warnings and errors, 2 = debug output
 * `job_interval` is number of seconds between subsequent runs

The script is meant to run continuously, both PBN and config files are read from scratch on every iteration.

Quirks, assumptions and known issues
====================================

 * one only section within the PBN is supported: table number (`[Table "XX"]`) is stripped of any section letters and converted to numerical value that must match the table number in Teamy database
 * LoveBridge exports seem to indicate double in the `[Contract ""]` field by `*`, not `x` - both notations are supported
 * bidding data is always overwriting values in the database
 * lineups, if requested, are always overwriting values in the database
 * if the records for specific boards are missing from the `scores` table in event database (as in, JFR Webmaster haven't created them yet), they are created

Author
======

This software was made by [Michał Klichowicz](https://emkael.info).

If you use it, you probably know how to reach me.

If you don't (know how to reach me), you can find it on my website.

License
=======

PBN parsing makes significant use of [the Python port of BCDD](https://github.com/emkael/pybcdd), with BCalc binding removed, in a blatant act of self-plagiarism.

So I guess it's suitable to share this under [BSD-2-Clause license](LICENSE), as well.

---

`In a room with a window in the corner I found truth`
